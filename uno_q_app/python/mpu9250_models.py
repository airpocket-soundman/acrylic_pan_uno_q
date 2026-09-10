from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter_ns

import numpy as np


SAMPLE_RATE_HZ = 4_000
EVENT_SAMPLES = 80
TRIGGER_INDEX = 10
FEATURE_COUNT = 120
PANEL_SIZE_MM = np.asarray((400.0, 300.0), dtype=np.float64)
XY_MLP_LAYER_COUNT = 4


def extract_features(samples: list[int] | np.ndarray) -> np.ndarray:
    waveform = np.asarray(samples, dtype=np.float64)
    if waveform.shape != (EVENT_SAMPLES,):
        raise ValueError(f"expected {EVENT_SAMPLES} samples, got {waveform.size}")
    baseline = float(np.mean(waveform[:TRIGGER_INDEX]))
    centered = waveform - baseline
    post = centered[TRIGGER_INDEX:]
    peak = max(float(np.max(np.abs(post))), 1.0)
    rms = max(float(np.sqrt(np.mean(post**2))), 1.0)
    normalized_time = post / peak
    spectrum = np.abs(np.fft.rfft(centered * np.hanning(EVENT_SAMPLES)))[1:]
    normalized_spectrum = np.log1p(spectrum / peak)
    absolute = np.abs(post)
    energy = absolute**2
    quarters = np.asarray([np.sum(part) for part in np.array_split(energy, 4)])
    quarters /= max(float(np.sum(energy)), 1.0)
    scalars = np.asarray((
        np.log1p(peak), np.log1p(rms), peak / rms,
        float(np.argmax(absolute)) / max(len(post) - 1, 1),
        float(np.max(post)) / peak, float(-np.min(post)) / peak,
        *quarters,
    ))
    result = np.concatenate((normalized_time, normalized_spectrum, scalars)).astype(np.float32)
    if result.shape != (FEATURE_COUNT,) or not np.isfinite(result).all():
        raise RuntimeError("MPU9250 feature extraction failed")
    return result


def _softmax(logits: np.ndarray) -> np.ndarray:
    values = np.asarray(logits, dtype=np.float64)
    values -= np.max(values, axis=-1, keepdims=True)
    values = np.exp(values)
    return values / np.sum(values, axis=-1, keepdims=True)


def _area_ids(xy_mm: np.ndarray) -> np.ndarray:
    xy = np.asarray(xy_mm, dtype=np.float64)
    columns = np.clip((xy[..., 0] // 100.0).astype(np.int64), 0, 3)
    rows = np.clip((xy[..., 1] // 100.0).astype(np.int64), 0, 2)
    return rows * 4 + columns


def _hidden(features: np.ndarray, mean: np.ndarray, scale: np.ndarray,
            alpha: np.ndarray, bias: np.ndarray) -> np.ndarray:
    normalized = (np.asarray(features, dtype=np.float64) - mean) / scale
    return np.tanh(normalized @ alpha + bias)


def _ridge(hidden: np.ndarray, targets: np.ndarray, ridge: float) -> np.ndarray:
    identity = np.eye(hidden.shape[1], dtype=np.float64)
    return np.linalg.solve(hidden.T @ hidden + ridge * identity, hidden.T @ targets)


def _xy_mlp(arrays: dict[str, np.ndarray], features: np.ndarray) -> np.ndarray:
    """Run the portable, fully-trained direct-XY MLP stored in the model archive."""
    values = ((np.asarray(features, dtype=np.float64) - arrays["feature_mean"])
              / arrays["feature_scale"])
    for index in range(XY_MLP_LAYER_COUNT):
        values = values @ arrays[f"xy_w_{index}"] + arrays[f"xy_b_{index}"]
        if index + 1 < XY_MLP_LAYER_COUNT:
            values = np.maximum(values, 0.0)
    return np.clip(values, 0.0, 1.0) * arrays["panel_size_mm"]


def has_xy_mlp(arrays: dict[str, np.ndarray]) -> bool:
    return all(f"xy_w_{index}" in arrays and f"xy_b_{index}" in arrays
               for index in range(XY_MLP_LAYER_COUNT))


def add_xy_mlp(arrays: dict[str, np.ndarray], weights: list[np.ndarray],
               biases: list[np.ndarray]) -> dict[str, np.ndarray]:
    if len(weights) != XY_MLP_LAYER_COUNT or len(biases) != XY_MLP_LAYER_COUNT:
        raise ValueError("direct XY MLP must have four trainable layers")
    for index, (weight, bias) in enumerate(zip(weights, biases)):
        arrays[f"xy_w_{index}"] = np.asarray(weight, dtype=np.float32)
        arrays[f"xy_b_{index}"] = np.asarray(bias, dtype=np.float32)
    return arrays


def copy_xy_mlp(source: dict[str, np.ndarray], destination: dict[str, np.ndarray]) -> None:
    if not has_xy_mlp(source):
        return
    for index in range(XY_MLP_LAYER_COUNT):
        destination[f"xy_w_{index}"] = np.asarray(source[f"xy_w_{index}"], dtype=np.float32).copy()
        destination[f"xy_b_{index}"] = np.asarray(source[f"xy_b_{index}"], dtype=np.float32).copy()


def fine_tune_xy_mlp(arrays: dict[str, np.ndarray], features: np.ndarray,
                     xy_mm: np.ndarray, *, epochs: int = 8, batch_size: int = 128,
                     learning_rate: float = 1e-4, seed: int = 9250) -> None:
    """Small NumPy Adam update used on UNO Q after real MPU9250 captures."""
    if not has_xy_mlp(arrays):
        return
    x = ((np.asarray(features, dtype=np.float32) - arrays["feature_mean"])
         / arrays["feature_scale"])
    target = np.asarray(xy_mm, dtype=np.float32) / arrays["panel_size_mm"]
    weights = [arrays[f"xy_w_{index}"].astype(np.float32, copy=True)
               for index in range(XY_MLP_LAYER_COUNT)]
    biases = [arrays[f"xy_b_{index}"].astype(np.float32, copy=True)
              for index in range(XY_MLP_LAYER_COUNT)]
    parameters = weights + biases
    first = [np.zeros_like(value) for value in parameters]
    second = [np.zeros_like(value) for value in parameters]
    random = np.random.default_rng(seed)
    step = 0
    for _ in range(epochs):
        order = random.permutation(len(x))
        for start in range(0, len(x), batch_size):
            indices = order[start:start + batch_size]
            activations = [x[indices]]
            preactivations = []
            for layer, (weight, bias) in enumerate(zip(weights, biases)):
                value = activations[-1] @ weight + bias
                preactivations.append(value)
                activations.append(np.maximum(value, 0.0) if layer + 1 < XY_MLP_LAYER_COUNT else value)
            gradient = 2.0 * (activations[-1] - target[indices]) / len(indices)
            weight_gradients: list[np.ndarray] = []
            bias_gradients: list[np.ndarray] = []
            for layer in range(XY_MLP_LAYER_COUNT - 1, -1, -1):
                weight_gradients.append(activations[layer].T @ gradient + 2e-5 * weights[layer])
                bias_gradients.append(np.sum(gradient, axis=0))
                if layer:
                    gradient = (gradient @ weights[layer].T) * (preactivations[layer - 1] > 0.0)
            gradients = list(reversed(weight_gradients)) + list(reversed(bias_gradients))
            step += 1
            for index, (parameter, gradient_value) in enumerate(zip(parameters, gradients)):
                first[index] = 0.9 * first[index] + 0.1 * gradient_value
                second[index] = 0.999 * second[index] + 0.001 * gradient_value**2
                corrected_first = first[index] / (1.0 - 0.9**step)
                corrected_second = second[index] / (1.0 - 0.999**step)
                parameter -= learning_rate * corrected_first / (np.sqrt(corrected_second) + 1e-8)
    add_xy_mlp(arrays, weights, biases)


def train_arrays(features: np.ndarray, labels: np.ndarray, xy_mm: np.ndarray,
                 support_xy_mm: np.ndarray | None = None, *, seed: int = 9250,
                 hidden_count: int = 768, ridge: float = 1.0,
                 temperature12: float = 0.05, temperature60: float = 0.05) -> dict[str, np.ndarray]:
    x = np.asarray(features, dtype=np.float64)
    labels = np.asarray(labels, dtype=np.int64)
    xy = np.asarray(xy_mm, dtype=np.float64)
    if x.ndim != 2 or x.shape[1] != FEATURE_COUNT or len(x) != len(labels) or xy.shape != (len(x), 2):
        raise ValueError("invalid training arrays")
    if len(x) < 60 or set(np.unique(labels)) != set(range(12)):
        raise ValueError("training data must contain all 12 areas")
    support = np.unique(xy, axis=0) if support_xy_mm is None else np.asarray(support_xy_mm, dtype=np.float64)
    if len(support) != 60:
        raise ValueError(f"expected 60 coordinate classes, got {len(support)}")
    lookup = {tuple(row): index for index, row in enumerate(support)}
    position_labels = np.asarray([lookup[tuple(row)] for row in xy], dtype=np.int64)
    mean = np.mean(x, axis=0)
    scale = np.std(x, axis=0)
    scale[scale < 1e-6] = 1.0
    random = np.random.default_rng(seed)
    alpha = random.normal(0.0, 1.0 / np.sqrt(FEATURE_COUNT), (FEATURE_COUNT, hidden_count))
    bias = random.uniform(-0.5, 0.5, hidden_count)
    hidden = _hidden(x, mean, scale, alpha, bias)
    target12 = np.eye(12, dtype=np.float64)[labels]
    target60 = np.eye(60, dtype=np.float64)[position_labels]
    return {
        "feature_mean": mean.astype(np.float32),
        "feature_scale": scale.astype(np.float32),
        "alpha": alpha.astype(np.float32),
        "bias": bias.astype(np.float32),
        "beta12": _ridge(hidden, target12, ridge).astype(np.float32),
        "beta60": _ridge(hidden, target60, ridge).astype(np.float32),
        "beta_xy": _ridge(hidden, xy / PANEL_SIZE_MM, ridge).astype(np.float32),
        "support_xy_mm": support.astype(np.float32),
        "panel_size_mm": PANEL_SIZE_MM.astype(np.float32),
        "temperature12": np.asarray((temperature12,), dtype=np.float32),
        "temperature60": np.asarray((temperature60,), dtype=np.float32),
    }


def evaluate_arrays(arrays: dict[str, np.ndarray], features: np.ndarray,
                    labels: np.ndarray, xy_mm: np.ndarray) -> dict:
    hidden = _hidden(features, arrays["feature_mean"], arrays["feature_scale"],
                     arrays["alpha"], arrays["bias"])
    probability12 = _softmax((hidden @ arrays["beta12"]) / float(arrays["temperature12"][0]))
    probability60 = _softmax((hidden @ arrays["beta60"]) / float(arrays["temperature60"][0]))
    direct = (_xy_mlp(arrays, features) if has_xy_mlp(arrays) else
              np.clip(hidden @ arrays["beta_xy"], 0.0, 1.0) * PANEL_SIZE_MM)
    pseudo = probability60 @ arrays["support_xy_mm"]
    expected = np.asarray(xy_mm, dtype=np.float64)
    labels = np.asarray(labels, dtype=np.int64)
    return {
        "count": int(len(labels)),
        "area_accuracy_12class": float(np.mean(np.argmax(probability12, axis=1) == labels)),
        "area_accuracy_60class": float(np.mean(_area_ids(arrays["support_xy_mm"][np.argmax(probability60, axis=1)]) == labels)),
        "position_top1_accuracy": float(np.mean(np.all(arrays["support_xy_mm"][np.argmax(probability60, axis=1)] == expected, axis=1))),
        "pseudo_xy_mae_mm": float(np.mean(np.linalg.norm(pseudo - expected, axis=1))),
        "direct_xy_mae_mm": float(np.mean(np.linalg.norm(direct - expected, axis=1))),
        "pseudo_xy_p90_mm": float(np.percentile(np.linalg.norm(pseudo - expected, axis=1), 90)),
        "direct_xy_p90_mm": float(np.percentile(np.linalg.norm(direct - expected, axis=1), 90)),
    }


@dataclass
class ModelSuite:
    model_path: Path
    metadata_path: Path

    def __post_init__(self) -> None:
        self._lock = threading.RLock()
        self.reload()

    def reload(self) -> None:
        with np.load(self.model_path, allow_pickle=False) as archive:
            arrays = {name: np.asarray(archive[name]) for name in archive.files}
        metadata = json.loads(self.metadata_path.read_text(encoding="utf-8"))
        with self._lock:
            self.arrays = arrays
            self.metadata = metadata

    def predict(self, samples: list[int] | np.ndarray) -> dict:
        started = perf_counter_ns()
        features = extract_features(samples)
        with self._lock:
            arrays = self.arrays
            hidden = _hidden(features, arrays["feature_mean"], arrays["feature_scale"],
                             arrays["alpha"], arrays["bias"])
            probability12 = _softmax((hidden @ arrays["beta12"]) / float(arrays["temperature12"][0]))
            probability60 = _softmax((hidden @ arrays["beta60"]) / float(arrays["temperature60"][0]))
            support = arrays["support_xy_mm"]
            direct = (_xy_mlp(arrays, features) if has_xy_mlp(arrays) else
                      np.clip(hidden @ arrays["beta_xy"], 0.0, 1.0) * arrays["panel_size_mm"])
        map_index = int(np.argmax(probability60))
        map_xy = support[map_index]
        pseudo = probability60 @ support
        order = np.argsort(probability60)[::-1]
        credible_count = int(np.searchsorted(np.cumsum(probability60[order]), 0.90) + 1)
        entropy = float(-np.sum(probability60 * np.log(np.clip(probability60, 1e-12, 1.0))))
        residual = support - pseudo
        covariance = np.einsum("n,ni,nj->ij", probability60, residual, residual)
        area = int(np.argmax(probability12))
        return {
            "predicted_class": area,
            "class_probabilities": probability12.astype(float).tolist(),
            "position_index": map_index,
            "position_probabilities": probability60.astype(float).tolist(),
            "support_xy_mm": support.astype(float).tolist(),
            "credible_90_indices": order[:credible_count].astype(int).tolist(),
            "distribution_peak_probability": float(probability60[map_index]),
            "distribution_entropy": entropy,
            "map_x_mm": float(map_xy[0]), "map_y_mm": float(map_xy[1]),
            "x_mm": float(pseudo[0]), "y_mm": float(pseudo[1]),
            "expected_x_mm": float(pseudo[0]), "expected_y_mm": float(pseudo[1]),
            "direct_x_mm": float(direct[0]), "direct_y_mm": float(direct[1]),
            "sigma_x_mm": float(np.sqrt(max(covariance[0, 0], 0.0))),
            "sigma_y_mm": float(np.sqrt(max(covariance[1, 1], 0.0))),
            "inference_us": int((perf_counter_ns() - started) // 1000),
            "model": self.metadata.get("model", "mpu9250_unified_v2"),
            "method": "12class ELM + 60class probability pseudo-XY + direct XY MLP",
        }


def save_model(path: Path, arrays: dict[str, np.ndarray]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp.npz")
    np.savez_compressed(temporary, **arrays)
    temporary.replace(path)
