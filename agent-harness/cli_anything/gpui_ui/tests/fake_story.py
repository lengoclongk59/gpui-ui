"""Test double of the story automation server, for unit tests only.

Speaks the same JSON Lines protocol as `crates/story/src/automation.rs` with a
tiny in-memory gallery. E2E tests use the real application instead.
"""

from __future__ import annotations

import json
import socketserver
import struct
import threading
import zlib
from typing import Any

ELEMENTS = [
    ("disabled", "button", "Disabled", True, None),
    ("notifications", "switch", "Notifications", False, True),
    ("primary", "button", "Primary", False, None),
    ("toggle-theme", "button", "Dark mode", False, None),
]


def encode_png(width: int, height: int, rgba: tuple[int, int, int, int], filter_type: int = 0) -> bytes:
    """Encodes a solid-color RGBA PNG using one filter type for every row."""
    row = bytes(rgba) * width
    raw = bytearray()
    previous = bytes(len(row))
    for _ in range(height):
        raw.append(filter_type)
        encoded = bytearray(len(row))
        for i, value in enumerate(row):
            left = row[i - 4] if i >= 4 else 0
            up = previous[i]
            corner = previous[i - 4] if i >= 4 else 0
            if filter_type == 0:
                predictor = 0
            elif filter_type == 1:
                predictor = left
            elif filter_type == 2:
                predictor = up
            elif filter_type == 3:
                predictor = (left + up) // 2
            else:
                guess = left + up - corner
                pa, pb, pc = abs(guess - left), abs(guess - up), abs(guess - corner)
                predictor = left if pa <= pb and pa <= pc else up if pb <= pc else corner
            encoded[i] = (value - predictor) & 0xFF
        raw += encoded
        previous = row

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(bytes(raw))) + chunk(b"IEND", b"")


class FakeGallery:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.clicks = 0
        self.notifications = True
        self.theme = "light"
        self.requests: list[dict[str, Any]] = []

    def state(self) -> dict[str, Any]:
        items = []
        for index, (element_id, kind, label, disabled, checked) in enumerate(ELEMENTS):
            if element_id == "notifications":
                checked = self.notifications
            if element_id == "toggle-theme":
                label = "Light mode" if self.theme == "dark" else "Dark mode"
            items.append({
                "id": element_id, "kind": kind, "label": label, "disabled": disabled, "checked": checked,
                "bounds": {"x": 10.0 + 100 * index, "y": 20.0, "width": 80.0, "height": 36.0},
            })
        return {
            "theme": self.theme,
            "gallery": {"clicks": self.clicks, "notifications": self.notifications},
            "elements": items,
        }

    def handle(self, request: dict[str, Any]) -> dict[str, Any]:
        self.requests.append(request)
        cmd = request.get("cmd")
        ids = [item[0] for item in ELEMENTS]
        if cmd == "ping":
            return {"ok": True, "result": {"app": "gpui-ui-story", "version": "0.0.0-fake", "protocol": 1}}
        if cmd == "state":
            return {"ok": True, "result": self.state()}
        if cmd in {"click", "hover"}:
            element_id = request.get("id")
            if element_id not in ids:
                return {"ok": False, "error": f"no element with id `{element_id}`; known ids: {', '.join(ids)}"}
            if cmd == "click":
                if element_id == "primary":
                    self.clicks += 1
                elif element_id == "notifications":
                    self.notifications = not self.notifications
                elif element_id == "toggle-theme":
                    self.theme = "dark" if self.theme == "light" else "light"
            return {"ok": True, "result": self.state()}
        if cmd == "set_theme":
            if request.get("mode") not in {"light", "dark"}:
                return {"ok": False, "error": "invalid request: unknown theme"}
            self.theme = request["mode"]
            return {"ok": True, "result": self.state()}
        if cmd == "screenshot":
            element_id = request.get("id")
            if element_id is not None and element_id not in ids:
                return {"ok": False, "error": f"no element with id `{element_id}`; known ids: {', '.join(ids)}"}
            width, height = (80, 36) if element_id else (200, 100)
            color = (37, 99, 235, 255) if element_id == "primary" else (255, 255, 255, 255)
            with open(request["path"], "wb") as handle:
                handle.write(encode_png(width, height, color))
            return {"ok": True, "result": {"path": request["path"], "width": width, "height": height}}
        if cmd == "quit":
            return {"ok": True, "result": {"quitting": True}}
        return {"ok": False, "error": f"invalid request: unknown cmd {cmd!r}"}


class _Handler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        gallery: FakeGallery = self.server.gallery  # type: ignore[attr-defined]
        for line in self.rfile:
            if not line.strip():
                continue
            try:
                request = json.loads(line)
            except json.JSONDecodeError as error:
                response = {"ok": False, "error": f"invalid request: {error}"}
            else:
                with gallery.lock:
                    response = gallery.handle(request)
            self.wfile.write((json.dumps(response) + "\n").encode("utf-8"))
            self.wfile.flush()


class FakeStory:
    """Runs a fake automation server on a free loopback port."""

    def __init__(self) -> None:
        self.gallery = FakeGallery()
        self.server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), _Handler)
        self.server.daemon_threads = True
        self.server.gallery = self.gallery  # type: ignore[attr-defined]
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self) -> "FakeStory":
        self.thread.start()
        return self

    def __exit__(self, *exc: Any) -> None:
        self.server.shutdown()
        self.server.server_close()
