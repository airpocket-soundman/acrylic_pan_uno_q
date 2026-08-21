from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from arduino.app_utils import App, Bridge, Logger

from dummy_model import DummyElmModel, load_golden_cases


EVENT_SAMPLES = 512
SAMPLE_RATE_HZ = 25_600
CAPTURE_PATH = Path("data/captures/events.jsonl")
INFERENCE_PATH = Path("data/inference/dummy_results.jsonl")
MODEL_PATH = Path(__file__).with_name("model.npz")
GOLDEN_PATH = Path(__file__).with_name("golden_outputs.json")

logger = Logger("acrylic-pan")
lock = threading.Lock()
pending: dict[int, dict] = {}
model = DummyElmModel.load(MODEL_PATH)
golden_cases = load_golden_cases(GOLDEN_PATH, model.output_count)


def on_runtime_status(mode: str, sensor_ready: bool) -> None:
    logger.info(f"Runtime mode={mode}, sensor_ready={sensor_ready}")


def on_sensor_status(ready: bool, who_am_i: int) -> None:
    if ready:
        logger.info(f"KX134 ready (WHO_AM_I=0x{who_am_i:02X})")
    else:
        logger.error(f"KX134 not found (WHO_AM_I=0x{who_am_i:02X})")


def on_dummy_case(case_id: int) -> None:
    case = golden_cases[case_id % len(golden_cases)]
    started = time.perf_counter_ns()
    predicted, scores = model.predict(case["input"])
    elapsed_us = (time.perf_counter_ns() - started) // 1000
    expected = int(case["expected_class"])
    result = {
        "case_id": case_id,
        "expected_class": expected,
        "predicted_class": predicted,
        "passed": predicted == expected,
        "scores": scores,
        "inference_us": elapsed_us,
        "created_at_unix_ns": time.time_ns(),
        "model": "acrylic_pan_time128_h32_12class_v1",
        "source": "dummy_golden_case",
    }
    INFERENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with INFERENCE_PATH.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n")
    logger.info(
        f"DUMMY case={case_id} expected={expected} predicted={predicted} "
        f"pass={result['passed']} inference_us={elapsed_us}"
    )


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

        event["captured_at_unix_ns"] = time.time_ns()
        CAPTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with CAPTURE_PATH.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")
        pending.pop(sequence, None)
        logger.info(
            f"Saved event {sequence}: {EVENT_SAMPLES} samples, peak={peak_abs}, "
            f"path={CAPTURE_PATH}"
        )


Bridge.provide("on_sensor_status", on_sensor_status)
Bridge.provide("on_runtime_status", on_runtime_status)
Bridge.provide("on_capture_chunk", on_capture_chunk)
Bridge.provide("on_dummy_case", on_dummy_case)

App.run()
