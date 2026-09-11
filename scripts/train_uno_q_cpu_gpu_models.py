"""Train session-separated CPU and GPU TFLite models for Acrylic Pan UNO Q."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import subprocess
from pathlib import Path

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

import numpy as np
import tensorflow as tf


SAMPLE_RATE_HZ = 25_600
SOURCE_SAMPLES = 2_048
SAMPLES = 512
TRIGGER = 64
PANEL_SIZE = np.asarray([400.0, 300.0], dtype=np.float32)
TRAIN_SESSIONS = (
    "20260720_215533_aa9943ae", "20260720_220935_bd12a70b",
    "20260821_215225_8f38a3e4", "20260821_221547_4c753402",
    "20260823_081435_223491a5", "20260823_082825_9374f169",
    "20260823_083716_e0336d95", "20260823_084554_6d26bd22",
    "20260823_102330_ae4338bd",
)
VALIDATION_SESSIONS = ("20260823_103846_18384ce0",)
TEST_SESSIONS = ("20260823_104754_2553f5d8",)
ALL_SESSIONS = (*TRAIN_SESSIONS, *VALIDATION_SESSIONS, *TEST_SESSIONS)


def _scalar(archive: np.lib.npyio.NpzFile, name: str) -> int:
    value = np.asarray(archive[name])
    if value.size != 1:
        raise ValueError(f"{name} is not scalar")
    return int(value.reshape(-1)[0])


def load_dataset(root: Path) -> dict[str, np.ndarray | str | list[dict]]:
    waves, coordinates, sessions, event_ids, manifest = [], [], [], [], []
    digest = hashlib.sha256()
    for session_id in ALL_SESSIONS:
        directory = root / session_id
        metadata_path = directory / "session.json"
        rows_path = directory / "manifest.jsonl"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        rows = [json.loads(line) for line in rows_path.read_text(encoding="utf-8").splitlines() if line]
        if metadata.get("format") != "acrylic-pan-session-v1":
            raise ValueError(f"{session_id}: unexpected format")
        if metadata.get("user_metadata", {}).get("panel_profile_id") != "400x300x5":
            raise ValueError(f"{session_id}: unexpected panel")
        if metadata.get("event_count") != len(rows):
            raise ValueError(f"{session_id}: manifest count mismatch")
        digest.update(metadata_path.read_bytes())
        digest.update(rows_path.read_bytes())
        session_count = 0
        for row in rows:
            annotation = row.get("annotations") or {}
            path = directory / row["file"]
            with np.load(path, allow_pickle=False) as event:
                samples = np.asarray(event["samples"], dtype=np.int16)
                if samples.shape != (SOURCE_SAMPLES,):
                    raise ValueError(f"{path}: expected {SOURCE_SAMPLES} samples")
                if _scalar(event, "sample_rate_hz") != SAMPLE_RATE_HZ:
                    raise ValueError(f"{path}: unexpected sample rate")
                if _scalar(event, "trigger_index") != TRIGGER:
                    raise ValueError(f"{path}: unexpected trigger")
            xy = (float(annotation["target_x_mm"]), float(annotation["target_y_mm"]))
            if not (0 <= xy[0] <= 400 and 0 <= xy[1] <= 300):
                raise ValueError(f"{path}: coordinate outside panel")
            digest.update(samples.tobytes())
            waves.append(samples[:SAMPLES])
            coordinates.append(xy)
            sessions.append(session_id)
            event_ids.append(f"{session_id}:{int(row['index'])}")
            session_count += 1
        manifest.append({"session_id": session_id, "event_count": session_count})
    return {
        "waves": np.asarray(waves, dtype=np.float32),
        "xy": np.asarray(coordinates, dtype=np.float32),
        "sessions": np.asarray(sessions),
        "event_ids": np.asarray(event_ids),
        "dataset_sha256": digest.hexdigest(),
        "session_manifest": manifest,
    }


def support_and_labels(xy: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    support = np.unique(xy, axis=0)
    if support.shape != (60, 2):
        raise ValueError(f"expected 60 coordinates, got {support.shape}")
    lookup = {tuple(point): index for index, point in enumerate(support.tolist())}
    return support, np.asarray([lookup[tuple(point)] for point in xy.tolist()], dtype=np.int32)


def rich_features(waves: np.ndarray) -> np.ndarray:
    baseline = waves[:, :TRIGGER].mean(axis=1, keepdims=True)
    centered = waves - baseline
    post = centered[:, TRIGGER:]
    peak = np.maximum(np.max(np.abs(post), axis=1, keepdims=True), 1.0)
    rms = np.maximum(np.sqrt(np.mean(post**2, axis=1, keepdims=True)), 1.0)
    time_part = post / peak
    spectrum = np.abs(np.fft.rfft(centered * np.hanning(SAMPLES), axis=1))[:, 1:]
    spectrum = np.log1p(spectrum / peak)
    absolute = np.abs(post)
    energy = absolute**2
    quarters = np.stack([part.sum(axis=1) for part in np.split(energy, 4, axis=1)], axis=1)
    quarters /= np.maximum(energy.sum(axis=1, keepdims=True), 1.0)
    scalars = np.column_stack((
        np.log1p(peak[:, 0]), np.log1p(rms[:, 0]), peak[:, 0] / rms[:, 0],
        np.argmax(absolute, axis=1) / (post.shape[1] - 1),
        np.max(post, axis=1) / peak[:, 0], -np.min(post, axis=1) / peak[:, 0], quarters,
    ))
    result = np.concatenate((time_part, spectrum, scalars), axis=1).astype(np.float32)
    if result.shape[1] != 714 or not np.isfinite(result).all():
        raise RuntimeError("714-feature extraction failed")
    return result


def gpu_features(waves: np.ndarray) -> np.ndarray:
    baseline = waves[:, :TRIGGER].mean(axis=1, keepdims=True)
    centered = waves[:, TRIGGER:] - baseline
    peak = np.maximum(np.max(np.abs(centered), axis=1, keepdims=True), 1.0)
    rms = np.maximum(np.sqrt(np.mean(centered**2, axis=1, keepdims=True)), 1.0)
    normalized = centered / peak
    log_peak = np.broadcast_to(np.log1p(peak) / 12.0, normalized.shape)
    log_rms = np.broadcast_to(np.log1p(rms) / 12.0, normalized.shape)
    return np.stack((normalized, log_peak, log_rms), axis=-1)[:, :, None, :].astype(np.float32)


def balanced_indices(labels: np.ndarray, selected: np.ndarray, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    groups = [np.flatnonzero(selected & (labels == value)) for value in range(60)]
    if any(not len(group) for group in groups):
        raise ValueError("training split does not contain all 60 positions")
    target = max(map(len, groups))
    result = np.concatenate([rng.choice(group, target, replace=len(group) < target) for group in groups])
    rng.shuffle(result)
    return result


def heads(features: tf.Tensor) -> tuple[tf.Tensor, tf.Tensor]:
    density = tf.keras.layers.Dense(60, activation="softmax", name="position_probability")(features)
    xy = tf.keras.layers.Dense(2, activation="sigmoid", name="direct_xy_normalized")(features)
    return density, xy


def cpu_model(mean: np.ndarray, variance: np.ndarray) -> tf.keras.Model:
    inputs = tf.keras.Input((714,), name="features_714")
    norm = tf.keras.layers.Normalization(mean=mean, variance=variance, name="feature_normalization")(inputs)
    x = tf.keras.layers.Dense(192, activation="relu")(norm)
    x = tf.keras.layers.Dense(96, activation="relu")(x)
    x = tf.keras.layers.Dense(64, activation="relu")(x)
    return tf.keras.Model(inputs, heads(x), name="acrylic_pan_cpu_mlp")


def gpu_model() -> tf.keras.Model:
    inputs = tf.keras.Input((448, 1, 3), name="waveform_448x3")
    x = inputs
    for filters, kernel, stride in ((32, 11, 2), (64, 9, 2), (96, 7, 2), (128, 5, 2)):
        x = tf.keras.layers.Conv2D(filters, (kernel, 1), strides=(stride, 1),
                                   padding="same", activation="relu")(x)
    # Preserve temporal position. Global-average pooling made the first
    # candidate too invariant and reduced held-out-session accuracy.
    x = tf.keras.layers.Reshape((28 * 128,))(x)
    x = tf.keras.layers.Dense(256, activation="relu")(x)
    x = tf.keras.layers.Dense(128, activation="relu")(x)
    return tf.keras.Model(inputs, heads(x), name="acrylic_pan_gpu_conv2d")


def compile_and_fit(model: tf.keras.Model, x: np.ndarray, xy: np.ndarray, labels: np.ndarray,
                    train_indices: np.ndarray, validation: np.ndarray, epochs: int) -> dict:
    model.compile(
        optimizer=tf.keras.optimizers.Adam(8e-4),
        loss={"position_probability": "sparse_categorical_crossentropy",
              "direct_xy_normalized": "mse"},
        loss_weights={"position_probability": 1.0, "direct_xy_normalized": 2.0},
        metrics={"position_probability": ["sparse_categorical_accuracy"],
                 "direct_xy_normalized": ["mae"]},
    )
    callback = tf.keras.callbacks.EarlyStopping(
        monitor="val_position_probability_sparse_categorical_accuracy",
        mode="max", patience=15, restore_best_weights=True,
    )
    history = model.fit(
        x[train_indices], {"position_probability": labels[train_indices],
                           "direct_xy_normalized": xy[train_indices] / PANEL_SIZE},
        validation_data=(x[validation], {"position_probability": labels[validation],
                                         "direct_xy_normalized": xy[validation] / PANEL_SIZE}),
        epochs=epochs, batch_size=128, verbose=2, callbacks=[callback], shuffle=True,
    )
    return {"epochs": len(history.history["loss"]),
            "best_validation_probability_accuracy": float(max(
                history.history["val_position_probability_sparse_categorical_accuracy"]
            ))}


def outputs(model: tf.keras.Model, x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    prediction = model.predict(x, batch_size=256, verbose=0)
    by_size = {value.shape[1]: value for value in prediction}
    return by_size[60], by_size[2] * PANEL_SIZE


def area_ids(xy: np.ndarray) -> np.ndarray:
    column = np.clip((xy[:, 0] // 100).astype(int), 0, 3)
    row = np.clip((xy[:, 1] // 100).astype(int), 0, 2)
    return row * 4 + column


def metrics(probability: np.ndarray, direct_xy: np.ndarray, target_xy: np.ndarray,
            labels: np.ndarray, support: np.ndarray) -> dict:
    map_xy = support[np.argmax(probability, axis=1)]
    expected_xy = probability @ support
    direct_distance = np.linalg.norm(direct_xy - target_xy, axis=1)
    expected_distance = np.linalg.norm(expected_xy - target_xy, axis=1)
    map_distance = np.linalg.norm(map_xy - target_xy, axis=1)
    area_probability = np.zeros((len(probability), 12), dtype=np.float32)
    support_areas = area_ids(support)
    for position, area in enumerate(support_areas):
        area_probability[:, area] += probability[:, position]
    true_area = area_ids(target_xy)
    confidence = probability.max(axis=1)
    correct = np.argmax(probability, axis=1) == labels
    ece = 0.0
    for lower in np.linspace(0, .9, 10):
        chosen = (confidence >= lower) & (confidence < lower + .1)
        if chosen.any():
            ece += chosen.mean() * abs(confidence[chosen].mean() - correct[chosen].mean())
    return {
        "sample_count": int(len(labels)),
        "position_top1_accuracy": float(correct.mean()),
        "area_accuracy_12class": float((np.argmax(area_probability, axis=1) == true_area).mean()),
        "nll": float(-np.mean(np.log(np.clip(probability[np.arange(len(labels)), labels], 1e-9, 1)))),
        "brier_score": float(np.mean(np.sum((probability - np.eye(60)[labels])**2, axis=1))),
        "ece": float(ece),
        "direct_xy_mean_mm": float(direct_distance.mean()),
        "direct_xy_median_mm": float(np.median(direct_distance)),
        "direct_xy_p90_mm": float(np.percentile(direct_distance, 90)),
        "direct_xy_p95_mm": float(np.percentile(direct_distance, 95)),
        "expected_xy_mean_mm": float(expected_distance.mean()),
        "map_xy_mean_mm": float(map_distance.mean()),
    }


def save_tflite(model: tf.keras.Model, path: Path, optimization: str,
                representative: np.ndarray | None = None) -> bytes:
    input_shape = [1, *model.input_shape[1:]]

    @tf.function(input_signature=[tf.TensorSpec(input_shape, tf.float32, name=model.input.name)])
    def fixed_batch_inference(value):
        return model(value, training=False)

    # A fixed batch-one frozen graph avoids dynamic SHAPE/SLICE/PACK operators
    # around the GPU model's reshape, reducing delegate partitioning risk.
    converter = tf.lite.TFLiteConverter.from_concrete_functions(
        [fixed_batch_inference.get_concrete_function()]
    )
    if optimization in {"dynamic", "int8", "fp16"}:
        converter.optimizations = [tf.lite.Optimize.DEFAULT]
    if optimization == "fp16":
        converter.target_spec.supported_types = [tf.float16]
    elif optimization == "int8":
        assert representative is not None
        converter.representative_dataset = lambda: ([row[None].astype(np.float32)] for row in representative)
        converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
        converter.inference_input_type = tf.int8
        converter.inference_output_type = tf.int8
    content = converter.convert()
    path.write_bytes(content)
    return content


def tflite_outputs(path: Path, x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    interpreter = tf.lite.Interpreter(model_path=str(path), num_threads=4)
    interpreter.allocate_tensors()
    input_info = interpreter.get_input_details()[0]
    output_info = interpreter.get_output_details()
    result = {2: [], 60: []}
    scale, zero = input_info["quantization"]
    for row in x:
        value = row[None]
        if input_info["dtype"] == np.int8:
            value = np.clip(np.rint(value / scale + zero), -128, 127).astype(np.int8)
        interpreter.set_tensor(input_info["index"], value.astype(input_info["dtype"]))
        interpreter.invoke()
        for info in output_info:
            value = interpreter.get_tensor(info["index"])
            out_scale, out_zero = info["quantization"]
            if info["dtype"] == np.int8:
                value = (value.astype(np.float32) - out_zero) * out_scale
            result[value.shape[1]].append(value[0])
    return np.asarray(result[60]), np.asarray(result[2]) * PANEL_SIZE


def describe_tflite(path: Path) -> dict:
    interpreter = tf.lite.Interpreter(model_path=str(path), num_threads=4)
    interpreter.allocate_tensors()
    detail = interpreter.get_input_details()[0]
    return {
        "file": path.name, "bytes": path.stat().st_size,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "input": {"name": detail["name"], "shape": detail["shape"].tolist(),
                  "dtype": detail["dtype"].__name__},
        "outputs": [{"name": item["name"], "shape": item["shape"].tolist(),
                     "dtype": item["dtype"].__name__}
                    for item in interpreter.get_output_details()],
        "operators": [item["op_name"] for item in interpreter._get_ops_details()
                      if item["op_name"] != "DELEGATE"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sessions", type=Path, default=Path(r"D:\GitHub\acrylic_pan\data\raw\sessions"))
    parser.add_argument("--output", type=Path, default=Path("uno_q_model_candidates"))
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--seed", type=int, default=20260911)
    args = parser.parse_args()
    random.seed(args.seed); np.random.seed(args.seed); tf.random.set_seed(args.seed)
    data = load_dataset(args.sessions)
    waves, xy, sessions = data["waves"], data["xy"], data["sessions"]
    support, labels = support_and_labels(xy)
    train = np.isin(sessions, TRAIN_SESSIONS)
    validation = np.isin(sessions, VALIDATION_SESSIONS)
    test = np.isin(sessions, TEST_SESSIONS)
    train_indices = balanced_indices(labels, train, args.seed)
    cpu_x, gpu_x = rich_features(waves), gpu_features(waves)
    args.output.mkdir(parents=True, exist_ok=True)

    cpu = cpu_model(cpu_x[train].mean(axis=0), cpu_x[train].var(axis=0) + 1e-6)
    cpu_history = compile_and_fit(cpu, cpu_x, xy, labels, train_indices, validation, args.epochs)
    cpu_probability, cpu_xy = outputs(cpu, cpu_x[test])
    cpu_metrics = metrics(cpu_probability, cpu_xy, xy[test], labels[test], support)
    cpu.save(args.output / "acrylic_pan_xy_cpu.keras")
    save_tflite(cpu, args.output / "acrylic_pan_xy_cpu_fp32.tflite", "fp32")
    save_tflite(cpu, args.output / "acrylic_pan_xy_cpu_dynamic.tflite", "dynamic")
    representative_cpu = cpu_x[train_indices[:512]]
    save_tflite(cpu, args.output / "acrylic_pan_xy_cpu_int8.tflite", "int8", representative_cpu)

    gpu = gpu_model()
    gpu_history = compile_and_fit(gpu, gpu_x, xy, labels, train_indices, validation, args.epochs)
    gpu_probability, gpu_xy = outputs(gpu, gpu_x[test])
    gpu_metrics = metrics(gpu_probability, gpu_xy, xy[test], labels[test], support)
    gpu.save(args.output / "acrylic_pan_xy_gpu.keras")
    save_tflite(gpu, args.output / "acrylic_pan_xy_gpu_fp32.tflite", "fp32")
    save_tflite(gpu, args.output / "acrylic_pan_xy_gpu_fp16.tflite", "fp16")

    variant_metrics = {}
    for name, model_path, values in (
        ("cpu_fp32", args.output / "acrylic_pan_xy_cpu_fp32.tflite", cpu_x[test]),
        ("cpu_dynamic", args.output / "acrylic_pan_xy_cpu_dynamic.tflite", cpu_x[test]),
        ("cpu_int8", args.output / "acrylic_pan_xy_cpu_int8.tflite", cpu_x[test]),
        ("gpu_fp32", args.output / "acrylic_pan_xy_gpu_fp32.tflite", gpu_x[test]),
        ("gpu_fp16", args.output / "acrylic_pan_xy_gpu_fp16.tflite", gpu_x[test]),
    ):
        variant_probability, variant_xy = tflite_outputs(model_path, values)
        variant_metrics[name] = metrics(
            variant_probability, variant_xy, xy[test], labels[test], support
        )

    parity_indices = np.concatenate([
        np.flatnonzero(test & (labels == position))[:2] for position in range(60)
    ])
    np.savez_compressed(args.output / "parity_cases.npz", waveform=waves[parity_indices],
                        features_714=cpu_x[parity_indices], waveform_448x3=gpu_x[parity_indices],
                        target_xy_mm=xy[parity_indices], labels=labels[parity_indices],
                        support_xy_mm=support, event_ids=data["event_ids"][parity_indices])
    parity = {}
    for name, model_path, values, reference_p, reference_xy in (
        ("cpu_fp32", args.output / "acrylic_pan_xy_cpu_fp32.tflite", cpu_x[parity_indices],
         outputs(cpu, cpu_x[parity_indices])[0], outputs(cpu, cpu_x[parity_indices])[1]),
        ("cpu_dynamic", args.output / "acrylic_pan_xy_cpu_dynamic.tflite", cpu_x[parity_indices],
         outputs(cpu, cpu_x[parity_indices])[0], outputs(cpu, cpu_x[parity_indices])[1]),
        ("cpu_int8", args.output / "acrylic_pan_xy_cpu_int8.tflite", cpu_x[parity_indices],
         outputs(cpu, cpu_x[parity_indices])[0], outputs(cpu, cpu_x[parity_indices])[1]),
        ("gpu_fp32", args.output / "acrylic_pan_xy_gpu_fp32.tflite", gpu_x[parity_indices],
         outputs(gpu, gpu_x[parity_indices])[0], outputs(gpu, gpu_x[parity_indices])[1]),
        ("gpu_fp16", args.output / "acrylic_pan_xy_gpu_fp16.tflite", gpu_x[parity_indices],
         outputs(gpu, gpu_x[parity_indices])[0], outputs(gpu, gpu_x[parity_indices])[1]),
    ):
        tflite_p, tflite_xy = tflite_outputs(model_path, values)
        parity[name] = {"probability_max_abs_delta": float(np.max(np.abs(tflite_p-reference_p))),
                        "direct_xy_max_delta_mm": float(np.max(np.linalg.norm(tflite_xy-reference_xy, axis=1)))}

    split_manifest = {
        "strategy": "whole_session_split_no_event_leakage", "train": list(TRAIN_SESSIONS),
        "validation": list(VALIDATION_SESSIONS), "test": list(TEST_SESSIONS),
        "counts": {"train": int(train.sum()), "validation": int(validation.sum()), "test": int(test.sum())},
    }
    report = {
        "created_by": "scripts/train_uno_q_cpu_gpu_models.py", "seed": args.seed,
        "tensorflow_version": tf.__version__,
        "git_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, encoding="utf-8"
        ).strip(),
        "dataset_sha256": data["dataset_sha256"], "event_count": int(len(waves)),
        "session_manifest": data["session_manifest"], "split": split_manifest,
        "contract": {"sensor": "KX134-1211", "sample_rate_hz": SAMPLE_RATE_HZ,
                     "source_samples": SOURCE_SAMPLES, "live_samples": SAMPLES,
                     "trigger_index": TRIGGER, "panel_mm": [400, 300], "position_count": 60},
        "cpu": {"input": [1, 714], "architecture": [192, 96, 64],
                "training": cpu_history, "test": cpu_metrics},
        "gpu": {"input": [1, 448, 1, 3],
                "architecture": "Conv2D 32/64/96/128 + Flatten + Dense256/128",
                "training": gpu_history, "test": gpu_metrics},
        "tflite_test": variant_metrics,
        "tflite_parity": parity,
    }
    (args.output / "dataset_manifest.json").write_text(json.dumps({
        "dataset_sha256": data["dataset_sha256"], "sessions": data["session_manifest"]
    }, indent=2) + "\n", encoding="utf-8")
    (args.output / "split_manifest.json").write_text(json.dumps(split_manifest, indent=2) + "\n", encoding="utf-8")
    (args.output / "support_xy_mm.json").write_text(json.dumps(support.tolist(), indent=2) + "\n", encoding="utf-8")
    (args.output / "evaluation_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    feature_contract = {
        "common": report["contract"],
        "cpu": {"input": "714 float32 features", "preprocessing":
                "64-sample baseline; normalized 448-point time waveform; 256-bin log spectrum; 10 scalars"},
        "gpu": {"input": "[1,448,1,3] float32", "channels":
                ["post-trigger waveform / absolute peak", "log1p(peak)/12", "log1p(rms)/12"]},
        "outputs": {"60": "normalized position probability", "2": "direct XY normalized to panel size"},
    }
    (args.output / "feature_contract.json").write_text(
        json.dumps(feature_contract, indent=2) + "\n", encoding="utf-8"
    )
    cpu_metadata = {
        "selected": "acrylic_pan_xy_cpu_dynamic.tflite",
        "reason": "same held-out accuracy as FP32 at 27% of its size",
        "models": {name: describe_tflite(args.output / file) for name, file in {
            "fp32": "acrylic_pan_xy_cpu_fp32.tflite",
            "dynamic": "acrylic_pan_xy_cpu_dynamic.tflite",
            "int8_rejected": "acrylic_pan_xy_cpu_int8.tflite",
        }.items()}, "test": variant_metrics,
    }
    gpu_metadata = {
        "selected": "acrylic_pan_xy_gpu_fp16.tflite",
        "reason": "FP32-equivalent held-out accuracy with half-size weights",
        "models": {name: describe_tflite(args.output / file) for name, file in {
            "fp32": "acrylic_pan_xy_gpu_fp32.tflite", "fp16": "acrylic_pan_xy_gpu_fp16.tflite",
        }.items()}, "test": {name: variant_metrics[name] for name in ("gpu_fp32", "gpu_fp16")},
        "delegate_status": "requires verification on UNO Q; PC conversion does not prove OpenCL delegation",
    }
    (args.output / "cpu_model_metadata.json").write_text(json.dumps(cpu_metadata, indent=2) + "\n", encoding="utf-8")
    (args.output / "gpu_model_metadata.json").write_text(json.dumps(gpu_metadata, indent=2) + "\n", encoding="utf-8")
    rows = "".join(
        f"<tr><td>{name}</td><td>{value['position_top1_accuracy']:.2%}</td>"
        f"<td>{value['area_accuracy_12class']:.2%}</td><td>{value['map_xy_mean_mm']:.2f}</td>"
        f"<td>{value['direct_xy_mean_mm']:.2f}</td></tr>"
        for name, value in variant_metrics.items()
    )
    (args.output / "evaluation_report.html").write_text(
        "<!doctype html><meta charset=utf-8><title>UNO Q model evaluation</title>"
        "<h1>UNO Q CPU/GPU model evaluation</h1>"
        "<p>Whole-session held-out test: 1,907 events. GPU delegate execution remains to be verified on UNO Q.</p>"
        "<table border=1><tr><th>Model</th><th>60-position</th><th>12-area</th>"
        "<th>MAP mean mm</th><th>Direct XY mean mm</th></tr>" + rows + "</table>",
        encoding="utf-8",
    )
    (args.output / "README.md").write_text(
        "# UNO Q CPU/GPU model candidates\n\n"
        "Generated with `scripts/train_uno_q_cpu_gpu_models.py`. The selected CPU candidate is "
        "`acrylic_pan_xy_cpu_dynamic.tflite`; the selected GPU candidate is "
        "`acrylic_pan_xy_gpu_fp16.tflite`. INT8 is retained for diagnosis but rejected because its "
        "held-out accuracy and parity are worse. GPU delegate execution and latency must be verified "
        "on the UNO Q before deployment. See `evaluation_report.json` for all metrics.\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
