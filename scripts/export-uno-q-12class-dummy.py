"""Export the merged 12-class firmware weights for UNO Q dummy inference."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HEADER = ROOT / "firmware" / "AcrylicPanCollector" / "generated" / "apan_12class_model.h"
DEFAULT_OUTPUT = ROOT / "data" / "dummy_model_12class"


def read_bfloat_array(source: str, name: str) -> np.ndarray:
    match = re.search(rf"\b{name}\s*\[[^=]+?=\s*\{{(.*?)\}};", source, re.DOTALL)
    if not match:
        raise ValueError(f"array not found: {name}")
    bits = np.asarray(
        [int(value, 16) for value in re.findall(r"0x[0-9A-Fa-f]{4}", match.group(1))],
        dtype=np.uint16,
    )
    return (bits.astype(np.uint32) << 16).view(np.float32)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--header", type=Path, default=DEFAULT_HEADER)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    source = args.header.read_text(encoding="ascii")
    alpha = read_bfloat_array(source, "apan_model_alpha").reshape(128, 32)
    beta = read_bfloat_array(source, "apan_model_beta").reshape(32, 12)
    golden = read_bfloat_array(source, "apan_model_golden_inputs").reshape(12, 128)
    hidden = np.clip(0.2 * (golden @ alpha) + 0.5, 0.0, 1.0)
    predictions = np.argmax(hidden @ beta, axis=1)
    expected = np.arange(12)
    if not np.array_equal(predictions, expected):
        raise RuntimeError(f"12-class golden inputs failed: {predictions.tolist()}")

    args.output.mkdir(parents=True, exist_ok=True)
    np.savez(args.output / "model.npz", alpha=alpha, beta=beta)
    document = {
        "model": "acrylic_pan_time128_h32_12class_v1",
        "source": str(args.header.relative_to(ROOT)).replace("\\", "/"),
        "note": "Representative inputs only; sensor accuracy is not measured by this self-test.",
        "cases": [
            {"case_id": int(index), "expected_class": int(index), "input": row.astype(float).tolist()}
            for index, row in enumerate(golden)
        ],
    }
    (args.output / "golden_outputs.json").write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
