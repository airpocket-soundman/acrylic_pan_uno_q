import importlib.util
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "train_mpu9250_real_data", ROOT / "scripts" / "train_mpu9250_real_data.py"
)
TRAINER = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(TRAINER)


def make_rows(repetitions=5):
    rows = []
    timestamp = 1
    with np.load(
        ROOT / "uno_q_app" / "python" / "mpu9250_training_seed.npz",
        allow_pickle=False,
    ) as seed:
        support = seed["support_xy_mm"]
    for x_mm, y_mm in support:
        for _ in range(repetitions):
            rows.append({
                "class_id": int(y_mm // 100) * 4 + int(x_mm // 100),
                "target_x_mm": int(x_mm),
                "target_y_mm": int(y_mm),
                "captured_at_unix_ns": timestamp,
                "z": list(range(80)),
            })
            timestamp += 1
    return rows


class RealMpu9250TrainingTests(unittest.TestCase):
    def test_load_labeled_rows_deduplicates(self):
        row = make_rows(1)[0]
        with TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            path.write_text(json.dumps(row) + "\n" + json.dumps(row) + "\n", encoding="utf-8")
            self.assertEqual(TRAINER.load_labeled_rows(path), [row])

    def test_split_holds_out_each_of_all_60_positions(self):
        training, validation = TRAINER.split_real_rows(make_rows(), holdout_every=5)
        self.assertEqual(len(training), 240)
        self.assertEqual(len(validation), 60)
        self.assertEqual(
            len({(row["target_x_mm"], row["target_y_mm"]) for row in validation}), 60
        )

    def test_split_rejects_incomplete_position_set(self):
        with self.assertRaisesRegex(ValueError, "all 60 positions"):
            TRAINER.split_real_rows(make_rows()[:-5], holdout_every=5)


if __name__ == "__main__":
    unittest.main()
