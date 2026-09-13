"""TensorFlow Lite position models used by the UNO Q Linux app.

Every model takes one 512-sample KX134 Z-axis event and returns a 60-way
probability over the anchor positions plus an auxiliary normalised XY guess.
``predict_samples`` turns that into the app's result: the most likely anchor
(MAP), the probability-weighted expected XY, the 12-area index, a 90 %
credible set and the spatial spread of the distribution. The graph, the
winning area and the heat map are all drawn from this one distribution.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from time import perf_counter_ns

import numpy as np

try:
    from ai_edge_litert.interpreter import Interpreter
except ImportError:  # Development-PC fallback.
    import tensorflow as tf

    Interpreter = tf.lite.Interpreter


PANEL_SIZE_MM = np.asarray((400.0, 300.0), dtype=np.float32)


class TflitePositionModel:
    """One warm TFLite coordinate model with the app's common result contract."""

    accelerator = "cpu_xnnpack"

    def __init__(self, model_id: str, label: str, model_path: Path,
                 parity_path: Path, report_path: Path, input_kind: str = "raw_fft"):
        self.model_id = model_id
        self.label = label
        self.name = model_path.stem
        self.input_kind = input_kind
        self.parity = np.load(parity_path)
        self.support = np.asarray(self.parity["support_xy_mm"], dtype=np.float32)
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if model_id == "fft_large":
            evaluation = report.get("models", {}).get("large", {})
        elif model_id == "temporal_fft_ensemble":
            evaluation = report.get("ensemble", {})
        elif model_id == "temporal_cnn":
            evaluation = {"architecture": report.get("gpu", {}),
                          "tflite_test": report.get("tflite_test", {}).get("gpu_fp16", {}),
                          "tflite_parity": report.get("tflite_parity", {}).get("gpu_fp16", {})}
        else:
            evaluation = report.get("models", {}).get("standard", {})
        self.metadata = {"model_id": model_id, "label": label,
                         "evaluation_coverage": report.get("evaluation_coverage"),
                         "evaluation": evaluation}
        self._interpreter = Interpreter(model_path=str(model_path), num_threads=4)
        self._interpreter.allocate_tensors()
        self._input = self._interpreter.get_input_details()[0]
        self._outputs = {int(detail["shape"][-1]): detail
                         for detail in self._interpreter.get_output_details()}
        if 60 not in self._outputs or 2 not in self._outputs:
            raise RuntimeError(f"Unexpected TFLite outputs for {self.name}")
        self._lock = threading.Lock()
        # Warm XNNPACK and all lazy kernels before the first sensor event.
        self._invoke(np.zeros(512, dtype=np.float32))

    def _make_input(self, samples) -> np.ndarray:
        waveform = np.asarray(samples, dtype=np.float32)
        if waveform.shape != (512,):
            raise ValueError(f"Expected 512 samples, got {waveform.size}")
        # Embedded-FFT models take the raw 512 samples and do baseline removal,
        # normalisation and the Hann-windowed RFFT inside the TFLite graph. Only
        # the legacy temporal CNN needs its three input channels built here.
        if self.input_kind == "temporal_cnn":
            baseline = float(waveform[:64].mean())
            post = waveform[64:] - baseline
            peak = max(float(np.max(np.abs(post))), 1.0)
            rms = max(float(np.sqrt(np.mean(post ** 2))), 1.0)
            normalized = post / peak
            return np.stack((normalized,
                             np.full_like(normalized, np.log1p(peak) / 12.0),
                             np.full_like(normalized, np.log1p(rms) / 12.0)), axis=-1)[:, None, :]
        return waveform

    def _invoke(self, samples) -> tuple[np.ndarray, np.ndarray]:
        model_input = self._make_input(samples)
        with self._lock:
            self._interpreter.set_tensor(self._input["index"], model_input[None])
            self._interpreter.invoke()
            probability = self._interpreter.get_tensor(self._outputs[60]["index"])[0].copy()
            direct_xy = self._interpreter.get_tensor(self._outputs[2]["index"])[0].copy()
        return probability.astype(np.float64), direct_xy.astype(np.float64) * PANEL_SIZE_MM

    def predict_samples(self, samples) -> dict:
        started = perf_counter_ns()
        probability, direct_xy = self._invoke(samples)
        # Clamp and renormalise so the 60 outputs form a proper distribution.
        probability = np.maximum(probability, 0.0)
        probability /= max(float(probability.sum()), 1e-12)
        # Expected XY: probability-weighted mean of the anchor coordinates.
        expected_xy = probability @ self.support
        # MAP: the single most likely anchor.
        map_index = int(np.argmax(probability))
        map_xy = self.support[map_index]
        # Smallest set of anchors that together hold 90 % of the probability.
        order = np.argsort(probability)[::-1]
        count = int(np.searchsorted(np.cumsum(probability[order]), 0.90) + 1)
        # Spread of the distribution around the expected XY, reported as sigma.
        residual = self.support - expected_xy
        covariance = np.einsum("n,ni,nj->ij", probability, residual, residual)
        # Area index of the MAP anchor on the 4-column x 3-row, 100 mm grid.
        zone = int(np.clip(map_xy[1] // 100, 0, 2) * 4 + np.clip(map_xy[0] // 100, 0, 3))
        return {
            "x_mm": float(map_xy[0]), "y_mm": float(map_xy[1]),
            "map_x_mm": float(map_xy[0]), "map_y_mm": float(map_xy[1]),
            "expected_x_mm": float(expected_xy[0]), "expected_y_mm": float(expected_xy[1]),
            "direct_x_mm": float(direct_xy[0]), "direct_y_mm": float(direct_xy[1]),
            "predicted_class": zone,
            "position_probabilities": probability.tolist(),
            "support_xy_mm": self.support.astype(float).tolist(),
            "credible_90_indices": order[:count].astype(int).tolist(),
            "peak_probability": float(probability[map_index]),
            "sigma_x_mm": float(np.sqrt(max(covariance[0, 0], 0.0))),
            "sigma_y_mm": float(np.sqrt(max(covariance[1, 1], 0.0))),
            "inference_us": int((perf_counter_ns() - started) // 1000),
            "model": self.name,
            "method": ("uno_q_tflite_temporal_cnn_60point_probability_map"
                       if self.input_kind == "temporal_cnn" else
                       "uno_q_tflite_embedded_fft_60point_probability_map"),
            "inference_accelerator": self.accelerator,
        }

    def parity_case(self, case_id: int) -> dict:
        case_id %= len(self.parity["waveform"])
        result = self.predict_samples(self.parity["waveform"][case_id])
        target = self.parity["target_xy_mm"][case_id]
        result.update({"case_id": case_id, "source": "fft_tflite_parity_case",
                       "target_x_mm": float(target[0]), "target_y_mm": float(target[1])})
        return result


class SelectablePositionModels:
    """Atomically select between preloaded models without per-hit startup cost."""

    def __init__(self, model_root: Path, data_root: Path):
        parity = model_root / "parity_cases.npz"
        specifications = (
            ("fft_large", "FFT大型版（推奨）", "acrylic_pan_fft_hybrid_large_fp16.tflite",
             "evaluation_report.json", "raw_fft"),
            ("fft_standard", "FFT標準版", "acrylic_pan_fft_hybrid_standard_fp16.tflite",
             "evaluation_report.json", "raw_fft"),
            ("temporal_cnn", "従来CNN版", "acrylic_pan_xy_gpu_fp16.tflite",
             "cnn_evaluation_report.json", "temporal_cnn"),
            ("temporal_fft_ensemble", "CNN＋FFTアンサンブル", "acrylic_pan_temporal_fft_ensemble_fp16.tflite",
             "evaluation_report.json", "raw_fft"),
        )
        self._models = {model_id: TflitePositionModel(model_id, label, model_root / filename,
                                                       parity, model_root / report_name, input_kind)
                        for model_id, label, filename, report_name, input_kind in specifications}
        self._config_path = data_root / "config" / "inference_model.json"
        selected = "fft_large"
        try:
            selected = json.loads(self._config_path.read_text(encoding="utf-8"))["model_id"]
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            pass
        self._active_id = selected if selected in self._models else "fft_large"
        self._lock = threading.RLock()

    @property
    def active(self) -> TflitePositionModel:
        with self._lock:
            return self._models[self._active_id]

    @property
    def active_id(self): return self.active.model_id
    @property
    def name(self): return self.active.name
    @property
    def label(self): return self.active.label
    @property
    def accelerator(self): return self.active.accelerator
    @property
    def metadata(self): return self.active.metadata
    @property
    def support(self): return self.active.support

    def available(self) -> list[dict]:
        return [{"id": item.model_id, "label": item.label, "model": item.name,
                 "accelerator": item.accelerator} for item in self._models.values()]

    def select(self, model_id: str) -> dict:
        if model_id not in self._models:
            raise ValueError(f"Unknown inference model: {model_id}")
        with self._lock:
            self._active_id = model_id
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        self._config_path.write_text(json.dumps({"model_id": model_id}) + "\n", encoding="utf-8")
        return {"model_id": model_id, "label": self.active.label, "model": self.active.name,
                "accelerator": self.active.accelerator}

    def predict_samples(self, samples): return self.active.predict_samples(samples)
    def parity_case(self, case_id: int): return self.active.parity_case(case_id)
