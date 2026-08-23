from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import joblib
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_ROOT = ROOT.parent / "acrylic_pan"
DEFAULT_MODEL = DEFAULT_SOURCE_ROOT / "artifacts/pc_position_runtime_400x300x5/position_ensemble.joblib"
DEFAULT_REPORT = DEFAULT_SOURCE_ROOT / "artifacts/pc_position_runtime_400x300x5/training_report.json"
DEFAULT_SESSIONS = (
    DEFAULT_SOURCE_ROOT / "data/raw/sessions/20260821_221547_4c753402",
    DEFAULT_SOURCE_ROOT / "data/raw/sessions/20260823_104754_2553f5d8",
)
DEFAULT_OUTPUT = ROOT / "data/position_model_400x300"


def forward(features: np.ndarray, model) -> np.ndarray:
    values = np.asarray(features, dtype=np.float64)
    for index, (weights, bias) in enumerate(zip(model.coefs_, model.intercepts_)):
        values = values @ weights + bias
        if index < len(model.coefs_) - 1:
            values = np.maximum(values, 0.0)
    return values


def softmax(logits: np.ndarray) -> np.ndarray:
    shifted = logits - np.max(logits)
    values = np.exp(shifted)
    return values / np.sum(values)


def collect_parity_waveforms(sessions: tuple[Path, ...]) -> tuple[np.ndarray, np.ndarray]:
    selected: dict[tuple[float, float], np.ndarray] = {}
    for session in sessions:
        for line in (session / "manifest.jsonl").read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            annotation = row.get("annotations", {})
            coordinate = (float(annotation["target_x_mm"]), float(annotation["target_y_mm"]))
            if coordinate in selected:
                continue
            with np.load(session / row["file"], allow_pickle=False) as event:
                selected[coordinate] = np.asarray(event["samples"][:512], dtype=np.int16)
    if len(selected) != 60:
        raise ValueError(f"Expected 60 parity coordinates, got {len(selected)}")
    centres = {(x, y) for y in (50.0, 150.0, 250.0) for x in (50.0, 150.0, 250.0, 350.0)}
    order = sorted(selected, key=lambda xy: (xy not in centres, xy[1], xy[0]))
    return np.stack([selected[xy] for xy in order]), np.asarray(order, dtype=np.float32)


def export(source_root: Path, model_path: Path, report_path: Path, sessions: tuple[Path, ...], output: Path) -> None:
    sys.path.insert(0, str(source_root))
    from sim.pc_position_grid_runtime import extract_grid_features

    bundle = joblib.load(model_path)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    contract = bundle["contract"]
    if (
        contract.get("panel_width_mm") != 400.0
        or contract.get("panel_height_mm") != 300.0
        or contract.get("feature_mode") != "pc_rich_20ms_v1"
    ):
        raise ValueError(f"Unexpected source model contract: {contract}")

    arrays: dict[str, np.ndarray] = {
        "regression_mean": bundle["scaler"].mean_,
        "regression_scale": bundle["scaler"].scale_,
        "density_mean": bundle["density_scaler"].mean_,
        "density_scale": bundle["density_scaler"].scale_,
        "support_xy_mm": np.asarray(bundle["density_support_xy_mm"]),
        "density_temperature": np.asarray([bundle["density_temperature"]]),
        "panel_size_mm": np.asarray([400.0, 300.0]),
    }
    for family, models in (("reg", bundle["models"]), ("density", bundle["density_models"])):
        for member, model in enumerate(models):
            for layer, (weights, bias) in enumerate(zip(model.coefs_, model.intercepts_)):
                arrays[f"{family}_{member}_w_{layer}"] = np.asarray(weights)
                arrays[f"{family}_{member}_b_{layer}"] = np.asarray(bias)

    waveforms, targets = collect_parity_waveforms(sessions)
    features = np.stack([extract_grid_features(row) for row in waveforms])
    reg_scaled = bundle["scaler"].transform(features)
    direct_members = np.stack([forward(reg_scaled, model) for model in bundle["models"]])
    direct_xy = np.clip(direct_members.mean(axis=0), 0.0, 1.0) * (400.0, 300.0)
    density_scaled = bundle["density_scaler"].transform(features)
    member_probability = np.stack(
        [np.stack([softmax(forward(row, model)) for row in density_scaled]) for model in bundle["density_models"]]
    )
    probability = member_probability.mean(axis=0)
    temperature = float(bundle["density_temperature"])
    probability = np.stack([softmax(np.log(np.clip(row, 1e-12, 1.0)) / temperature) for row in probability])
    support = np.asarray(bundle["density_support_xy_mm"])
    expected_xy = probability @ support
    map_xy = support[np.argmax(probability, axis=1)]

    output.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(output / "model.npz", **arrays)
    np.savez_compressed(
        output / "parity_cases.npz",
        waveforms=waveforms,
        target_xy_mm=targets,
        expected_xy_mm=expected_xy,
        map_xy_mm=map_xy,
        direct_xy_mm=direct_xy,
        probabilities=probability,
    )
    metadata = {
        "model": "acrylic_pan_position_400x300x5_grid_v7_portable",
        "source_model": str(model_path),
        "source_sha256": hashlib.sha256(model_path.read_bytes()).hexdigest(),
        "source_experiment": report["experiment"],
        "contract": contract,
        "architecture": report["architecture"],
        "sample_count": report["sample_count"],
        "unique_coordinates": report["unique_coordinates"],
        "validation": report["common_holdout_comparison"]["candidate_seven_grid_sessions"],
        "density_validation": report["density_validation"],
        "scope": report["scope"],
        "parity_case_count": len(waveforms),
    }
    (output / "model_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Exported portable model: {output / 'model.npz'}")
    print(f"Parity cases: {len(waveforms)} / source SHA-256 {metadata['source_sha256']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Import today's 400x300 Acrylic Pan position model for UNO Q.")
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--sessions", type=Path, nargs="+", default=list(DEFAULT_SESSIONS))
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    export(args.source_root, args.model, args.report, tuple(args.sessions), args.output)


if __name__ == "__main__":
    main()
