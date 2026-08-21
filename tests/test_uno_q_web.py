import json
import threading
import unittest
from urllib.request import urlopen

from pc.uno_q_web.server import create_server


class FakeSource:
    def snapshot(self):
        result = {
            "case_id": 11,
            "expected_class": 11,
            "predicted_class": 11,
            "passed": True,
            "scores": [0.0] * 11 + [1.0],
            "inference_us": 8200,
            "created_at_unix_ns": 1_787_275_836_365_034_001,
            "model": "acrylic_pan_time128_h32_12class_v1",
        }
        return {
            "connected": True,
            "app_running": True,
            "device": "uno-test",
            "mode": "dummy",
            "sensor_connected": False,
            "model": result["model"],
            "latest": result,
            "history": [result],
            "sample_count": 1,
            "pass_count": 1,
            "accuracy": 1.0,
            "latency_us": {"latest": 8200, "average": 8200, "maximum": 8200},
            "error": None,
        }


class UnoQWebTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = create_server("127.0.0.1", 0, FakeSource())
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_status_api(self):
        with urlopen(self.base + "/api/status", timeout=2) as response:
            payload = json.load(response)
        self.assertTrue(payload["connected"])
        self.assertEqual(payload["latest"]["predicted_class"], 11)

    def test_static_dashboard(self):
        with urlopen(self.base + "/", timeout=2) as response:
            html = response.read().decode("utf-8")
        self.assertIn("UNO Q Live Console", html)
        self.assertIn("4 × 3", html)
        self.assertIn('href="/docs"', html)

    def test_documentation_portal(self):
        with urlopen(self.base + "/docs", timeout=2) as response:
            html = response.read().decode("utf-8")
        self.assertIn("ARDUINO UNO Q PROJECT", html)
        self.assertIn('data-page="bom"', html)
        self.assertIn('data-page="uno-q-wiring"', html)
        self.assertIn('data-page="simulation-calculix-5mm"', html)

        with urlopen(self.base + "/web/pages/bom.html", timeout=2) as response:
            bom = response.read().decode("utf-8")
        self.assertIn("61201421721", bom)

        with urlopen(self.base + "/web/pages/uno-q-wiring.html", timeout=2) as response:
            wiring = response.read().decode("utf-8")
        self.assertIn("D10 / SS / PB9", wiring)
        self.assertIn("5 Vへ接続しない", wiring)

        with urlopen(self.base + "/web/pages/overview.html", timeout=2) as response:
            overview = response.read().decode("utf-8")
        self.assertIn('href="../../docs#bom"', overview)
        self.assertIn('href="../../docs#uno-q-wiring"', overview)

        with urlopen(self.base + "/web/pages/experiment.html", timeout=2) as response:
            experiment = response.read().decode("utf-8")
        self.assertIn("固定60点", experiment)
        self.assertIn("中心12点", experiment)
        self.assertIn("四隅48点", experiment)

    def test_original_simulation_asset_is_served(self):
        path = "/web/assets/simulation/5mm-400x300/calculix/model-metadata.json"
        with urlopen(self.base + path, timeout=2) as response:
            metadata = json.load(response)
        self.assertIsInstance(metadata, dict)


if __name__ == "__main__":
    unittest.main()
