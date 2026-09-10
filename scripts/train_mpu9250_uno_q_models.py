"""Convert the measured KX134 sessions and train the portable UNO Q MPU9250 suite."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
from sklearn.neural_network import MLPRegressor


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "uno_q_app" / "python"))

from mpu9250_models import add_xy_mlp, evaluate_arrays, extract_features, save_model, train_arrays  # noqa: E402


XY_HIDDEN_LAYERS = (384, 192, 96)


def train_xy_mlp(arrays: dict[str, np.ndarray], features: np.ndarray,
                 xy_mm: np.ndarray, *, seed: int = 1) -> tuple[dict[str, np.ndarray], int]:
    normalized = ((features - arrays["feature_mean"]) / arrays["feature_scale"])
    model = MLPRegressor(
        hidden_layer_sizes=XY_HIDDEN_LAYERS, activation="relu", solver="adam",
        alpha=1e-3, batch_size=128, learning_rate_init=1e-3, max_iter=350,
        early_stopping=True, validation_fraction=0.15, n_iter_no_change=20,
        random_state=seed,
    )
    model.fit(normalized, xy_mm / arrays["panel_size_mm"])
    add_xy_mlp(arrays, model.coefs_, model.intercepts_)
    return arrays, int(model.n_iter_)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-repo", type=Path, default=ROOT.parent / "acrylic_pan")
    parser.add_argument("--output", type=Path, default=ROOT / "uno_q_app" / "python")
    args = parser.parse_args()
    source = args.source_repo.resolve()
    sys.path.insert(0, str(source))
    from sim.mpu9250_position_experiment import convert_to_mpu9250, load_source_waveforms
    from sim.pc_position_grid_runtime import load_position_dataset

    sessions = source / "data" / "raw" / "sessions"
    dataset = load_position_dataset(sessions)
    source_waveforms = load_source_waveforms(sessions)
    converted, clipping = convert_to_mpu9250(source_waveforms)
    waveforms = converted[:, :80]
    features = np.stack([extract_features(row) for row in waveforms])
    holdout = dataset.repetitions % 5 == 0
    support = np.unique(dataset.xy_mm, axis=0)

    validation_arrays = train_arrays(features[~holdout], dataset.labels[~holdout],
                                     dataset.xy_mm[~holdout], support)
    validation_arrays, validation_xy_iterations = train_xy_mlp(
        validation_arrays, features[~holdout], dataset.xy_mm[~holdout])
    validation = evaluate_arrays(validation_arrays, features[holdout],
                                 dataset.labels[holdout], dataset.xy_mm[holdout])
    final_arrays = train_arrays(features, dataset.labels, dataset.xy_mm, support)
    final_arrays, final_xy_iterations = train_xy_mlp(final_arrays, features, dataset.xy_mm)
    training = evaluate_arrays(final_arrays, features, dataset.labels, dataset.xy_mm)

    args.output.mkdir(parents=True, exist_ok=True)
    model_path = args.output / "mpu9250_models.npz"
    seed_path = args.output / "mpu9250_training_seed.npz"
    save_model(model_path, final_arrays)
    np.savez_compressed(seed_path, features=features.astype(np.float32),
                        labels=dataset.labels.astype(np.uint8),
                        xy_mm=dataset.xy_mm.astype(np.float32),
                        support_xy_mm=support.astype(np.float32),
                        waveforms=waveforms.astype(np.int16))
    report = {
        "model": "acrylic_pan_mpu9250_unified_400x300_v2",
        "created_from": "measured KX134 sessions converted to MPU9250 equivalent",
        "dataset_sha256": dataset.dataset_sha256,
        "event_count": int(len(features)),
        "session_count": int(len(np.unique(dataset.session_ids))),
        "sensor": {"name": "MPU9250", "sample_rate_hz": 4000, "range_g": 16,
                   "bandwidth_hz": 1130, "event_samples": 80, "trigger_index": 10},
        "tasks": ["12class", "60class", "pseudo_xy_from_60class", "direct_xy_regression"],
        "direct_xy_model": {
            "type": "fully-trained relu MLP",
            "architecture": [120, *XY_HIDDEN_LAYERS, 2],
            "trainable_parameter_count": 139106,
            "validation_training_iterations": validation_xy_iterations,
            "full_training_iterations": final_xy_iterations,
        },
        "validation_split": "repetition modulo 5 equals zero",
        "validation": validation,
        "full_training": training,
        "clipping": clipping,
        "model_sha256": hashlib.sha256(model_path.read_bytes()).hexdigest(),
        "training_seed_sha256": hashlib.sha256(seed_path.read_bytes()).hexdigest(),
        "limitations": [
            "Initial data is an offline sensor-domain conversion; fresh MPU9250 recordings are needed for final calibration.",
            "The conversion cannot reproduce package, mounting, cross-axis, clock-jitter, or sensor-noise differences.",
        ],
    }
    (args.output / "mpu9250_model_metadata.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
