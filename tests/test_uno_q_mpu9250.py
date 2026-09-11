from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "uno_q_app" / "python"))
from mpu9250_models import FEATURE_COUNT, ModelSuite, extract_features  # noqa: E402
from position_model import PositionModel  # noqa: E402
from training_manager import TrainingManager  # noqa: E402

MODEL_PATH = ROOT / "uno_q_app" / "python" / "mpu9250_models.npz"
METADATA_PATH = ROOT / "uno_q_app" / "python" / "mpu9250_model_metadata.json"
SEED_PATH = ROOT / "uno_q_app" / "python" / "mpu9250_training_seed.npz"
POSITION_ROOT = ROOT / "data" / "position_model_400x300"


def position_model():
    return PositionModel(POSITION_ROOT / "model.npz", POSITION_ROOT / "parity_cases.npz",
                         POSITION_ROOT / "model_metadata.json")


class UnoQMpu9250Tests(unittest.TestCase):
    def test_feature_and_model_contract(self):
        with np.load(SEED_PATH, allow_pickle=False) as seed:
            waveform = seed["waveforms"][0]
        self.assertEqual(extract_features(waveform).shape, (FEATURE_COUNT,))
        result = ModelSuite(MODEL_PATH, METADATA_PATH).predict(waveform)
        self.assertEqual(len(result["class_probabilities"]), 12)
        self.assertEqual(len(result["position_probabilities"]), 60)
        self.assertAlmostEqual(sum(result["class_probabilities"]), 1.0)
        self.assertAlmostEqual(sum(result["position_probabilities"]), 1.0)
        self.assertTrue(0 <= result["x_mm"] <= 400 and 0 <= result["y_mm"] <= 300)

    def test_report_and_all_60_targets(self):
        metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
        self.assertEqual(metadata["event_count"], 7132)
        self.assertGreater(metadata["validation"]["area_accuracy_12class"], .99)
        self.assertGreater(metadata["validation"]["position_top1_accuracy"], .98)
        self.assertLess(metadata["validation"]["pseudo_xy_mae_mm"], 2.0)
        self.assertLess(metadata["validation"]["direct_xy_mae_mm"], 10.0)
        self.assertEqual(metadata["direct_xy_model"]["architecture"], [120, 384, 192, 96, 2])
        self.assertEqual(metadata["direct_xy_model"]["trainable_parameter_count"], 139106)
        suite = ModelSuite(MODEL_PATH, METADATA_PATH)
        for index in range(4):
            self.assertIn(f"xy_w_{index}", suite.arrays)
            self.assertIn(f"xy_b_{index}", suite.arrays)
        with tempfile.TemporaryDirectory() as directory:
            model = position_model()
            manager = TrainingManager(Path(directory), model)
            self.assertEqual(len(manager.targets), 60)
            self.assertEqual({(item["x_mm"], item["y_mm"]) for item in manager.targets},
                             {tuple(map(int, point)) for point in model.support})
            state = manager.start(2, "all60")
            self.assertEqual(state["total_samples"], 120)
            self.assertEqual(state["samples_per_class"], 10)

    def test_static_pages_are_complete(self):
        static = ROOT / "uno_q_app" / "python" / "static"
        for name in ("index.html", "collector.html", "position.html", "instrument.html", "instrument-probability.html", "camera-test.html"):
            self.assertTrue((static / name).is_file())
        collector = (static / "collector.html").read_text(encoding="utf-8")
        self.assertIn("KX134-1211・±32 g・25.6 kHz・512点 / 20 ms", collector)
        self.assertIn("KX134 採取済みデータ", collector)
        self.assertNotIn("trainingStart", collector)
        self.assertNotIn("sync_train_mpu9250", collector)
        self.assertNotIn("25.6 kHz・2,048点", collector)
        collector_js = (static / "app.js").read_text(encoding="utf-8")
        self.assertIn("collection.active ? '採取中' : '採取開始'", collector_js)
        self.assertIn("=== 'corners' ? 10 : 50", collector_js)
        self.assertIn("positionHeatmap", (static / "position.html").read_text(encoding="utf-8"))
        self.assertIn("確率分布", (static / "instrument-probability.html").read_text(encoding="utf-8"))
        probability_html = (static / "instrument-probability.html").read_text(encoding="utf-8")
        probability_js = (static / "instrument-probability.js").read_text(encoding="utf-8")
        self.assertIn('<iframe id="usbCamera"', probability_html)
        self.assertIn('<video id="pcCamera"', probability_html)
        self.assertIn('id="cameraSource"', probability_html)
        self.assertIn('value="pc"', probability_html)
        self.assertIn('value="unoq"', probability_html)
        self.assertIn('id="cameraHeatmapOverlay"', probability_html)
        self.assertIn('<select id="panelProfile" hidden', probability_html)
        self.assertIn('<select id="port" hidden', probability_html)
        self.assertIn('<select id="positionSource" hidden', probability_html)
        self.assertIn('id="inferenceModel"', probability_html)
        self.assertIn('value="fft_standard"', probability_html)
        self.assertIn('value="temporal_cnn"', probability_html)
        self.assertIn('value="temporal_fft_ensemble"', probability_html)
        self.assertIn("const modeForSource=()=> 'inference'", probability_js)
        self.assertIn("/api/inference/model", probability_js)
        self.assertIn("CPU/XNNPACK", probability_js)
        self.assertIn("DEFAULT_CAMERA_STREAM", probability_js)
        self.assertIn("navigator.mediaDevices.getUserMedia", probability_js)
        self.assertIn("CAMERA_SOURCE_KEY", probability_js)
        self.assertIn("calibrationStorageKey", probability_js)
        self.assertIn("CAMERA_ROW_DIVIDERS_KEY", probability_js)
        self.assertIn("rowDividerRatios", probability_js)
        self.assertIn("projectSideRatio", probability_js)
        self.assertIn("mappedSideRatio", probability_js)
        self.assertIn("8点フィット", probability_html)
        self.assertIn("redrawCameraOverlay", probability_js)
        self.assertIn("/api/audio/note.wav", probability_js)
        self.assertIn("playUnoQMedia", probability_js)
        self.assertIn("support.length&&support.length===probability.length", probability_js)
        self.assertIn("map_x_mm??lastRenderedPosition.x_mm", probability_js)
        self.assertIn('id="masterVolume"', probability_html)
        self.assertIn("updateMasterVolume", probability_js)
        self.assertIn("audio=new AudioEngine()", (static / "instrument.js").read_text(encoding="utf-8"))
        self.assertIn('class="card position-stage" hidden', probability_html)
        self.assertIn("localStorage.setItem(DISPLAY_MODE_KEY,'camera')", probability_js)
        self.assertIn("camera-viewport iframe", (static / "position.css").read_text(encoding="utf-8"))
        self.assertIn("camera-viewport iframe", (static / "instrument.css").read_text(encoding="utf-8"))
        self.assertIn('title="UNO Q USBカメラ映像"', (static / "index.html").read_text(encoding="utf-8"))
        camera_embed_js = (static / "camera-embed.js").read_text(encoding="utf-8")
        self.assertIn("acrylicPanUnoQCameraServer", camera_embed_js)
        self.assertIn(":4912/embed", camera_embed_js)
        camera_test = (static / "camera-test.html").read_text(encoding="utf-8")
        self.assertIn("UNO Q USB Camera Test", camera_test)
        self.assertIn(":4912/embed", camera_test)
        dual_camera_script = (ROOT / "scripts" / "run-dual-camera-ui.ps1").read_text(encoding="utf-8-sig")
        self.assertIn("127.0.0.1:8765", dual_camera_script)
        self.assertIn('"-L", "${CameraPort}:127.0.0.1:4912"', dual_camera_script)

    def test_training_library_lists_loads_and_deletes_jsonl_events(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = TrainingManager(Path(directory), position_model())
            manager.start(1, "center")
            stored = manager.record({
                "sequence": 7, "sample_rate_hz": 25600, "trigger_index": 64,
                "peak_abs": 2400, "irq_count": 1,
                "z": [index * 10 for index in range(512)],
            })
            self.assertIsNotNone(stored)
            manager.stop()
            sessions = manager.list_sessions()["sessions"]
            self.assertEqual(sessions[0]["event_count"], 1)
            events = manager.list_events(manager.SESSION_ID)["events"]
            self.assertEqual(events[0]["sequence"], 7)
            payload = manager.load_event(manager.SESSION_ID, 1)
            self.assertEqual(len(payload["samples"]), 512)
            self.assertEqual(len(payload["frequency_hz"]), 257)
            self.assertEqual(payload["stored"]["class_id"], 0)
            self.assertEqual(manager.delete_event(manager.SESSION_ID, 1)["remaining"], 0)
            self.assertEqual(manager.list_sessions()["sessions"], [])

    def test_uno_q_retrigger_guard_matches_original_application_contract(self):
        sketch = (ROOT / "uno_q_app" / "sketch" / "sketch.ino").read_text(encoding="utf-8")
        capture = (ROOT / "uno_q_app" / "sketch" / "apan_capture.cpp").read_text(encoding="utf-8")
        server = (ROOT / "uno_q_app" / "python" / "web_server.py").read_text(encoding="utf-8")
        self.assertIn('Bridge.provide("set_retrigger_guard"', sketch)
        self.assertIn("CONFIRMATION_THRESHOLD", sketch)
        self.assertIn("candidateConfirmed", capture)
        self.assertIn("difference >= jerkThreshold_", capture)
        self.assertIn("magnitude(sample) >= levelThreshold_", capture)
        self.assertIn("self.set_retrigger_guard", server)
        self.assertIn("confirmationThreshold", capture)
        self.assertIn('self.set_sensor_thresholds("collection")', server)
        self.assertIn('self.set_sensor_thresholds("inference")', server)
        self.assertIn("self.training.load_event", server)
        self.assertIn("self.training.delete_event", server)
        self.assertIn("DWT->CYCCNT", sketch)
        self.assertIn("missedDataReady += lateCycles / samplePeriodCycles", sketch)
        self.assertNotIn("SAMPLE_PERIOD_US", sketch)


if __name__ == "__main__":
    unittest.main()
