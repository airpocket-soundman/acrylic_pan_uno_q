from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import numpy as np
from arduino.app_utils import App, Bridge, Logger

from audio_synth import synthesize_note
from mpu9250_models import EVENT_SAMPLES, ModelSuite, SAMPLE_RATE_HZ
from training_manager import PANEL, TrainingManager
from web_server import start_web_server

ROOT = Path(__file__).resolve().parent
DATA_ROOT = Path("data")
MODEL_PATH = ROOT / "mpu9250_models.npz"
METADATA_PATH = ROOT / "mpu9250_model_metadata.json"
SEED_PATH = ROOT / "mpu9250_training_seed.npz"
STATIC_ROOT = ROOT / "static"
CAPTURE_PATH = DATA_ROOT / "captures" / "mpu9250_events.jsonl"
INFERENCE_PATH = DATA_ROOT / "inference" / "results.jsonl"
logger = Logger("acrylic-pan-mpu9250")
lock = threading.RLock()
pending: dict[int, dict] = {}
INFERENCE_THRESHOLDS = {"jerk": 1400, "level": 400, "confirmation": 6000}
COLLECTION_THRESHOLDS = {"jerk": 600, "level": 200, "confirmation": 1800}
runtime = {"connected": True, "port": "UNO Q internal SPI", "device_mode": "inference",
           "inference_active": True, "sensor_ready": False, "latest_ai": None,
           "event_count": 0, "sample_rate_hz": SAMPLE_RATE_HZ, "retrigger_guard_ms": 80,
           "last_error": None, "sensor_thresholds": dict(INFERENCE_THRESHOLDS)}
model = ModelSuite(MODEL_PATH, METADATA_PATH)
training = TrainingManager(DATA_ROOT, SEED_PATH, model)
with np.load(SEED_PATH, allow_pickle=False) as seed:
    demo_waveforms = np.asarray(seed["waveforms"])


def _position(result: dict) -> dict:
    return {"x_mm": result["x_mm"], "y_mm": result["y_mm"],
            "expected_x_mm": result["expected_x_mm"], "expected_y_mm": result["expected_y_mm"],
            "map_x_mm": result["map_x_mm"], "map_y_mm": result["map_y_mm"],
            "direct_x_mm": result["direct_x_mm"], "direct_y_mm": result["direct_y_mm"],
            "sigma_x_mm": result["sigma_x_mm"], "sigma_y_mm": result["sigma_y_mm"],
            "confidence_level": .9, "classification_confidence": max(result["class_probabilities"]),
            "class_probabilities": result["class_probabilities"],
            "probability_map": {"support_xy_mm": result["support_xy_mm"],
                                "probabilities": result["position_probabilities"],
                                "credible_90_indices": result["credible_90_indices"], "normalization": "sum_1"},
            "distribution_peak_probability": result["distribution_peak_probability"],
            "distribution_entropy": result["distribution_entropy"],
            "model_available": True, "method": result["method"], "inference_source": "device",
            "scope": "MPU9250 4 kHz / 60測定点確率・疑似XY・直接XY"}


def store_result(result: dict, event: dict | None = None) -> dict:
    with lock:
        sequence = int(result.get("sequence", runtime["event_count"] + 1))
        ai = {**result, "sequence": sequence, "outputs": result["class_probabilities"],
              "position": _position(result), "created_at_unix_ns": time.time_ns()}
        if event: ai["event"] = event
        runtime["latest_ai"] = ai; runtime["event_count"] += 1
    INFERENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with INFERENCE_PATH.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(ai, ensure_ascii=False, separators=(",", ":")) + "\n")
    return ai


def run_demo(case_id: int = 0) -> dict:
    result = model.predict(demo_waveforms[case_id % len(demo_waveforms)])
    result.update({"source": "converted_training_demo", "case_id": case_id})
    return store_result(result)


def get_status() -> dict:
    with lock: status = dict(runtime)
    status.update({"panel": PANEL, "panel_profile_id": PANEL["id"], "panel_profiles": [PANEL],
                   "collection": training.status(), "training": dict(training.training),
                   "model": model.metadata["model"], "model_metadata": model.metadata, "web_port": 8765})
    status.update({"output_root": str(DATA_ROOT / "training"), "session_dir": None,
                   "last_control": None, "assembly": {"progress": None, "retry_required": False},
                   "stats": {"events_received": status["event_count"], "events_saved": status["event_count"],
                             "missing_sequences": 0, "decoder_errors": 0, "duplicate_sequences": 0,
                             "out_of_order_sequences": 0, "save_errors": 0}})
    return status


def update_runtime(**values) -> dict:
    with lock: runtime.update(values)
    return get_status()


def set_retrigger_guard(milliseconds: int) -> dict:
    milliseconds = int(milliseconds)
    if not 0 <= milliseconds <= 500:
        raise ValueError("milliseconds must be between 0 and 500")
    Bridge.call("set_retrigger_guard", milliseconds)
    update_runtime(retrigger_guard_ms=milliseconds)
    return {"milliseconds": milliseconds, "confirmed": True}


def set_sensor_thresholds(profile: str) -> dict:
    thresholds = COLLECTION_THRESHOLDS if profile == "collection" else INFERENCE_THRESHOLDS
    Bridge.call("set_thresholds", thresholds["jerk"], thresholds["level"], thresholds["confirmation"])
    update_runtime(sensor_thresholds=dict(thresholds))
    return {"profile": profile, **thresholds}


def on_runtime_status(mode: str, sensor_ready: bool) -> None:
    active_mode = "collection" if training.active else ("inference" if mode == "sensor" else mode)
    update_runtime(device_mode=active_mode, sensor_ready=sensor_ready)


def on_sensor_status(ready: bool, who_am_i: int) -> None:
    update_runtime(sensor_ready=ready, last_error=None if ready else f"MPU9250 WHO_AM_I=0x{who_am_i:02X}")
    (logger.info if ready else logger.error)(f"MPU9250 {'ready' if ready else 'not found'} (WHO_AM_I=0x{who_am_i:02X})")


def on_capture_sample(sequence: int, offset: int, x: int, y: int, z: int,
                      trigger_index: int, peak_abs: int, irq_count: int) -> None:
    with lock:
        runtime["sensor_ready"] = True
        event = pending.setdefault(sequence, {"sequence": sequence, "sample_rate_hz": SAMPLE_RATE_HZ,
            "trigger_index": trigger_index, "peak_abs": peak_abs, "irq_count": irq_count,
            "x": [None] * EVENT_SAMPLES, "y": [None] * EVENT_SAMPLES, "z": [None] * EVENT_SAMPLES})
        if not 0 <= offset < EVENT_SAMPLES: return
        event["x"][offset], event["y"][offset], event["z"][offset] = x, y, z
        if any(value is None for value in event["z"]): return
        pending.pop(sequence, None)
    event["captured_at_unix_ns"] = time.time_ns(); CAPTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CAPTURE_PATH.open("a", encoding="utf-8") as stream: stream.write(json.dumps(event, separators=(",", ":")) + "\n")
    training.record(event)
    with lock: active = runtime["inference_active"]
    if active:
        result = model.predict(event["z"]); result.update({"sequence": sequence, "source": "mpu9250_capture", "peak_abs": peak_abs})
        store_result(result, event)


Bridge.provide("on_sensor_status", on_sensor_status)
Bridge.provide("on_runtime_status", on_runtime_status)
Bridge.provide("on_capture_sample", on_capture_sample)
start_web_server(STATIC_ROOT, get_status, update_runtime, run_demo, training, synthesize_note,
                 set_retrigger_guard, set_sensor_thresholds)
logger.info("MPU9250 acquisition, training, inference and web UI listening on port 8765")
App.run()
