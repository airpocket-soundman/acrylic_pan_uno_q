from __future__ import annotations

import json
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse


class AcrylicPanHandler(SimpleHTTPRequestHandler):
    static_root: Path
    get_status: Callable[[], dict]
    run_demo: Callable[[int], dict]
    run_self_test: Callable[[], list[dict]]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(self.static_root), **kwargs)

    def log_message(self, format: str, *args) -> None:
        return

    def send_json(self, payload: object, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/status":
            self.send_json(self.get_status())
            return
        if path == "/api/self-test":
            self.send_json({"cases": self.run_self_test()})
            return
        if path in ("/", "/index.html"):
            self.path = "/position.html"
        super().do_GET()

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path.startswith("/api/demo/"):
            try:
                case_id = int(path.rsplit("/", 1)[-1])
            except ValueError:
                self.send_json({"error": "invalid case id"}, 400)
                return
            self.send_json(self.run_demo(case_id))
            return
        self.send_json({"error": "not found"}, 404)


def start_web_server(
    static_root: Path,
    get_status: Callable[[], dict],
    run_demo: Callable[[int], dict],
    run_self_test: Callable[[], list[dict]],
    port: int = 8765,
) -> ThreadingHTTPServer:
    handler = type(
        "ConfiguredAcrylicPanHandler",
        (AcrylicPanHandler,),
        {
            "static_root": static_root,
            "get_status": staticmethod(get_status),
            "run_demo": staticmethod(run_demo),
            "run_self_test": staticmethod(run_self_test),
        },
    )
    server = ThreadingHTTPServer(("0.0.0.0", port), handler)
    threading.Thread(target=server.serve_forever, name="apan-web", daemon=True).start()
    return server
