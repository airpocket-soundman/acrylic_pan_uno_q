"""Build a single-file Story preview with every image embedded as a data URI.

The editable source keeps relative ``assets/`` paths. The generated file can be
opened from anywhere (mail, chat, previews that load pages as data URLs).
"""
from __future__ import annotations

import base64
import mimetypes
import re
from pathlib import Path

DOCS = Path(__file__).resolve().parents[1] / "docs"
SOURCE = DOCS / "hackster-story-ja.html"
TARGET = DOCS / "hackster-story-ja.standalone.html"


def embed(match: re.Match[str]) -> str:
    path = DOCS / match.group(1)
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f'src="data:{mime};base64,{data}"'


def main() -> None:
    html = SOURCE.read_text(encoding="utf-8")
    html = re.sub(r'src="(assets/[^"]+)"', embed, html)
    TARGET.write_text(html, encoding="utf-8")
    print(f"{TARGET} ({TARGET.stat().st_size / 1_000_000:.1f} MB)")


if __name__ == "__main__":
    main()
