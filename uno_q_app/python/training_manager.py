from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

PANEL = {"id": "400x300x5", "label": "400 × 300 × 5 mm（12クラス）",
         "width_mm": 400, "height_mm": 300, "thickness_mm": 5,
         "columns": 4, "rows": 3, "class_count": 12,
         "area_width_mm": 100, "area_height_mm": 100,
         "clamp": {"x_min": 200, "x_max": 300, "y_min": 0, "y_max": 20}}


def targets_60(support_xy_mm: np.ndarray) -> list[dict]:
    result = []
    for row in range(3):
        for column in range(4):
            class_id = row * 4 + column
            points = [point for point in np.asarray(support_xy_mm) if
                      int(point[0] // 100) == column and int(point[1] // 100) == row]
            points.sort(key=lambda point: (bool(int(point[0]) % 100 == 50 and int(point[1]) % 100 == 50), point[1], point[0]))
            for point_id, point in enumerate(points):
                x_mm, y_mm = int(point[0]), int(point[1])
                name = "center" if x_mm % 100 == 50 and y_mm % 100 == 50 else ("up_left", "up_right", "down_left", "down_right")[point_id]
                result.append({"target_index": len(result), "class_id": class_id,
                               "point_id": point_id, "point_name": name,
                               "x_mm": x_mm, "y_mm": y_mm})
    return result


class TrainingManager:
    SESSION_ID = "kx134-training"

    def __init__(self, data_root: Path, model):
        self.data_root = Path(data_root)
        self.model = model
        self.events_path = self.data_root / "training" / "kx134_events.jsonl"
        self.targets = targets_60(model.support)
        self._lock = threading.RLock()
        self.active = False
        self.finished = False
        self.repetitions = 0
        self.pattern = "all60"
        self.active_indices = list(range(60))
        self.selected_index: int | None = None
        self.counts = [0] * len(self.targets)
        self.training = {"active": False, "last_error": None, "last_report": None}

    def start(self, repetitions: int, pattern: str = "corners") -> dict:
        if not 1 <= repetitions <= 1000:
            raise ValueError("repetitions must be 1..1000")
        with self._lock:
            if pattern == "center": self.active_indices = [index for index, target in enumerate(self.targets) if target["point_id"] == 4]
            elif pattern == "corners": self.active_indices = [index for index, target in enumerate(self.targets) if target["point_id"] < 4]
            elif pattern == "all60": self.active_indices = list(range(60))
            else: raise ValueError("unknown position pattern")
            self.pattern = pattern
            self.active, self.finished, self.repetitions = True, False, repetitions
            self.selected_index = self.active_indices[0]
            self.counts = [0] * len(self.targets)
        return self.status()

    def select(self, index: int) -> dict:
        if not self.active or not 0 <= index < len(self.targets):
            raise ValueError("invalid or inactive collection target")
        self.selected_index = index
        return self.status()

    def stop(self) -> dict:
        self.active = False
        self.selected_index = None
        return self.status()

    def undo(self) -> dict:
        if not self.active:
            raise ValueError("collection is not active")
        nonempty = [index for index, count in enumerate(self.counts) if count]
        if not nonempty:
            raise ValueError("nothing to undo")
        index = nonempty[-1]
        rows = self._read_rows()
        for row_index in range(len(rows) - 1, -1, -1):
            if rows[row_index].get("collection_target_index") == index:
                rows.pop(row_index)
                break
        self.events_path.parent.mkdir(parents=True, exist_ok=True)
        self.events_path.write_text("".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows), encoding="utf-8")
        self.counts[index] -= 1
        self.selected_index = index
        return self.status()

    def record(self, event: dict) -> dict | None:
        with self._lock:
            if not self.active or self.selected_index is None:
                return None
            index = self.selected_index
            target = self.targets[index]
            row = {**event, "collection_target_index": index, "class_id": target["class_id"],
                   "target_x_mm": target["x_mm"], "target_y_mm": target["y_mm"],
                   "target_point_name": target["point_name"],
                   "repetition": self.counts[index] + 1,
                   "captured_at_unix_ns": time.time_ns()}
            self.events_path.parent.mkdir(parents=True, exist_ok=True)
            with self.events_path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(row, separators=(",", ":")) + "\n")
            self.counts[index] += 1
            remaining = [i for i in self.active_indices if self.counts[i] < self.repetitions]
            if remaining:
                self.selected_index = remaining[0]
            else:
                self.active, self.finished, self.selected_index = False, True, None
            return row

    def _read_rows(self) -> list[dict]:
        if not self.events_path.is_file():
            return []
        return [json.loads(line) for line in self.events_path.read_text(encoding="utf-8").splitlines() if line]

    @staticmethod
    def _iso_time(row: dict) -> str:
        nanoseconds = int(row.get("captured_at_unix_ns", 0))
        return datetime.fromtimestamp(nanoseconds / 1_000_000_000, timezone.utc).isoformat()

    def _event_summary(self, row: dict, index: int) -> dict:
        target_index = int(row.get("collection_target_index", -1))
        target = self.targets[target_index] if 0 <= target_index < len(self.targets) else {}
        return {
            "index": index,
            "sequence": int(row.get("sequence", index)),
            "class_id": int(row["class_id"]),
            "peak_abs": int(row.get("peak_abs", max(abs(int(value)) for value in row["z"]))),
            "received_at": self._iso_time(row),
            "exists": True,
            "annotations": {
                "target_point_name": row.get("target_point_name", target.get("point_name")),
                "repetition": row.get("repetition"),
                "target_x_mm": int(row["target_x_mm"]),
                "target_y_mm": int(row["target_y_mm"]),
            },
        }

    def list_sessions(self) -> dict:
        with self._lock:
            rows = self._read_rows()
            if not rows:
                return {"root": str(self.events_path.parent), "sessions": []}
            classes = sorted({int(row["class_id"]) for row in rows})
            session = {
                "session_id": self.SESSION_ID,
                "event_count": len(rows),
                "declared_event_count": len(rows),
                "class_ids": classes,
                "created_at": self._iso_time(rows[0]),
                "closed_at": None if self.active else self._iso_time(rows[-1]),
                "mode": "guided_60_positions",
                "consistent": True,
                "error": None,
            }
            return {"root": str(self.events_path.parent), "sessions": [session]}

    def list_events(self, session_id: str) -> dict:
        if session_id != self.SESSION_ID:
            raise ValueError("unknown training session")
        with self._lock:
            rows = self._read_rows()
            return {"root": str(self.events_path.parent), "session_id": session_id,
                    "events": [self._event_summary(row, index) for index, row in enumerate(rows, 1)]}

    def load_event(self, session_id: str, index: int) -> dict:
        if session_id != self.SESSION_ID:
            raise ValueError("unknown training session")
        with self._lock:
            rows = self._read_rows()
            if not 1 <= index <= len(rows):
                raise ValueError("unknown training event")
            row = rows[index - 1]
        samples = np.asarray(row["z"], dtype=np.float64)
        sample_rate = int(row.get("sample_rate_hz", 25600))
        windowed = (samples - np.mean(samples)) * np.hanning(len(samples))
        magnitude = np.abs(np.fft.rfft(windowed))
        magnitude_db = 20.0 * np.log10(np.maximum(magnitude, 1e-9))
        summary = self._event_summary(row, index)
        return {
            "sequence": summary["sequence"], "source": "kx134-training-library",
            "samples": samples.astype(int).tolist(),
            "time_ms": (np.arange(len(samples)) * 1000.0 / sample_rate).tolist(),
            "frequency_hz": np.fft.rfftfreq(len(samples), 1.0 / sample_rate).tolist(),
            "magnitude_db": magnitude_db.tolist(), "sample_rate_hz": sample_rate,
            "trigger_time_ms": float(row.get("trigger_index", 64)) * 1000.0 / sample_rate,
            "peak_abs": summary["peak_abs"],
            "stored": {"session_id": session_id, "index": index,
                       "class_id": summary["class_id"]},
        }

    def delete_event(self, session_id: str, index: int) -> dict:
        if session_id != self.SESSION_ID:
            raise ValueError("unknown training session")
        with self._lock:
            if self.active:
                raise ValueError("採取中は削除できません。先に採取を停止してください")
            rows = self._read_rows()
            if not 1 <= index <= len(rows):
                raise ValueError("unknown training event")
            deleted = rows.pop(index - 1)
            self._write_rows(rows)
            target_index = int(deleted.get("collection_target_index", -1))
            if 0 <= target_index < len(self.counts) and self.counts[target_index] > 0:
                self.counts[target_index] -= 1
            self.finished = False
            return {"deleted": index, "remaining": len(rows)}

    def delete_session(self, session_id: str) -> dict:
        if session_id != self.SESSION_ID:
            raise ValueError("unknown training session")
        with self._lock:
            if self.active:
                raise ValueError("採取中は削除できません。先に採取を停止してください")
            count = len(self._read_rows())
            self._write_rows([])
            self.counts = [0] * len(self.targets)
            self.finished = False
            return {"deleted_session": session_id, "deleted_events": count}

    def _write_rows(self, rows: list[dict]) -> None:
        self.events_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.events_path.with_suffix(".tmp")
        temporary.write_text("".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows), encoding="utf-8")
        temporary.replace(self.events_path)

    def status(self) -> dict:
        with self._lock:
            selected = self.targets[self.selected_index] if self.selected_index is not None else None
            per_class = [sum(self.counts[class_id * 5:(class_id + 1) * 5]) for class_id in range(12)]
            completed = sum(self.counts)
            positions = [{**target, "count": self.counts[index],
                          "complete": self.repetitions > 0 and self.counts[index] >= self.repetitions}
                         for index, target in enumerate(self.targets)]
            return {
                "active": self.active, "finished": self.finished, "repetitions": self.repetitions,
                "completed_samples": completed, "total_samples": self.repetitions * len(self.active_indices),
                "samples_per_class": self.repetitions * (len(self.active_indices) // 12), "per_class_counts": per_class,
                "per_position_counts": positions, "current_target_index": self.selected_index,
                "current_class_id": selected["class_id"] if selected else 0,
                "current_point_id": selected["point_id"] if selected else 0,
                "current_point_name": selected["point_name"] if selected else "center",
                "current_x_mm": selected["x_mm"] if selected else 0,
                "current_y_mm": selected["y_mm"] if selected else 0,
                "current_repetition": self.counts[self.selected_index] + 1 if self.selected_index is not None else 0,
                "position_pattern": self.pattern, "panel": PANEL,
            }

    def start_training(self) -> dict:
        raise ValueError("再学習はWeb UIから自動実行しません。採取データを保護し、PC側で明示的に実行してください")
