from __future__ import annotations

import sys
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "uno_q_app/python"))

from position_model import PositionModel, extract_grid_features  # noqa: E402


MODEL_ROOT = ROOT / "data/position_model_400x300"


def load_model() -> PositionModel:
    return PositionModel(
        MODEL_ROOT / "model.npz",
        MODEL_ROOT / "parity_cases.npz",
        MODEL_ROOT / "model_metadata.json",
    )


def test_all_portable_predictions_match_source_model() -> None:
    model = load_model()
    for case_id in range(60):
        result = model.parity_case(case_id)
        assert result["portable_delta_mm"] < 1e-4
        assert 0 <= result["x_mm"] <= 400
        assert 0 <= result["y_mm"] <= 300
        assert abs(sum(result["position_probabilities"]) - 1.0) < 1e-9


def test_rich_feature_contract() -> None:
    features = extract_grid_features(np.zeros(512, dtype=np.int16))
    assert features.shape == (714,)
    assert np.all(np.isfinite(features))
