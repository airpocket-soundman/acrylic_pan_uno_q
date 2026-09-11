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
                         {"train": 4745, "validation": 480, "test": 1907})
        self.assertIn("48 of 60", self.report["evaluation_limit"])

    def test_standard_fp16_contains_embedded_fft(self):
        self.assertEqual(self.report["selected"],
                         "acrylic_pan_temporal_fft_ensemble_fp16.tflite")
        selected = self.report["models"]["standard"]["variants"]["fp16"]
        self.assertIn("RFFT2D", selected["artifact"]["operators"])
        self.assertIn("COMPLEX_ABS", selected["artifact"]["operators"])
        self.assertGreater(selected["test"]["position_top1_accuracy"], 0.97)
        self.assertGreater(selected["test"]["area_accuracy_12class"], 0.988)
        self.assertLess(selected["test"]["map_xy_mean_mm"], 1.7)
        self.assertLess(selected["parity"]["probability_max_abs_delta"], 0.001)

        model = CANDIDATES / selected["artifact"]["file"]
        self.assertEqual(model.stat().st_size, selected["artifact"]["bytes"])
        self.assertEqual(hashlib.sha256(model.read_bytes()).hexdigest(),
            selected["artifact"]["sha256"])

    def test_selected_ensemble_improves_baseline_accuracy(self):
        ensemble = self.report["ensemble"]
        self.assertAlmostEqual(ensemble["temporal_weight"], 0.85)
        self.assertAlmostEqual(ensemble["fft_weight"], 0.15)
        self.assertGreater(ensemble["test"]["position_top1_accuracy"], 0.9795)
        self.assertGreater(ensemble["test"]["area_accuracy_12class"], 0.989)
        self.assertLess(ensemble["test"]["expected_xy_mean_mm"], 1.85)
        self.assertIn("RFFT2D", ensemble["artifact"]["operators"])

        model = CANDIDATES / ensemble["artifact"]["file"]
        self.assertEqual(model.stat().st_size, ensemble["artifact"]["bytes"])
        self.assertEqual(hashlib.sha256(model.read_bytes()).hexdigest(),
                         ensemble["artifact"]["sha256"])

    def test_larger_model_is_recorded_but_not_selected(self):
        standard = self.report["models"]["standard"]
        large = self.report["models"]["large"]
        self.assertGreater(large["parameters"], standard["parameters"])
        self.assertLessEqual(
            large["variants"]["fp16"]["test"]["position_top1_accuracy"],
            standard["variants"]["fp16"]["test"]["position_top1_accuracy"],
        )


if __name__ == "__main__":
    unittest.main()
