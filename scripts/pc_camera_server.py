"""Serve a Windows webcam as MJPEG for embedding in the UNO Q web UI."""

from __future__ import annotations

import argparse
import json
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cv2


VIEWER = b"""<!doctype html><html lang=\"ja\"><head><meta charset=\"utf-8\">
<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>PC Camera Stream</title>
<style>*{box-sizing:border-box}html,body{margin:0;width:100%;height:100%;background:#071018;color:#eaf2f7;font-family:sans-serif}main{display:grid;grid-template-rows:auto 1fr;height:100%;padding:10px;gap:8px}header{display:flex;justify-content:space-between;align-items:center}h1{font-size:16px;margin:0}span{color:#7cf4c1}figure{display:grid;place-items:center;margin:0;min-height:0;overflow:hidden;border-radius:8px;background:#020507}img{display:block;width:100%;height:100%;object-fit:contain;transform:scaleX(-1)}</style>
</head><body><main><header><h1>PC Camera / MJPEG</h1><span>Local development utility</span></header>
<figure><img src=\"/stream.mjpg\" alt=\"PC webcam stream\"></figure></main></body></html>"""


class Camera:
    def __init__(self, index: int, width: int, height: int, fps: int, quality: int):
        self.condition = threading.Condition()
        self.frame: bytes | None = None
        self.sequence = 0
        self.error: str | None = None
        self.quality = quality
        self.capture = self._open(index, width, height, fps)
        threading.Thread(target=self._run, name="pc-camera-capture", daemon=True).start()

    @staticmethod
    def _open(index: int, width: int, height: int, fps: int):
        for backend in (cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY):
            capture = cv2.VideoCapture(index, backend)
            if not capture.isOpened():
                capture.release()
                continue
            capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            capture.set(cv2.CAP_PROP_FPS, fps)
            capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
            return capture
        raise RuntimeError(f"camera index {index} could not be opened")

    def _run(self) -> None:
        while True:
            ok, image = self.capture.read()
            if not ok:
                self.error = "camera frame read failed"
                time.sleep(.05)
                continue
            ok, encoded = cv2.imencode(".jpg", image, (cv2.IMWRITE_JPEG_QUALITY, self.quality))
            if not ok:
                continue
            with self.condition:
                self.frame = encoded.tobytes()
                self.sequence += 1
                self.error = None
                self.condition.notify_all()

    def wait(self, after: int, timeout: float = 2.0) -> tuple[int, bytes | None]:
        with self.condition:
            self.condition.wait_for(lambda: self.sequence != after, timeout)
            return self.sequence, self.frame


class Handler(BaseHTTPRequestHandler):
    camera: Camera

    def log_message(self, format: str, *args) -> None:
        return

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path == "/":
            return self._send(VIEWER, "text/html; charset=utf-8")
        if path == "/health":
            body = json.dumps({"ok": self.camera.frame is not None, "sequence": self.camera.sequence,
                               "error": self.camera.error}).encode()
            return self._send(body, "application/json")
        if path == "/snapshot.jpg":
            _, frame = self.camera.wait(-1)
            return self._send(frame or b"", "image/jpeg",
                              HTTPStatus.OK if frame else HTTPStatus.SERVICE_UNAVAILABLE)
        if path == "/stream.mjpg":
            return self._stream()
        self.send_error(HTTPStatus.NOT_FOUND)

    def _send(self, body: bytes, content_type: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers(); self.wfile.write(body)

    def _stream(self) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        sequence = -1
        try:
            while True:
                sequence, frame = self.camera.wait(sequence)
                if frame is None:
                    continue
                self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: " +
                                 str(len(frame)).encode() + b"\r\n\r\n" + frame + b"\r\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            return


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8878)
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--quality", type=int, default=80)
    args = parser.parse_args()
    camera = Camera(args.camera, args.width, args.height, args.fps, args.quality)
    handler = type("PcCameraHandler", (Handler,), {"camera": camera})
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"PC camera: http://127.0.0.1:{args.port}/", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
