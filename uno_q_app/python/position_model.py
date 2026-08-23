from __future__ import annotations

import json
from pathlib import Path
from time import perf_counter_ns

import numpy as np


def extract_grid_features(samples: list[int] | np.ndarray) -> np.ndarray:
    waveform = np.asarray(samples, dtype=np.float64)
    if waveform.shape != (512,):
        raise ValueError(f"Expected 512 samples, got {waveform.size}")
    baseline = float(np.mean(waveform[:64]))
    centered = waveform - baseline
    post = centered[64:]
    peak = max(float(np.max(np.abs(post))), 1.0)
    rms = max(float(np.sqrt(np.mean(post**2))), 1.0)
    normalized_time = post / peak
    spectrum = np.abs(np.fft.rfft(centered * np.hanning(512)))[1:]
    normalized_spectrum = np.log1p(spectrum / peak)
    absolute = np.abs(post)
    energy = absolute**2
    quarter_energy = np.asarray([np.sum(part) for part in np.array_split(energy, 4)]) / max(
        float(np.sum(energy)), 1.0
    )
    scalars = np.asarray(
        [
            np.log1p(peak),
            np.log1p(rms),
            peak / rms,
            float(np.argmax(absolute)) / max(len(post) - 1, 1),
            float(np.max(post)) / peak,
            float(-np.min(post)) / peak,
            *quarter_energy,
        ]
    )
    result = np.concatenate((normalized_time, normalized_spectrum, scalars))
    if result.shape != (714,) or not np.isfinite(result).all():
        raise RuntimeError("Position feature extraction failed")
    return result


def softmax(logits: np.ndarray) -> np.ndarray:
    shifted = logits - np.max(logits)
    values = np.exp(shifted)
    return values / np.sum(values)


class PositionModel:
    name = "acrylic_pan_position_400x300x5_grid_v7_portable"

    def __init__(self, model_path: Path, parity_path: Path, metadata_path: Path):
        archive = np.load(model_path)
        self.regression_mean = archive["regression_mean"]
        self.regression_scale = archive["regression_scale"]
        self.density_mean = archive["density_mean"]
        self.density_scale = archive["density_scale"]
        self.support = archive["support_xy_mm"]
        self.temperature = float(archive["density_temperature"][0])
        self.panel_size = archive["panel_size_mm"]
        self.regression = self._load_family(archive, "reg", 3)
        self.density = self._load_family(archive, "density", 3)
        self.parity = np.load(parity_path)
        self.metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

    @staticmethod
    def _load_family(archive, family: str, members: int) -> list[list[tuple[np.ndarray, np.ndarray]]]:
        result = []
        for member in range(members):
            layers = []
            layer = 0
            while f"{family}_{member}_w_{layer}" in archive:
                layers.append((archive[f"{family}_{member}_w_{layer}"], archive[f"{family}_{member}_b_{layer}"]))
                layer += 1
            result.append(layers)
        return result

    @staticmethod
    def _forward(features: np.ndarray, layers: list[tuple[np.ndarray, np.ndarray]]) -> np.ndarray:
        values = features
        for index, (weights, bias) in enumerate(layers):
            values = values @ weights + bias
            if index < len(layers) - 1:
                values = np.maximum(values, 0.0)
        return values

    def predict_samples(self, samples: list[int] | np.ndarray) -> dict:
        started = perf_counter_ns()
        features = extract_grid_features(samples)
        reg_scaled = (features - self.regression_mean) / self.regression_scale
        direct_members = np.stack([self._forward(reg_scaled, model) for model in self.regression])
        direct_xy = np.clip(direct_members.mean(axis=0), 0.0, 1.0) * self.panel_size

        density_scaled = (features - self.density_mean) / self.density_scale
        member_probability = np.stack(
            [softmax(self._forward(density_scaled, model)) for model in self.density]
        )
        probability = member_probability.mean(axis=0)
        probability = softmax(np.log(np.clip(probability, 1e-12, 1.0)) / self.temperature)
        expected_xy = probability @ self.support
        map_index = int(np.argmax(probability))
        map_xy = self.support[map_index]
        order = np.argsort(probability)[::-1]
        count = int(np.searchsorted(np.cumsum(probability[order]), 0.90) + 1)
        residual = self.support - expected_xy
        covariance = np.einsum("n,ni,nj->ij", probability, residual, residual)
        zone = int(np.clip(map_xy[1] // 100, 0, 2) * 4 + np.clip(map_xy[0] // 100, 0, 3))
        return {
            "x_mm": float(map_xy[0]),
            "y_mm": float(map_xy[1]),
            "map_x_mm": float(map_xy[0]),
            "map_y_mm": float(map_xy[1]),
            "expected_x_mm": float(expected_xy[0]),
            "expected_y_mm": float(expected_xy[1]),
            "direct_x_mm": float(direct_xy[0]),
            "direct_y_mm": float(direct_xy[1]),
            "predicted_class": zone,
            "position_probabilities": probability.astype(float).tolist(),
            "support_xy_mm": self.support.astype(float).tolist(),
            "credible_90_indices": order[:count].astype(int).tolist(),
            "peak_probability": float(probability[map_index]),
            "sigma_x_mm": float(np.sqrt(max(covariance[0, 0], 0.0))),
            "sigma_y_mm": float(np.sqrt(max(covariance[1, 1], 0.0))),
            "inference_us": int((perf_counter_ns() - started) // 1000),
            "model": self.name,
            "method": "pc_mlp_60class_probability_map",
        }

    def parity_case(self, case_id: int) -> dict:
        case_id %= len(self.parity["waveforms"])
        result = self.predict_samples(self.parity["waveforms"][case_id])
        result.update(
            {
                "case_id": case_id,
                "source": "portable_parity_case",
                "target_x_mm": float(self.parity["target_xy_mm"][case_id, 0]),
                "target_y_mm": float(self.parity["target_xy_mm"][case_id, 1]),
                "source_expected_x_mm": float(self.parity["expected_xy_mm"][case_id, 0]),
                "source_expected_y_mm": float(self.parity["expected_xy_mm"][case_id, 1]),
            }
        )
        result["portable_delta_mm"] = float(
            np.linalg.norm(
                np.asarray((result["expected_x_mm"], result["expected_y_mm"]))
                - self.parity["expected_xy_mm"][case_id]
            )
        )
        return result
