from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from arduino.app_utils import App, Bridge, Logger

from position_model import PositionModel
from web_server import start_web_server


EVENT_SAMPLES = 512
SAMPLE_RATE_HZ = 25_600
CAPTURE_PATH = Path("data/captures/events.jsonl")
INFERENCE_PATH = Path("data/inference/results.jsonl")
POSITION_MODEL_PATH = Path(__file__).with_name("position_model.npz")
POSITION_PARITY_PATH = Path(__file__).with_name("position_parity.npz")
POSITION_METADATA_PATH = Path(__file__).with_name("position_metadata.json")
STATIC_ROOT = Path(__file__).with_name("static")

logger = Logger("acrylic-pan")
lock = threading.Lock()
pending: dict[int, dict] = {}
runtime = {
    "mode": "demo",
    "sensor_ready": False,
    "latest": None,
    "event_count": 0,
    "sample_rate_hz": SAMPLE_RATE_HZ,
}
position_model = PositionModel(POSITION_MODEL_PATH, POSITION_PARITY_PATH, POSITION_METADATA_PATH)


def store_result(result: dict) -> dict:
    result = {**result, "created_at_unix_ns": time.time_ns()}
    with lock:
        runtime["latest"] = result
        runtime["event_count"] += 1
    INFERENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with INFERENCE_PATH.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n")
    return result


def run_demo(case_id: int) -> dict:
    result = position_model.parity_case(case_id % 12)
    store_result(result)
    logger.info(
        f"POSITION demo case={result['case_id']} map=({result['x_mm']:.1f},{result['y_mm']:.1f}) "
        f"expected=({result['expected_x_mm']:.1f},{result['expected_y_mm']:.1f}) "
        f"portable_delta={result['portable_delta_mm']:.6f}mm inference_us={result['inference_us']}"
    )
    return result


def run_self_test() -> list[dict]:
    return [position_model.parity_case(case_id) for case_id in range(12)]


def get_status() -> dict:
    with lock:
        current = dict(runtime)
    current.update(
        {
            "model": position_model.name,
            "model_scope": "400x300x5_60_coordinate_probability_map",
            "panel_width_mm": 400,
            "panel_height_mm": 300,
            "panel_thickness_mm": 5,
            "panel_columns": 4,
            "panel_rows": 3,
            "position_support_count": 60,
            "training_sample_count": position_model.metadata["sample_count"],
            "validation": position_model.metadata["validation"],
            "density_validation": position_model.metadata["density_validation"],
            "web_port": 8765,
        }
    )
    return current


def on_runtime_status(mode: str, sensor_ready: bool) -> None:
    with lock:
        runtime["mode"] = mode
        runtime["sensor_ready"] = sensor_ready
    logger.info(f"Runtime mode={mode}, sensor_ready={sensor_ready}")


def on_sensor_status(ready: bool, who_am_i: int) -> None:
    with lock:
        runtime["sensor_ready"] = ready
    if ready:
        logger.info(f"KX134 ready (WHO_AM_I=0x{who_am_i:02X})")
    else:
        logger.error(f"KX134 not found (WHO_AM_I=0x{who_am_i:02X})")


def on_dummy_case(case_id: int) -> None:
    # The sketch cycles cases while the sensor is unavailable. This exercises the
    # same XY inference and HTTP state used by a real capture.
    run_demo(case_id % 12)


def on_capture_chunk(
    sequence: int,
    offset: int,
    samples: list[int],
    trigger_index: int,
    peak_abs: int,
) -> None:
    with lock:
        event = pending.setdefault(
            sequence,
            {
                "sequence": sequence,
                "sample_rate_hz": SAMPLE_RATE_HZ,
                "trigger_index": trigger_index,
                "peak_abs": peak_abs,
                "samples": [None] * EVENT_SAMPLES,
            },
        )
        end = min(offset + len(samples), EVENT_SAMPLES)
        event["samples"][offset:end] = samples[: end - offset]
        if any(value is None for value in event["samples"]):
            return
        pending.pop(sequence, None)

    event["captured_at_unix_ns"] = time.time_ns()
    CAPTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CAPTURE_PATH.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")

    if trigger_index != 64:
        logger.error(f"Rejected event {sequence}: trigger_index={trigger_index}, expected=64")
        return
    prediction = position_model.predict_samples(event["samples"])
    result = store_result({**prediction, "sequence": sequence, "source": "kx134_capture", "peak_abs": peak_abs})
    logger.info(
        f"POSITION event={sequence} map=({result['x_mm']:.1f},{result['y_mm']:.1f}) "
        f"expected=({result['expected_x_mm']:.1f},{result['expected_y_mm']:.1f}) "
        f"zone={result['predicted_class'] + 1} peak={peak_abs} inference_us={result['inference_us']}"
    )


Bridge.provide("on_sensor_status", on_sensor_status)
Bridge.provide("on_runtime_status", on_runtime_status)
Bridge.provide("on_capture_chunk", on_capture_chunk)
Bridge.provide("on_dummy_case", on_dummy_case)

start_web_server(STATIC_ROOT, get_status, run_demo, run_self_test)
logger.info("Web UI listening on port 8765")
App.run()
