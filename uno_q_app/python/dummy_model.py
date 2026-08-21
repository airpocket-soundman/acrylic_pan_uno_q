"""Pure-Python reader and inference runtime for the existing dummy ELM model."""

from __future__ import annotations

import ast
import json
import struct
import zipfile
from dataclasses import dataclass
from pathlib import Path


INPUT_COUNT = 128
HIDDEN_COUNT = 32
OUTPUT_COUNT = 8


def _read_npy_float32(payload: bytes) -> tuple[tuple[int, ...], tuple[float, ...]]:
    if payload[:6] != b"\x93NUMPY":
        raise ValueError("invalid NPY magic")
    major = payload[6]
    if major == 1:
        header_size = struct.unpack_from("<H", payload, 8)[0]
        header_offset = 10
    elif major in (2, 3):
        header_size = struct.unpack_from("<I", payload, 8)[0]
        header_offset = 12
    else:
        raise ValueError(f"unsupported NPY version {major}")

    header = ast.literal_eval(
        payload[header_offset : header_offset + header_size].decode("latin1").strip()
    )
    if header["descr"] not in ("<f4", "=f4"):
        raise ValueError("only little-endian float32 NPY arrays are supported")
    shape = tuple(int(value) for value in header["shape"])
    count = 1
    for dimension in shape:
        count *= dimension
    source = struct.unpack_from(f"<{count}f", payload, header_offset + header_size)
    if header["fortran_order"]:
        if len(shape) != 2:
            raise ValueError("Fortran-order conversion only supports 2D arrays")
        rows, columns = shape
        values = tuple(source[column * rows + row] for row in range(rows) for column in range(columns))
    else:
        values = source
    return shape, values


@dataclass(frozen=True)
class DummyElmModel:
    alpha: tuple[float, ...]
    beta: tuple[float, ...]

    @classmethod
    def load(cls, path: Path) -> "DummyElmModel":
        with zipfile.ZipFile(path) as archive:
            alpha_shape, alpha = _read_npy_float32(archive.read("alpha.npy"))
            beta_shape, beta = _read_npy_float32(archive.read("beta.npy"))
        if alpha_shape != (INPUT_COUNT, HIDDEN_COUNT):
            raise ValueError(f"unexpected alpha shape: {alpha_shape}")
        if beta_shape != (HIDDEN_COUNT, OUTPUT_COUNT):
            raise ValueError(f"unexpected beta shape: {beta_shape}")
        return cls(alpha=alpha, beta=beta)

    def predict(self, features: list[float]) -> tuple[int, list[float]]:
        if len(features) != INPUT_COUNT:
            raise ValueError(f"expected {INPUT_COUNT} inputs, got {len(features)}")
        hidden = []
        for column in range(HIDDEN_COUNT):
            value = 0.5
            for row, feature in enumerate(features):
                value += 0.2 * feature * self.alpha[row * HIDDEN_COUNT + column]
            hidden.append(min(1.0, max(0.0, value)))

        scores = []
        for output in range(OUTPUT_COUNT):
            score = 0.0
            for row, value in enumerate(hidden):
                score += value * self.beta[row * OUTPUT_COUNT + output]
            scores.append(score)
        predicted = max(range(OUTPUT_COUNT), key=scores.__getitem__)
        return predicted, scores


def load_golden_cases(path: Path) -> list[dict]:
    document = json.loads(path.read_text(encoding="utf-8"))
    cases = document["cases"]
    if len(cases) != OUTPUT_COUNT:
        raise ValueError(f"expected {OUTPUT_COUNT} golden cases")
    return cases
