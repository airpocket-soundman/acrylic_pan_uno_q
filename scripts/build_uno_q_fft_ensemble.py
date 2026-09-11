"""Fuse the temporal CNN and embedded-FFT model using validation-selected weights."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import tensorflow as tf

sys.path.insert(0, str(Path(__file__).resolve().parent))

import train_uno_q_cpu_gpu_models as base
import train_uno_q_fft_hybrid_models as hybrid


def probabilities(model: tf.keras.Model, values: np.ndarray) -> np.ndarray:
    prediction = model.predict(values, batch_size=256, verbose=0)
    return next(value for value in prediction if value.shape[1] == 60)


def choose_temporal_weight(temporal: np.ndarray, fft: np.ndarray,
                           labels: np.ndarray) -> tuple[float, list[dict]]:
    candidates = []
    for weight in np.linspace(0.0, 1.0, 21):
        combined = weight * temporal + (1.0 - weight) * fft
        accuracy = float(np.mean(np.argmax(combined, axis=1) == labels))
        nll = float(-np.mean(np.log(np.clip(
            combined[np.arange(len(labels)), labels], 1e-9, 1.0
        ))))
        candidates.append({"temporal_weight": float(weight), "accuracy": accuracy, "nll": nll})
    selected = max(candidates, key=lambda row: (row["accuracy"], -row["nll"]))
    return selected["temporal_weight"], candidates


def ensemble_model(temporal: tf.keras.Model, fft: tf.keras.Model,
                   temporal_weight: float) -> tf.keras.Model:
    temporal.trainable = False
    fft.trainable = False
    raw = tf.keras.Input((base.SAMPLES,), name="waveform_512")
    time_features, _, _ = hybrid.EmbeddedTimeFftFeatures(name="temporal_preprocessing")(raw)
    time_input = tf.keras.layers.Reshape((base.SAMPLES - base.TRIGGER, 1, 3))(time_features)
    temporal_probability, temporal_xy = temporal(time_input, training=False)
    fft_probability, fft_xy = fft(raw, training=False)
    fft_weight = 1.0 - temporal_weight
    probability = tf.keras.layers.Lambda(
        lambda values: temporal_weight * values[0] + fft_weight * values[1],
        name="position_probability",
    )((temporal_probability, fft_probability))
    direct_xy = tf.keras.layers.Lambda(
        lambda values: temporal_weight * values[0] + fft_weight * values[1],
        name="direct_xy_normalized",
    )((temporal_xy, fft_xy))
    return tf.keras.Model(raw, (probability, direct_xy), name="acrylic_pan_temporal_fft_ensemble")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sessions", type=Path,
                        default=Path(r"D:\GitHub\acrylic_pan\data\raw\sessions"))
    parser.add_argument("--temporal-model", type=Path,
                        default=Path("uno_q_model_candidates/acrylic_pan_xy_gpu.keras"))
    parser.add_argument("--fft-model", type=Path,
                        default=Path("uno_q_fft_candidates/acrylic_pan_fft_hybrid_standard.keras"))
    parser.add_argument("--output", type=Path,
                        default=Path("uno_q_fft_candidates/acrylic_pan_temporal_fft_ensemble_fp16.tflite"))
    parser.add_argument("--keras-output", type=Path,
                        default=Path("uno_q_fft_candidates/acrylic_pan_temporal_fft_ensemble.keras"))
    parser.add_argument("--report", type=Path,
                        default=Path("uno_q_fft_candidates/evaluation_report.json"))
    args = parser.parse_args()

    data = base.load_dataset(args.sessions)
    waves = np.asarray(data["waves"], dtype=np.float32)
    xy = np.asarray(data["xy"], dtype=np.float32)
    sessions = np.asarray(data["sessions"])
    support, labels = base.support_and_labels(xy)
    validation = np.isin(sessions, base.VALIDATION_SESSIONS)
    test = np.isin(sessions, base.TEST_SESSIONS)

    temporal = tf.keras.models.load_model(args.temporal_model)
    fft = tf.keras.models.load_model(args.fft_model)
    temporal_validation = probabilities(temporal, base.gpu_features(waves[validation]))
    fft_validation = probabilities(fft, waves[validation])
    weight, candidates = choose_temporal_weight(
        temporal_validation, fft_validation, labels[validation]
    )
    model = ensemble_model(temporal, fft, weight)
    model.save(args.keras_output)
    hybrid.save_tflite(model, args.output, fp16=True)

    probability, direct_xy = hybrid.tflite_outputs(args.output, waves[test])
    result = {
        "architecture": "validation-weighted temporal CNN + embedded-FFT hybrid",
        "parameters": int(model.count_params()),
        "temporal_weight": weight,
        "fft_weight": 1.0 - weight,
        "weight_selection": {
            "split": list(base.VALIDATION_SESSIONS),
            "criterion": "highest validation top-1, then lowest validation NLL",
            "candidates": candidates,
        },
        "artifact": hybrid.describe(args.output),
        "test": base.metrics(probability, direct_xy, xy[test], labels[test], support),
    }
    report = json.loads(args.report.read_text(encoding="utf-8"))
    report["ensemble"] = result
    report["selected"] = args.output.name
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
