"""Train raw-waveform UNO Q models with an embedded FFT feature branch."""

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

from train_uno_q_cpu_gpu_models import (
    PANEL_SIZE,
    SAMPLES,
    TEST_SESSIONS,
    TRAIN_SESSIONS,
    TRIGGER,
    VALIDATION_SESSIONS,
    balanced_indices,
    load_dataset,
    metrics,
    support_and_labels,
)


@tf.keras.utils.register_keras_serializable(package="acrylic_pan")
class EmbeddedTimeFftFeatures(tf.keras.layers.Layer):
    """Extract normalized time and magnitude-spectrum features in the model."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.window = tf.constant(np.hanning(SAMPLES).astype(np.float32))

    def call(self, waveform: tf.Tensor) -> tuple[tf.Tensor, tf.Tensor, tf.Tensor]:
        baseline = tf.reduce_mean(waveform[:, :TRIGGER], axis=1, keepdims=True)
        centered = waveform - baseline
        post = centered[:, TRIGGER:]
        peak = tf.maximum(tf.reduce_max(tf.abs(post), axis=1, keepdims=True), 1.0)
        rms = tf.maximum(tf.sqrt(tf.reduce_mean(tf.square(post), axis=1, keepdims=True)), 1.0)
        normalized = post / peak
        log_peak = tf.math.log1p(peak) / 12.0
        log_rms = tf.math.log1p(rms) / 12.0
        time_features = tf.stack(
            (
                normalized,
                tf.broadcast_to(log_peak, tf.shape(normalized)),
                tf.broadcast_to(log_rms, tf.shape(normalized)),
            ),
            axis=-1,
        )
        magnitude = tf.abs(tf.signal.rfft(centered * self.window))[:, 1:]
        spectrum = tf.math.log1p(magnitude / peak)
        amplitude = tf.concat((log_peak, log_rms, peak / rms), axis=1)
        return time_features, spectrum, amplitude

    def compute_output_shape(self, input_shape):
        return ((input_shape[0], SAMPLES - TRIGGER, 3),
                (input_shape[0], SAMPLES // 2), (input_shape[0], 3))


def hybrid_model(size: str) -> tf.keras.Model:
    if size == "standard":
        conv = ((32, 11, 2), (64, 9, 2), (96, 7, 2), (128, 5, 2))
        fft_dense = (160, 96)
        fused_dense = (384, 192)
    elif size == "large":
        conv = ((48, 13, 2), (96, 11, 2), (160, 9, 2), (224, 7, 2))
        fft_dense = (384, 192)
        fused_dense = (768, 384)
    else:
        raise ValueError(f"unknown model size: {size}")

    raw = tf.keras.Input((SAMPLES,), name="waveform_512")
    time_features, spectrum, amplitude = EmbeddedTimeFftFeatures(name="embedded_time_fft")(raw)

    time = tf.keras.layers.Reshape((SAMPLES - TRIGGER, 1, 3))(time_features)
    for filters, kernel, stride in conv:
        time = tf.keras.layers.Conv2D(
            filters, (kernel, 1), strides=(stride, 1), padding="same", activation="relu"
        )(time)
    time = tf.keras.layers.Flatten()(time)

    frequency = spectrum
    for width in fft_dense:
        frequency = tf.keras.layers.Dense(width, activation="relu")(frequency)

    fused = tf.keras.layers.Concatenate()((time, frequency, amplitude))
    for width in fused_dense:
        fused = tf.keras.layers.Dense(width, activation="relu")(fused)
        fused = tf.keras.layers.Dropout(0.10)(fused)
    probability = tf.keras.layers.Dense(60, activation="softmax", name="position_probability")(fused)
    direct_xy = tf.keras.layers.Dense(2, activation="sigmoid", name="direct_xy_normalized")(fused)
    return tf.keras.Model(raw, (probability, direct_xy), name=f"acrylic_pan_fft_hybrid_{size}")


def compile_and_fit(model: tf.keras.Model, waves: np.ndarray, xy: np.ndarray,
                    labels: np.ndarray, train_indices: np.ndarray,
                    validation: np.ndarray, epochs: int) -> dict:
    model.compile(
        optimizer=tf.keras.optimizers.Adam(6e-4),
        loss={"position_probability": "sparse_categorical_crossentropy",
              "direct_xy_normalized": tf.keras.losses.Huber(delta=0.05)},
        loss_weights={"position_probability": 1.0, "direct_xy_normalized": 2.0},
        metrics={"position_probability": ["sparse_categorical_accuracy"],
                 "direct_xy_normalized": ["mae"]},
    )
    callback = tf.keras.callbacks.EarlyStopping(
        monitor="val_position_probability_sparse_categorical_accuracy",
        mode="max", patience=18, restore_best_weights=True,
    )
    history = model.fit(
        waves[train_indices],
        {"position_probability": labels[train_indices],
         "direct_xy_normalized": xy[train_indices] / PANEL_SIZE},
        validation_data=(waves[validation],
                         {"position_probability": labels[validation],
                          "direct_xy_normalized": xy[validation] / PANEL_SIZE}),
        epochs=epochs, batch_size=128, verbose=2, callbacks=[callback], shuffle=True,
    )
    return {
        "epochs": len(history.history["loss"]),
        "best_validation_probability_accuracy": float(max(
            history.history["val_position_probability_sparse_categorical_accuracy"]
        )),
    }


def keras_outputs(model: tf.keras.Model, waves: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    result = model.predict(waves, batch_size=256, verbose=0)
    by_size = {value.shape[1]: value for value in result}
    return by_size[60], by_size[2] * PANEL_SIZE


def fixed_converter(model: tf.keras.Model) -> tf.lite.TFLiteConverter:
    @tf.function(input_signature=[tf.TensorSpec([1, SAMPLES], tf.float32, name="waveform_512")])
    def infer(value):
        return model(value, training=False)

    return tf.lite.TFLiteConverter.from_concrete_functions([infer.get_concrete_function()])


def save_tflite(model: tf.keras.Model, path: Path, fp16: bool) -> None:
    converter = fixed_converter(model)
    if fp16:
        converter.optimizations = [tf.lite.Optimize.DEFAULT]
        converter.target_spec.supported_types = [tf.float16]
    path.write_bytes(converter.convert())


def tflite_outputs(path: Path, waves: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    interpreter = tf.lite.Interpreter(model_path=str(path), num_threads=4)
    interpreter.allocate_tensors()
    input_info = interpreter.get_input_details()[0]
    output_info = interpreter.get_output_details()
    result = {2: [], 60: []}
    for wave in waves:
        interpreter.set_tensor(input_info["index"], wave[None].astype(np.float32))
        interpreter.invoke()
        for info in output_info:
            value = interpreter.get_tensor(info["index"])[0]
            result[value.shape[0]].append(value)
    return np.asarray(result[60]), np.asarray(result[2]) * PANEL_SIZE


def describe(path: Path) -> dict:
    interpreter = tf.lite.Interpreter(model_path=str(path), num_threads=4)
    interpreter.allocate_tensors()
    return {
        "file": path.name,
        "bytes": path.stat().st_size,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "operators": [op["op_name"] for op in interpreter._get_ops_details()
                      if op["op_name"] != "DELEGATE"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sessions", type=Path,
                        default=Path(os.environ.get("ACRYLIC_PAN_SESSIONS", "data/raw/sessions")))
    parser.add_argument("--output", type=Path, default=Path("uno_q_fft_candidates"))
    parser.add_argument("--epochs", type=int, default=120)
    parser.add_argument("--seed", type=int, default=20260912)
    args = parser.parse_args()
    random.seed(args.seed)
    np.random.seed(args.seed)
    tf.random.set_seed(args.seed)

    data = load_dataset(args.sessions)
    waves = np.asarray(data["waves"], dtype=np.float32)
    xy = np.asarray(data["xy"], dtype=np.float32)
    sessions = np.asarray(data["sessions"])
    support, labels = support_and_labels(xy)
    train = np.isin(sessions, TRAIN_SESSIONS)
    validation = np.isin(sessions, VALIDATION_SESSIONS)
    test = np.isin(sessions, TEST_SESSIONS)
    split_coverage = {
        "train": int(np.unique(labels[train]).size),
        "validation": int(np.unique(labels[validation]).size),
        "test": int(np.unique(labels[test]).size),
    }
    if any(count != 60 for count in split_coverage.values()):
        raise ValueError(f"every split must contain all 60 positions: {split_coverage}")
    train_indices = balanced_indices(labels, train, args.seed)
    args.output.mkdir(parents=True, exist_ok=True)

    report = {
        "created_by": "scripts/train_uno_q_fft_hybrid_models.py",
        "git_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, encoding="utf-8"
        ).strip(),
        "seed": args.seed,
        "dataset_sha256": data["dataset_sha256"],
        "event_count": int(len(waves)),
        "split": {"strategy": "whole_session_split_no_event_leakage",
                  "train": list(TRAIN_SESSIONS), "validation": list(VALIDATION_SESSIONS),
                  "test": list(TEST_SESSIONS),
                  "counts": {"train": int(train.sum()), "validation": int(validation.sum()),
                             "test": int(test.sum())},
                  "position_coverage": split_coverage},
        "evaluation_coverage": "all train, validation, and held-out test splits contain all 60 positions",
        "models": {},
    }

    parity_indices = np.concatenate([
        np.flatnonzero(test & (labels == position))[:2] for position in range(60)
    ])
    np.savez_compressed(args.output / "parity_cases.npz",
                        waveform=waves[parity_indices], target_xy_mm=xy[parity_indices],
                        labels=labels[parity_indices], support_xy_mm=support,
                        event_ids=np.asarray(data["event_ids"])[parity_indices])

    for offset, size in enumerate(("standard", "large")):
        tf.keras.backend.clear_session()
        random.seed(args.seed + offset)
        np.random.seed(args.seed + offset)
        tf.random.set_seed(args.seed + offset)
        model = hybrid_model(size)
        history = compile_and_fit(model, waves, xy, labels, train_indices, validation, args.epochs)
        keras_probability, keras_xy = keras_outputs(model, waves[test])
        keras_metrics = metrics(keras_probability, keras_xy, xy[test], labels[test], support)
        model.save(args.output / f"acrylic_pan_fft_hybrid_{size}.keras")
        fp32 = args.output / f"acrylic_pan_fft_hybrid_{size}_fp32.tflite"
        fp16 = args.output / f"acrylic_pan_fft_hybrid_{size}_fp16.tflite"
        save_tflite(model, fp32, False)
        save_tflite(model, fp16, True)
        variants = {}
        for variant, path in (("fp32", fp32), ("fp16", fp16)):
            probability, direct_xy = tflite_outputs(path, waves[test])
            variant_metrics = metrics(probability, direct_xy, xy[test], labels[test], support)
            parity_probability, parity_xy = tflite_outputs(path, waves[parity_indices])
            reference_probability, reference_xy = keras_outputs(model, waves[parity_indices])
            variants[variant] = {
                "artifact": describe(path),
                "test": variant_metrics,
                "parity": {
                    "probability_max_abs_delta": float(np.max(
                        np.abs(parity_probability - reference_probability)
                    )),
                    "direct_xy_max_delta_mm": float(np.max(
                        np.linalg.norm(parity_xy - reference_xy, axis=1)
                    )),
                },
            }
        report["models"][size] = {
            "architecture": model.name,
            "parameters": int(model.count_params()),
            "training": history,
            "keras_test": keras_metrics,
            "variants": variants,
        }

    ranked = sorted(
        ((details["variants"]["fp16"]["test"]["position_top1_accuracy"],
          -details["variants"]["fp16"]["test"]["map_xy_mean_mm"], size)
         for size, details in report["models"].items()),
        reverse=True,
    )
    report["selected"] = f"acrylic_pan_fft_hybrid_{ranked[0][2]}_fp16.tflite"
    (args.output / "evaluation_report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    (args.output / "README.md").write_text(
        "# UNO Q embedded-FFT hybrid candidates\n\n"
        "These candidates accept one raw 512-sample waveform and perform baseline removal, "
        "normalization, Hann-windowed RFFT, time-domain convolution, and time/frequency fusion "
        "inside the TFLite model. See `evaluation_report.json` for held-out metrics on the "
        "whole-session split covering all 60 positions.\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
