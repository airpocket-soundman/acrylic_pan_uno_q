from __future__ import annotations

import json
import math
import struct
import threading
import time
from pathlib import Path

from arduino.app_utils import App, Bridge, Logger

from audio_synth import initialize_audio, synthesize_note
from tflite_position_models import SelectablePositionModels
from training_manager import PANEL, TrainingManager
from web_server import start_web_server

ROOT = Path(__file__).resolve().parent
DATA_ROOT = Path("data")
STATIC_ROOT = ROOT / "static"
MODEL_ROOT = ROOT / "tflite_models"
CAPTURE_PATH = DATA_ROOT / "captures" / "kx134_events.jsonl"
INFERENCE_PATH = DATA_ROOT / "inference" / "results.jsonl"
SAMPLE_RATE_HZ = 25_600
EVENT_SAMPLES = 512

logger = Logger("acrylic-pan-kx134")
lock = threading.RLock()
ai_changed = threading.Condition(lock)
pending: dict[int, dict] = {}
INFERENCE_THRESHOLDS = {"jerk": 700, "level": 200, "confirmation": 3000}
COLLECTION_THRESHOLDS = {"jerk": 350, "level": 100, "confirmation": 1500}
runtime = {
    "connected": True, "port": "UNO Q internal SPI", "device_mode": "inference",
    "inference_active": True, "sensor_ready": False, "latest_ai": None,
    "event_count": 0, "sample_rate_hz": SAMPLE_RATE_HZ, "retrigger_guard_ms": 120,
    "last_error": None, "sensor_thresholds": dict(INFERENCE_THRESHOLDS),
    "sampling_sample_count": 0, "sampling_irq_count": 0, "missed_data_ready": 0,
    "read_1000_us": 0, "hardware_cycle_hz": 0,
    "observed_z_min": 0, "observed_z_max": 0, "observed_max_jerk": 0,
}
model = SelectablePositionModels(MODEL_ROOT, DATA_ROOT)
training = TrainingManager(DATA_ROOT, model)


def _normalize_result(result: dict) -> dict:
    probabilities = result["position_probabilities"]
    support = result["support_xy_mm"]
    area_probabilities = [0.0] * 12
    for probability, (x_mm, y_mm) in zip(probabilities, support):
        column = min(3, max(0, int(x_mm // 100)))
        row = min(2, max(0, int(y_mm // 100)))
        area_probabilities[row * 4 + column] += float(probability)
    result["class_probabilities"] = area_probabilities
    result["predicted_class"] = max(range(12), key=area_probabilities.__getitem__)
    result["distribution_peak_probability"] = result.pop("peak_probability")
    result["distribution_entropy"] = -sum(p * math.log(max(p, 1e-12)) for p in probabilities)
    return result


def _position(result: dict) -> dict:
    return {
        "x_mm": result["x_mm"], "y_mm": result["y_mm"],
        "expected_x_mm": result["expected_x_mm"], "expected_y_mm": result["expected_y_mm"],
        "map_x_mm": result["map_x_mm"], "map_y_mm": result["map_y_mm"],
        "direct_x_mm": result["direct_x_mm"], "direct_y_mm": result["direct_y_mm"],
        "sigma_x_mm": result["sigma_x_mm"], "sigma_y_mm": result["sigma_y_mm"],
        "confidence_level": .9,
        "classification_confidence": max(result["class_probabilities"]),
        "class_probabilities": result["class_probabilities"],
        "probability_map": {
            "support_xy_mm": result["support_xy_mm"],
            "probabilities": result["position_probabilities"],
            "credible_90_indices": result["credible_90_indices"], "normalization": "sum_1",
        },
        "distribution_peak_probability": result["distribution_peak_probability"],
        "distribution_entropy": result["distribution_entropy"],
        "model_available": True, "method": result["method"],
        "inference_accelerator": result["inference_accelerator"], "inference_source": "device",
        "scope": "KX134 25.6 kHz / 60測定点確率・疑似XY・直接XY",
    }


def store_result(result: dict, event: dict | None = None) -> dict:
    result = _normalize_result(result)
    with lock:
        sequence = int(result.get("sequence", runtime["event_count"] + 1))
        ai = {**result, "sequence": sequence, "outputs": result["class_probabilities"],
              "position": _position(result), "created_at_unix_ns": time.time_ns()}
        if event:
            ai["event"] = event
        runtime["latest_ai"] = ai
        runtime["event_count"] += 1
        ai_changed.notify_all()
    INFERENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with INFERENCE_PATH.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(ai, ensure_ascii=False, separators=(",", ":")) + "\n")
    return ai


def wait_for_ai(after, timeout: float) -> dict:
    """Block without polling until a new inference result is available."""
    def available() -> bool:
        latest = runtime.get("latest_ai")
        return bool(latest and str(latest.get("sequence")) != str(after))

    with ai_changed:
        ai_changed.wait_for(available, timeout=timeout)
        return dict(runtime.get("latest_ai") or {}) if available() else {}


def run_demo(case_id: int = 0) -> dict:
    return store_result(model.parity_case(case_id))


def get_status() -> dict:
    with lock:
        status = dict(runtime)
    status.update({
        "panel": PANEL, "panel_profile_id": PANEL["id"], "panel_profiles": [PANEL],
        "collection": training.status(), "training": dict(training.training),
        "model": model.name, "model_accelerator": model.accelerator,
        "model_metadata": model.metadata, "web_port": 8765,
        "inference_model_id": model.active_id, "inference_model_label": model.label,
        "inference_models": model.available(),
        "output_root": str(DATA_ROOT / "training"), "session_dir": None,
        "last_control": None, "assembly": {"progress": None, "retry_required": False},
        "stats": {"events_received": status["event_count"], "events_saved": status["event_count"],
                  "missing_sequences": 0, "decoder_errors": 0, "duplicate_sequences": 0,
                  "out_of_order_sequences": 0, "save_errors": 0},
    })
    return status


def update_runtime(**values) -> dict:
    with lock:
        runtime.update(values)
    return get_status()


def select_inference_model(model_id: str) -> dict:
    model.select(model_id)
    return get_status()


def set_retrigger_guard(milliseconds: int) -> dict:
    milliseconds = int(milliseconds)
    if not 0 <= milliseconds <= 500:
        raise ValueError("milliseconds must be between 0 and 500")
    # The MCU keeps a dedicated, non-yielding 25.6 kHz loop. Its original
    # The 120 ms guard remains fixed in the MCU to reject sensor ring-down without
    # blocking this web request on an inbound RPC while its sampling loop is active.
    update_runtime(retrigger_guard_ms=milliseconds)
    return {"milliseconds": milliseconds, "confirmed": milliseconds == 120}


def set_sensor_thresholds(profile: str) -> dict:
    thresholds = COLLECTION_THRESHOLDS if profile == "collection" else INFERENCE_THRESHOLDS
    # Capture uses the original KX134 thresholds in the MCU. Mode changes only
    # decide whether a completed event is saved for training or inferred.
    fixed = dict(INFERENCE_THRESHOLDS)
    update_runtime(sensor_thresholds=fixed)
    return {"profile": profile, **fixed}


def on_runtime_status(mode: str, sensor_ready: bool) -> None:
    active_mode = "collection" if training.active else ("inference" if mode == "sensor" else mode)
    update_runtime(device_mode=active_mode, sensor_ready=sensor_ready)


def on_sensor_status(ready: bool, who_am_i: int) -> None:
    update_runtime(sensor_ready=ready, last_error=None if ready else f"KX134 WHO_AM_I=0x{who_am_i:02X}")
    (logger.info if ready else logger.error)(
        f"KX134 {'ready' if ready else 'not found'} (WHO_AM_I=0x{who_am_i:02X})")


def on_sampling_status(sample_count: int, missed_data_ready: int,
                       read_1000_us: int, hardware_cycle_hz: int,
                       observed_z_min: int, observed_z_max: int,
                       observed_max_jerk: int) -> None:
    update_runtime(sampling_sample_count=sample_count, missed_data_ready=missed_data_ready,
                   read_1000_us=read_1000_us, hardware_cycle_hz=hardware_cycle_hz,
                   observed_z_min=observed_z_min, observed_z_max=observed_z_max,
                   observed_max_jerk=observed_max_jerk)


def on_capture_sample(sequence: int, offset: int, z: int, trigger_index: int,
                      peak_abs: int, irq_count: int) -> None:
    """Compatibility path for older sketches that sent one RPC per sample."""
    _accept_capture_values(sequence, offset, [z], trigger_index, peak_abs, irq_count)


def on_capture_chunk(sequence: int, offset: int, payload,
                     trigger_index: int, peak_abs: int, irq_count: int) -> None:
    """Receive one packed little-endian int16 waveform chunk from the MCU."""
    raw = bytes(payload)
    if len(raw) % 2:
        logger.error(f"Discarding odd capture chunk ({len(raw)} bytes)")
        return
    values = struct.unpack(f"<{len(raw) // 2}h", raw)
    _accept_capture_values(sequence, offset, values, trigger_index, peak_abs, irq_count)


def _accept_capture_values(sequence: int, offset: int, values,
                           trigger_index: int, peak_abs: int, irq_count: int) -> None:
    with lock:
        runtime["sensor_ready"] = True
        event = pending.setdefault(sequence, {
            "sequence": sequence, "sensor": "KX134-1211", "range_g": 32,
            "sample_rate_hz": SAMPLE_RATE_HZ, "trigger_index": trigger_index,
            "peak_abs": peak_abs, "irq_count": irq_count, "z": [None] * EVENT_SAMPLES,
        })
        end = offset + len(values)
        if not 0 <= offset < end <= EVENT_SAMPLES:
            return
        event["z"][offset:end] = values
        if any(value is None for value in event["z"]):
            return
        pending.pop(sequence, None)
    event["captured_at_unix_ns"] = time.time_ns()
    CAPTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CAPTURE_PATH.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event, separators=(",", ":")) + "\n")
    training.record(event)
    with lock:
        active = runtime["inference_active"]
    if active:
        result = model.predict_samples(event["z"])
        result.update({"sequence": sequence, "source": "kx134_capture", "peak_abs": peak_abs})
        store_result(result, event)


Bridge.provide("on_sensor_status", on_sensor_status)
Bridge.provide("on_runtime_status", on_runtime_status)
Bridge.provide("on_sampling_status", on_sampling_status)
Bridge.provide("on_capture_sample", on_capture_sample)
Bridge.provide("on_capture_chunk", on_capture_chunk)
audio_backend = initialize_audio()
start_web_server(STATIC_ROOT, get_status, update_runtime, run_demo, training, synthesize_note,
                 set_retrigger_guard, set_sensor_thresholds, wait_for_ai,
                 select_inference_model, audio_backend=audio_backend)
logger.info(f"KX134 acquisition, inference and web UI listening on port 8765; audio={audio_backend}")
App.run()
