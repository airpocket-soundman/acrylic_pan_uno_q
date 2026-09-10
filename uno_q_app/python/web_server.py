from __future__ import annotations

import json
import mimetypes
import threading
import time
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


class Handler(SimpleHTTPRequestHandler):
    static_root: Path
    get_status: object
    update_runtime: object
    run_demo: object
    training: object
    synthesize_audio: object
    set_retrigger_guard: object
    set_sensor_thresholds: object

    def __init__(self, *args, **kwargs): super().__init__(*args, directory=str(self.static_root), **kwargs)
    def log_message(self, format: str, *args) -> None: return
    def _json(self, value, status=HTTPStatus.OK):
        body = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status); self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store"); self.send_header("Content-Length", str(len(body)))
        self.end_headers(); self.wfile.write(body)
    def _latest(self): return self.get_status().get("latest_ai") or {}
    def _event(self):
        latest = self._latest(); event = dict(latest.get("event") or {})
        if event:
            event["samples"] = event.get("z", []); event["source"] = latest.get("source", "mpu9250_capture")
            event["sequence"] = latest.get("sequence", event.get("sequence"))
        return event

    def do_GET(self):
        parsed = urlparse(self.path); path = parsed.path
        if path == "/api/status": return self._json(self.get_status())
        if path == "/api/audio/note.wav":
            options = {name: values[-1] for name, values in parse_qs(parsed.query).items()}
            body = self.synthesize_audio(options)
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "audio/wav")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Audio-Synth", "UNO-Q")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers(); self.wfile.write(body); return
        if path == "/api/ports": return self._json({"ports": ["UNO Q internal SPI"]})
        if path == "/api/ai/latest": return self._json(self._latest())
        if path == "/api/events/latest": return self._json(self._event())
        if path == "/api/ai/wait":
            query = parse_qs(parsed.query); after = (query.get("after") or [None])[0]
            timeout = min(float((query.get("timeout") or ["1"])[0]), 5.0); deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                latest = self._latest()
                if latest and str(latest.get("sequence")) != str(after): return self._json(latest)
                time.sleep(.02)
            return self._json({})
        if path in ("/api/collection", "/api/session"): return self._json(self.training.status())
        if path == "/api/collection/targets":
            pattern = (parse_qs(parsed.query).get("pattern") or ["all60"])[0]
            targets = [target for target in self.training.targets if pattern == "all60" or
                       (pattern == "center" and target["point_id"] == 4) or
                       (pattern == "corners" and target["point_id"] < 4)]
            return self._json({"targets": targets, "panel": self.get_status()["panel"], "position_pattern": pattern})
        if path == "/api/training/status": return self._json(dict(self.training.training))
        if path == "/api/health": return self._json({"ok": True, "sensor_ready": self.get_status()["sensor_ready"]})
        if path == "/api/library/sessions": return self._json(self.training.list_sessions())
        if path == "/api/library/events":
            query = parse_qs(parsed.query)
            return self._json(self.training.list_events((query.get("session") or [""])[0]))
        if path == "/api/library/event":
            query = parse_qs(parsed.query)
            return self._json(self.training.load_event(
                (query.get("session") or [""])[0], int((query.get("index") or ["0"])[0])))
        if path in ("/", "/index.html"): self.path = "/index.html"
        return super().do_GET()

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            length = int(self.headers.get("Content-Length", "0")); body = json.loads(self.rfile.read(length) or b"{}")
            if path == "/api/connect": return self._json(self.update_runtime(connected=True))
            if path == "/api/disconnect": return self._json(self.update_runtime(connected=False, inference_active=False))
            if path == "/api/device/mode": return self._json(self.update_runtime(device_mode=str(body.get("mode", "inference"))))
            if path == "/api/inference/start":
                return self._json(self.update_runtime(inference_active=True, device_mode=str(body.get("mode", "inference"))))
            if path == "/api/inference/stop": return self._json(self.update_runtime(inference_active=False))
            if path == "/api/inference/retrigger":
                return self._json(self.set_retrigger_guard(int(body["milliseconds"])))
            if path == "/api/panel": return self._json(self.get_status())
            if path in ("/api/demo", "/api/ai/selftest"): return self._json(self.run_demo(int(body.get("case_id", 0))))
            if path == "/api/collection/start":
                self.update_runtime(device_mode="collection", inference_active=False)
                self.set_sensor_thresholds("collection")
                return self._json(self.training.start(int(body.get("repetitions", 10)), str(body.get("position_pattern", "corners"))))
            if path == "/api/collection/select": return self._json(self.training.select(int(body["target_index"])))
            if path == "/api/collection/stop":
                result = self.training.stop()
                self.set_sensor_thresholds("inference")
                self.update_runtime(device_mode="inference")
                return self._json(result)
            if path == "/api/collection/undo": return self._json(self.training.undo())
            if path == "/api/training/start": return self._json(self.training.start_training(), HTTPStatus.ACCEPTED)
            if path == "/api/library/delete":
                return self._json(self.training.delete_event(str(body.get("session", "")), int(body["index"])))
            if path == "/api/library/delete_session":
                return self._json(self.training.delete_session(str(body.get("session", ""))))
            if path == "/api/command": return self._json({"ok": True, "command": body.get("command")})
            return self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)
        except (KeyError, TypeError, ValueError, OSError) as error:
            return self._json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
        except Exception as error:
            return self._json({"error": str(error)}, HTTPStatus.INTERNAL_SERVER_ERROR)


def start_web_server(static_root: Path, get_status, update_runtime, run_demo, training,
                     synthesize_audio, set_retrigger_guard, set_sensor_thresholds, port: int = 8765):
    handler = type("AcrylicPanHandler", (Handler,), {"static_root": static_root,
        "get_status": staticmethod(get_status), "update_runtime": staticmethod(update_runtime),
        "run_demo": staticmethod(run_demo), "training": training,
        "synthesize_audio": staticmethod(synthesize_audio),
        "set_retrigger_guard": staticmethod(set_retrigger_guard),
        "set_sensor_thresholds": staticmethod(set_sensor_thresholds)})
    server = ThreadingHTTPServer(("0.0.0.0", port), handler)
    threading.Thread(target=server.serve_forever, name="apan-web", daemon=True).start(); return server
