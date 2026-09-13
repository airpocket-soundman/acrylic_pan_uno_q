from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = ROOT / "uno_q_fft_candidates"


class UnoQFftHybridCandidateTests(unittest.TestCase):
    def setUp(self):
        self.report = json.loads(
            (CANDIDATES / "evaluation_report.json").read_text(encoding="utf-8")
        )

    def test_dataset_and_split_are_comparable_to_baseline(self):
        self.assertEqual(self.report["event_count"], 7132)
        self.assertEqual(self.report["split"]["strategy"],
                         "whole_session_split_no_event_leakage")
        self.assertEqual(self.report["split"]["counts"],
                         {"train": 3545, "validation": 1080, "test": 2507})
        self.assertEqual(self.report["split"]["position_coverage"],
                         {"train": 60, "validation": 60, "test": 60})
        self.assertIn("all 60 positions", self.report["evaluation_coverage"])

    def test_standard_fp16_contains_embedded_fft(self):
        self.assertEqual(self.report["selected"],
                         "acrylic_pan_fft_hybrid_large_fp16.tflite")
        selected = self.report["models"]["standard"]["variants"]["fp16"]
        self.assertIn("RFFT2D", selected["artifact"]["operators"])
        self.assertIn("COMPLEX_ABS", selected["artifact"]["operators"])
        self.assertGreater(selected["test"]["position_top1_accuracy"], 0.965)
        self.assertGreater(selected["test"]["area_accuracy_12class"], 0.99)
        self.assertLess(selected["test"]["map_xy_mean_mm"], 2.2)
        self.assertLess(selected["parity"]["probability_max_abs_delta"], 0.001)

        model = CANDIDATES / selected["artifact"]["file"]
        self.assertEqual(model.stat().st_size, selected["artifact"]["bytes"])
        self.assertEqual(hashlib.sha256(model.read_bytes()).hexdigest(),
            selected["artifact"]["sha256"])

    def test_larger_model_is_selected_for_better_full_grid_generalization(self):
        standard = self.report["models"]["standard"]
        large = self.report["models"]["large"]
        self.assertGreater(large["parameters"], standard["parameters"])
        large_fp16 = large["variants"]["fp16"]
        standard_fp16 = standard["variants"]["fp16"]
        self.assertGreater(large_fp16["test"]["position_top1_accuracy"],
                           standard_fp16["test"]["position_top1_accuracy"])
        self.assertGreater(large_fp16["test"]["area_accuracy_12class"], .994)
        self.assertLess(large_fp16["test"]["expected_xy_mean_mm"], 1.8)
        self.assertLess(large_fp16["test"]["map_xy_mean_mm"], 1.8)
        self.assertIn("RFFT2D", large_fp16["artifact"]["operators"])

        model = CANDIDATES / large_fp16["artifact"]["file"]
        self.assertEqual(model.stat().st_size, large_fp16["artifact"]["bytes"])
        self.assertEqual(hashlib.sha256(model.read_bytes()).hexdigest(),
                         large_fp16["artifact"]["sha256"])


if __name__ == "__main__":
    unittest.main()
