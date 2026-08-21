"""Dependency-free USB/ADB dashboard server for Acrylic Pan UNO Q."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import webbrowser
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Protocol
from urllib.parse import urlparse


APP_CONTAINER = "acrylic-pan-dummy-main-1"
RESULT_PATH = "data/inference/dummy_results.jsonl"
STATIC_ROOT = Path(__file__).with_name("static")


class SnapshotSource(Protocol):
    def snapshot(self) -> dict: ...


def find_adb() -> Path | None:
    command = shutil.which("adb")
    if command:
        return Path(command)
    local = Path(os.environ.get("LOCALAPPDATA", ""))
    package_root = local / "Microsoft" / "WinGet" / "Packages"
    if package_root.is_dir():
        matches = sorted(package_root.glob("Google.PlatformTools_*/platform-tools/adb.exe"))
        if matches:
            return matches[-1]
    return None


@dataclass
class AdbSnapshotSource:
    adb: Path | None = None
    device: str | None = None
    limit: int = 96

    def __post_init__(self) -> None:
        self.adb = self.adb or find_adb()

    def _run(self, arguments: list[str], timeout: float = 4.0) -> str:
        if self.adb is None:
            raise RuntimeError("adb.exeが見つかりません。Google.PlatformToolsを導入してください。")
        command = [str(self.adb)]
        if self.device:
            command.extend(["-s", self.device])
        completed = subprocess.run(
            [*command, *arguments],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
        if completed.returncode:
            message = completed.stderr.strip() or completed.stdout.strip() or "ADB command failed"
            raise RuntimeError(message)
        return completed.stdout

    def _device_info(self) -> tuple[str, str]:
        output = self._run(["devices", "-l"])
        devices = [line for line in output.splitlines()[1:] if " device " in f" {line} "]
        if not devices:
            raise RuntimeError("USB接続されたUNO QをADBで検出できません。")
        line = devices[0]
        serial = line.split()[0]
        return serial, line

    def _results(self) -> list[dict]:
        output = self._run([
            "shell", "docker", "exec", APP_CONTAINER,
            "tail", "-n", str(self.limit), RESULT_PATH,
        ])
        results = []
        for line in output.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict) and "predicted_class" in item:
                results.append(item)
        return results

    def snapshot(self) -> dict:
        try:
            serial, detail = self._device_info()
            results = self._results()
            latest = results[-1] if results else None
            passed = sum(bool(item.get("passed")) for item in results)
            latencies = [int(item["inference_us"]) for item in results if "inference_us" in item]
            return {
                "connected": True,
                "app_running": True,
                "device": serial,
                "device_detail": detail,
                "mode": "dummy",
                "sensor_connected": False,
                "model": latest.get("model", "apan_dummy_128x32x8") if latest else "apan_dummy_128x32x8",
                "latest": latest,
                "history": results[-32:],
                "sample_count": len(results),
                "pass_count": passed,
                "accuracy": passed / len(results) if results else None,
                "latency_us": {
                    "latest": latencies[-1] if latencies else None,
                    "average": round(sum(latencies) / len(latencies)) if latencies else None,
                    "maximum": max(latencies) if latencies else None,
                },
                "error": None,
            }
        except (RuntimeError, subprocess.TimeoutExpired) as error:
            return {
                "connected": False,
                "app_running": False,
                "device": None,
                "mode": "dummy",
                "sensor_connected": False,
                "model": "apan_dummy_128x32x8",
                "latest": None,
                "history": [],
                "sample_count": 0,
                "pass_count": 0,
                "accuracy": None,
                "latency_us": {"latest": None, "average": None, "maximum": None},
                "error": str(error),
            }


class DashboardHandler(BaseHTTPRequestHandler):
    source: SnapshotSource

    def log_message(self, format: str, *args) -> None:
        return

    def _json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _static(self, path: str) -> None:
        names = {"/": "index.html", "/app.js": "app.js", "/style.css": "style.css"}
        name = names.get(path)
        if name is None:
            self.send_error(404)
            return
        target = STATIC_ROOT / name
        body = target.read_bytes()
        content_type = {
            ".html": "text/html; charset=utf-8",
            ".js": "text/javascript; charset=utf-8",
            ".css": "text/css; charset=utf-8",
        }[target.suffix]
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/status":
            self._json(self.source.snapshot())
        elif path == "/api/health":
            self._json({"ok": True})
        else:
            self._static(path)


def create_server(host: str, port: int, source: SnapshotSource) -> ThreadingHTTPServer:
    handler = type("BoundDashboardHandler", (DashboardHandler,), {"source": source})
    return ThreadingHTTPServer((host, port), handler)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--device")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    server = create_server(args.host, args.port, AdbSnapshotSource(device=args.device))
    url = f"http://{args.host}:{server.server_port}/"
    print(f"Acrylic Pan UNO Q dashboard: {url}")
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
