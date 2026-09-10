"""Train and validate the UNO Q model suite from labeled, real MPU9250 captures."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
from sklearn.neural_network import MLPRegressor


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "uno_q_app" / "python"))

from mpu9250_models import (  # noqa: E402
    FEATURE_COUNT,
    PANEL_SIZE_MM,
    add_xy_mlp,
    evaluate_arrays,
    extract_features,
    save_model,
    train_arrays,
)

XY_HIDDEN_LAYERS = (384, 192, 96)


def load_labeled_rows(path: Path) -> list[dict]:
    rows: list[dict] = []
    seen: set[tuple] = set()
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        z = row.get("z")
        coordinate = (int(row["target_x_mm"]), int(row["target_y_mm"]))
        if not isinstance(z, list) or len(z) != 80:
            raise ValueError(f"{path}:{line_number}: z must contain 80 samples")
        if not (0 <= int(row["class_id"]) < 12):
            raise ValueError(f"{path}:{line_number}: class_id must be 0..11")
        key = (row.get("captured_at_unix_ns"), coordinate, tuple(z))
        if key in seen:
            continue
        seen.add(key)
        rows.append(row)
    if not rows:
        raise ValueError(f"no labeled events in {path}")
    return rows


def split_real_rows(rows: list[dict], holdout_every: int = 5) -> tuple[list[dict], list[dict]]:
    grouped: dict[tuple[int, int], list[dict]] = defaultdict(list)
    for row in rows:
        grouped[(int(row["target_x_mm"]), int(row["target_y_mm"]))].append(row)
    if len(grouped) != 60:
        raise ValueError(f"all 60 positions are required; found {len(grouped)}")
    too_small = {position: len(values) for position, values in grouped.items() if len(values) < holdout_every}
    if too_small:
        raise ValueError(f"at least {holdout_every} events per position are required; insufficient: {too_small}")
    training: list[dict] = []
    validation: list[dict] = []
    for position in sorted(grouped):
        ordered = sorted(grouped[position], key=lambda row: int(row.get("captured_at_unix_ns", 0)))
        for index, row in enumerate(ordered):
            (validation if index % holdout_every == holdout_every - 1 else training).append(row)
    return training, validation


def row_arrays(rows: list[dict]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    features = np.stack([extract_features(row["z"]) for row in rows]).astype(np.float32)
    labels = np.asarray([int(row["class_id"]) for row in rows], dtype=np.uint8)
    coordinates = np.asarray([[row["target_x_mm"], row["target_y_mm"]] for row in rows], dtype=np.float32)
    return features, labels, coordinates


def seed_rehearsal(seed_path: Path, per_position: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    with np.load(seed_path, allow_pickle=False) as seed:
        features = np.asarray(seed["features"], dtype=np.float32)
        labels = np.asarray(seed["labels"], dtype=np.uint8)
        coordinates = np.asarray(seed["xy_mm"], dtype=np.float32)
        support = np.asarray(seed["support_xy_mm"], dtype=np.float32)
    selected: list[int] = []
    for position in support:
        matches = np.flatnonzero(np.all(coordinates == position, axis=1))
        selected.extend(matches[:per_position].tolist())
    indices = np.asarray(selected, dtype=np.int64)
    return features[indices], labels[indices], coordinates[indices], support


def train_direct_xy(arrays: dict[str, np.ndarray], features: np.ndarray,
                    coordinates: np.ndarray, seed: int) -> int:
    normalized = (features - arrays["feature_mean"]) / arrays["feature_scale"]
    model = MLPRegressor(
        hidden_layer_sizes=XY_HIDDEN_LAYERS,
        activation="relu",
        solver="adam",
        alpha=1e-3,
        batch_size=min(128, len(features)),
        learning_rate_init=5e-4,
        max_iter=500,
        early_stopping=True,
        validation_fraction=0.15,
        n_iter_no_change=30,
        random_state=seed,
    )
    model.fit(normalized, coordinates / PANEL_SIZE_MM)
    add_xy_mlp(arrays, model.coefs_, model.intercepts_)
    return int(model.n_iter_)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "data" / "raw" / "mpu9250_uno_q" / "latest" / "training" / "mpu9250_events.jsonl")
    parser.add_argument("--seed", type=Path, default=ROOT / "uno_q_app" / "python" / "mpu9250_training_seed.npz")
    parser.add_argument("--output-root", type=Path, default=ROOT / "artifacts" / "mpu9250_real")
    parser.add_argument("--seed-rehearsal-per-position", type=int, default=4)
    parser.add_argument("--holdout-every", type=int, default=5)
    parser.add_argument("--seed-value", type=int, default=9250)
    args = parser.parse_args()

    input_path = args.input.resolve()
    if args.seed_rehearsal_per_position < 0:
        raise ValueError("--seed-rehearsal-per-position must be non-negative")
    if args.holdout_every < 2:
        raise ValueError("--holdout-every must be at least 2")
    rows = load_labeled_rows(input_path)
    fresh_train, fresh_validation = split_real_rows(rows, args.holdout_every)
    train_x, train_y, train_xy = row_arrays(fresh_train)
    validation_x, validation_y, validation_xy = row_arrays(fresh_validation)
    seed_x, seed_y, seed_xy, support = seed_rehearsal(args.seed.resolve(), args.seed_rehearsal_per_position)
    combined_x = np.concatenate((train_x, seed_x))
    combined_y = np.concatenate((train_y, seed_y))
    combined_xy = np.concatenate((train_xy, seed_xy))

    arrays = train_arrays(combined_x, combined_y, combined_xy, support, seed=args.seed_value)
    xy_iterations = train_direct_xy(arrays, combined_x, combined_xy, args.seed_value)
    validation = evaluate_arrays(arrays, validation_x, validation_y, validation_xy)
    training = evaluate_arrays(arrays, train_x, train_y, train_xy)

    stamp = time.strftime("%Y%m%d-%H%M%S")
    output = args.output_root.resolve() / stamp
    output.mkdir(parents=True, exist_ok=False)
    model_path = output / "mpu9250_models.npz"
    metadata_path = output / "mpu9250_model_metadata.json"
    save_model(model_path, arrays)
    metadata = {
        "model": f"acrylic_pan_mpu9250_real_{stamp}",
        "created_from": "real MPU9250 labeled captures with converted KX134 rehearsal",
        "trained_on_pc": True,
        "created_at_unix_ns": time.time_ns(),
        "input": str(input_path),
        "input_sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
        "fresh_event_count": len(rows),
        "fresh_training_count": len(fresh_train),
        "fresh_validation_count": len(fresh_validation),
        "seed_rehearsal_count": len(seed_x),
        "validation_split": f"each position: every {args.holdout_every}th event",
        "validation": validation,
        "fresh_training_metrics": training,
        "sensor": {"name": "MPU9250", "sample_rate_hz": 4000, "range_g": 16,
                   "event_samples": 80, "trigger_index": 10},
        "tasks": ["12class", "60class", "pseudo_xy_from_60class", "direct_xy_regression"],
        "direct_xy_model": {"architecture": [FEATURE_COUNT, *XY_HIDDEN_LAYERS, 2],
                            "training_iterations": xy_iterations},
    }
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "training_report.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    latest = args.output_root.resolve() / "latest"
    latest.mkdir(parents=True, exist_ok=True)
    for path in (model_path, metadata_path, output / "training_report.json"):
        shutil.copy2(path, latest / path.name)
    print(json.dumps({"output": str(output), "latest": str(latest), "validation": validation}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
