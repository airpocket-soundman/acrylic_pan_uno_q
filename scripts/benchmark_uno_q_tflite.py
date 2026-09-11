from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np

try:
    from ai_edge_litert.interpreter import Interpreter, load_delegate
except ImportError:
    import tensorflow as tf

    Interpreter = tf.lite.Interpreter
    load_delegate = tf.lite.experimental.load_delegate


TRIGGER = 64
PANEL_SIZE = np.asarray((400.0, 300.0), dtype=np.float32)


def cpu_features(wave: np.ndarray) -> np.ndarray:
    baseline = wave[:TRIGGER].mean()
    centered = wave - baseline
    post = centered[TRIGGER:]
    peak = max(float(np.max(np.abs(post))), 1.0)
    rms = max(float(np.sqrt(np.mean(post**2))), 1.0)
    absolute = np.abs(post)
    energy = absolute**2
    quarters = np.asarray([part.sum() for part in np.split(energy, 4)]) / max(float(energy.sum()), 1.0)
    scalars = np.asarray((
        np.log1p(peak), np.log1p(rms), peak / rms,
        np.argmax(absolute) / (post.size - 1), np.max(post) / peak,
        -np.min(post) / peak, *quarters,
    ))
    spectrum = np.log1p(np.abs(np.fft.rfft(centered * np.hanning(512)))[1:] / peak)
    return np.concatenate((post / peak, spectrum, scalars)).astype(np.float32)


def gpu_features(wave: np.ndarray) -> np.ndarray:
    baseline = wave[:TRIGGER].mean()
    post = wave[TRIGGER:] - baseline
    peak = max(float(np.max(np.abs(post))), 1.0)
    rms = max(float(np.sqrt(np.mean(post**2))), 1.0)
    normalized = post / peak
    return np.stack((
        normalized,
        np.full_like(normalized, np.log1p(peak) / 12.0),
        np.full_like(normalized, np.log1p(rms) / 12.0),
    ), axis=-1)[:, None, :].astype(np.float32)


def raw_features(wave: np.ndarray) -> np.ndarray:
    """Pass a raw waveform to models that embed their own preprocessing and FFT."""
    return wave.astype(np.float32)


def percentiles(values: list[float]) -> dict[str, float]:
    data = np.asarray(values)
    return {
        "p50_ms": float(np.percentile(data, 50)),
        "p95_ms": float(np.percentile(data, 95)),
        "max_ms": float(np.max(data)),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--parity", type=Path, required=True)
    parser.add_argument("--variant", choices=("cpu", "gpu", "fft-hybrid"), required=True)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--repeats", type=int, default=10)
    parser.add_argument("--delegate", type=Path)
    args = parser.parse_args()

    parity = np.load(args.parity)
    input_key = {"cpu": "features_714", "gpu": "waveform_448x3",
                 "fft-hybrid": "waveform"}[args.variant]
    make_features = {"cpu": cpu_features, "gpu": gpu_features,
                     "fft-hybrid": raw_features}[args.variant]
    expected_inputs = parity[input_key]
    generated_inputs = np.stack([make_features(row) for row in parity["waveform"]])

    delegates = [load_delegate(str(args.delegate))] if args.delegate else None
    interpreter = Interpreter(model_path=str(args.model), num_threads=args.threads,
                              experimental_delegates=delegates)
    interpreter.allocate_tensors()
    input_detail = interpreter.get_input_details()[0]
    output_details = interpreter.get_output_details()
    operations = interpreter._get_ops_details()

    for row in expected_inputs[:10]:
        interpreter.set_tensor(input_detail["index"], row[None].astype(input_detail["dtype"]))
        interpreter.invoke()

    inference_times: list[float] = []
    preprocessing_times: list[float] = []
    probabilities: list[np.ndarray] = []
    direct_xy: list[np.ndarray] = []
    for repeat in range(args.repeats):
        for index, wave in enumerate(parity["waveform"]):
            started = time.perf_counter_ns()
            value = make_features(wave)
            after_features = time.perf_counter_ns()
            interpreter.set_tensor(input_detail["index"], value[None].astype(input_detail["dtype"]))
            interpreter.invoke()
            finished = time.perf_counter_ns()
            preprocessing_times.append((after_features - started) / 1e6)
            inference_times.append((finished - after_features) / 1e6)
            if repeat == 0:
                by_width = {int(detail["shape"][1]): interpreter.get_tensor(detail["index"])[0]
                            for detail in output_details}
                probabilities.append(by_width[60])
                direct_xy.append(by_width[2] * PANEL_SIZE)

    probability = np.asarray(probabilities)
    direct = np.asarray(direct_xy)
    predicted = np.argmax(probability, axis=1)
    target = parity["target_xy_mm"]
    support = parity["support_xy_mm"]
    map_xy = support[predicted]
    expected_xy = probability @ support
    delegated = [op for op in operations if op["op_name"] == "DELEGATE"]
    report = {
        "model": args.model.name,
        "variant": args.variant,
        "threads": args.threads,
        "requested_delegate": str(args.delegate) if args.delegate else None,
        "cases": int(len(expected_inputs)),
        "repeats": args.repeats,
        "input_reproduction_max_abs_delta": float(np.max(np.abs(generated_inputs - expected_inputs))),
        "position_top1_accuracy": float(np.mean(predicted == parity["labels"])),
        "map_xy_mean_mm": float(np.linalg.norm(map_xy - target, axis=1).mean()),
        "expected_xy_mean_mm": float(np.linalg.norm(expected_xy - target, axis=1).mean()),
        "direct_xy_mean_mm": float(np.linalg.norm(direct - target, axis=1).mean()),
        "preprocessing": percentiles(preprocessing_times),
        "inference": percentiles(inference_times),
        "end_to_end": percentiles(
            [preprocessing_times[i] + inference_times[i] for i in range(len(inference_times))]
        ),
        "operation_count": len(operations),
        "delegate_nodes": len(delegated),
        "operations": [op["op_name"] for op in operations],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
