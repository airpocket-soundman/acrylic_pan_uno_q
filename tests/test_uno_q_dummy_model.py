import importlib.util
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "uno_q_app" / "python" / "dummy_model.py"
SPEC = importlib.util.spec_from_file_location("uno_q_dummy_model", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class UnoQDummyModelTests(unittest.TestCase):
    def test_all_golden_cases_classify_correctly(self):
        model = MODULE.DummyElmModel.load(ROOT / "data" / "dummy_model" / "model.npz")
        cases = MODULE.load_golden_cases(ROOT / "data" / "dummy_model" / "golden_outputs.json")
        for case in cases:
            predicted, scores = model.predict(case["input"])
            self.assertEqual(predicted, case["expected_class"])
            self.assertEqual(len(scores), 8)


if __name__ == "__main__":
    unittest.main()
