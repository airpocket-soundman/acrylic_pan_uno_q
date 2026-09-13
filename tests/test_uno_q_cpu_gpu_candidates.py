from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = ROOT / "uno_q_model_candidates"


class UnoQCpuGpuCandidateTests(unittest.TestCase):
    def test_selected_models_match_metadata_and_accuracy_contract(self):
        report = json.loads((CANDIDATES / "evaluation_report.json").read_text(encoding="utf-8"))
        cpu = json.loads((CANDIDATES / "cpu_model_metadata.json").read_text(encoding="utf-8"))
        gpu = json.loads((CANDIDATES / "gpu_model_metadata.json").read_text(encoding="utf-8"))

        self.assertEqual(report["event_count"], 7132)
        self.assertEqual(report["split"]["strategy"], "whole_session_split_no_event_leakage")
        self.assertEqual(report["split"]["counts"], {"train": 3545, "validation": 1080, "test": 2507})
        self.assertEqual(report["split"]["position_coverage"],
                         {"train": 60, "validation": 60, "test": 60})
        self.assertEqual(cpu["selected"], "acrylic_pan_xy_cpu_dynamic.tflite")
        self.assertEqual(gpu["selected"], "acrylic_pan_xy_gpu_fp16.tflite")
        self.assertGreater(report["tflite_test"]["cpu_dynamic"]["position_top1_accuracy"], .95)
        self.assertGreater(report["tflite_test"]["gpu_fp16"]["position_top1_accuracy"], .95)
        self.assertGreater(report["tflite_test"]["cpu_dynamic"]["area_accuracy_12class"], .99)
        self.assertGreater(report["tflite_test"]["gpu_fp16"]["area_accuracy_12class"], .99)
        self.assertLess(report["tflite_parity"]["gpu_fp16"]["direct_xy_max_delta_mm"], .5)
        self.assertNotIn("SHAPE", gpu["models"]["fp16"]["operators"])
        self.assertNotIn("STRIDED_SLICE", gpu["models"]["fp16"]["operators"])

        for metadata, variant in ((cpu, "dynamic"), (gpu, "fp16")):
            model = CANDIDATES / metadata["models"][variant]["file"]
            self.assertEqual(model.stat().st_size, metadata["models"][variant]["bytes"])
            self.assertEqual(hashlib.sha256(model.read_bytes()).hexdigest(),
                             metadata["models"][variant]["sha256"])


if __name__ == "__main__":
    unittest.main()
