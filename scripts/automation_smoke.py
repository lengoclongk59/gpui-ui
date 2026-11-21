"""End-to-end smoke test of the gallery automation server.

Starts `story --automation --port 0`, drives every protocol command against the
real window and checks the results. Uses only the standard library.

Usage: py -3 -I scripts/automation_smoke.py [--exe PATH] [--out DIR]
"""

import argparse
import json
import pathlib
import socket
import struct
import subprocess
import sys
import tempfile
import zlib

REPO = pathlib.Path(__file__).resolve().parent.parent
EXE_NAME = "story.exe" if sys.platform == "win32" else "story"
DEFAULT_EXE = REPO / "target" / "debug" / EXE_NAME


class Client:
    """A JSON Lines client for one automation connection."""

    def __init__(self, port):
        self.sock = socket.create_connection(("127.0.0.1", port), timeout=30)
        self.reader = self.sock.makefile("r", encoding="utf-8")

    def call(self, cmd, **params):
        line = json.dumps({"cmd": cmd, **params}) + "\n"
        self.sock.sendall(line.encode("utf-8"))
        reply = self.reader.readline()
        if not reply:
            raise RuntimeError(f"server closed the connection during {cmd!r}")
        return json.loads(reply)

    def ok(self, cmd, **params):
        response = self.call(cmd, **params)
        if not response["ok"]:
            raise AssertionError(f"{cmd} failed: {response['error']}")
        return response["result"]

    def close(self):
        self.reader.close()
        self.sock.close()


def element(state, element_id):
    for item in state["elements"]:
        if item["id"] == element_id:
            return item
    raise AssertionError(f"element {element_id!r} missing from state")


def png_size(path):
    data = pathlib.Path(path).read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n", f"{path} is not a PNG"
    width, height = struct.unpack(">II", data[16:24])
    return width, height


def png_pixel(path, x, y):
    """Returns the RGBA pixel at (x, y) of an 8-bit RGBA, non-interlaced PNG."""
    data = pathlib.Path(path).read_bytes()
    width, height, depth, color = struct.unpack(">IIBB", data[16:26])
    assert (depth, color) == (8, 6), "expected an 8-bit RGBA PNG"
    pos, idat = 8, b""
    while pos < len(data):
        length, kind = struct.unpack(">I4s", data[pos:pos + 8])
        if kind == b"IDAT":
            idat += data[pos + 8:pos + 8 + length]
        pos += 12 + length
    raw = zlib.decompress(idat)
    stride = width * 4
    rows, previous = [], bytearray(stride)
    for row in range(height):
        start = row * (stride + 1)
        kind, line = raw[start], bytearray(raw[start + 1:start + 1 + stride])
        for i in range(stride):
            left = line[i - 4] if i >= 4 else 0
            up = previous[i]
            corner = previous[i - 4] if i >= 4 else 0
            if kind == 1:
                line[i] = (line[i] + left) & 0xFF
            elif kind == 2:
                line[i] = (line[i] + up) & 0xFF
            elif kind == 3:
                line[i] = (line[i] + (left + up) // 2) & 0xFF
            elif kind == 4:
                guess = left + up - corner
                pa, pb, pc = abs(guess - left), abs(guess - up), abs(guess - corner)
                pred = left if pa <= pb and pa <= pc else up if pb <= pc else corner
                line[i] = (line[i] + pred) & 0xFF
        rows.append(line)
        previous = line
    return tuple(rows[y][x * 4:x * 4 + 4])


def run(exe, out_dir):
    process = subprocess.Popen(
        [str(exe), "--automation", "--port", "0"],
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        ready = json.loads(process.stdout.readline())
        assert ready["event"] == "listening", ready
        client = Client(ready["port"])
        check(client, out_dir)
        assert client.ok("quit") == {"quitting": True}
        client.close()
        assert process.wait(timeout=10) == 0, "story should exit cleanly after quit"
    finally:
        if process.poll() is None:
            process.kill()


def check(client, out_dir):
    ping = client.ok("ping")
    assert ping["app"] == "gpui-ui-story" and ping["protocol"] == 1, ping
    print("ping ok", ping)

    state = client.ok("state")
    assert state["theme"] == "light", state["theme"]
    assert state["gallery"] == {"clicks": 0, "notifications": True}, state["gallery"]
    ids = [item["id"] for item in state["elements"]]
    assert ids == sorted(ids), "elements must be sorted by id"
    for expected in ["primary", "disabled", "notifications", "toggle-theme"]:
        assert expected in ids, f"{expected} missing: {ids}"
    assert element(state, "primary")["bounds"]["width"] > 0
    print("state ok:", len(ids), "elements")

    for _ in range(3):
        state = client.ok("click", id="primary")
    assert state["gallery"]["clicks"] == 3, state["gallery"]
    print("click primary x3 ok")

    state = client.ok("click", id="disabled")
    assert state["gallery"]["clicks"] == 3, "a disabled button must ignore clicks"
    print("disabled button ignores clicks ok")

    state = client.ok("click", id="notifications")
    assert state["gallery"]["notifications"] is False
    assert element(state, "notifications")["checked"] is False
    state = client.ok("click", id="switch-disabled")
    assert element(state, "switch-disabled")["checked"] is True
    print("switch toggles, disabled switch stays ok")

    state = client.ok("click", id="toggle-theme")
    assert state["theme"] == "dark", state["theme"]
    assert element(state, "toggle-theme")["label"] == "Light mode"
    state = client.ok("set_theme", mode="light")
    assert state["theme"] == "light"
    print("theme toggle and set_theme ok")

    client.ok("hover", id="danger")
    print("hover ok")

    error = client.call("click", id="nope")
    assert not error["ok"] and "known ids" in error["error"], error
    error = client.call("explode")
    assert not error["ok"] and "invalid request" in error["error"], error
    print("errors ok")

    full = out_dir / "gallery.png"
    shot = client.ok("screenshot", path=str(full))
    assert png_size(full) == (shot["width"], shot["height"]), shot
    primary = out_dir / "primary.png"
    shot = client.ok("screenshot", path=str(primary), id="primary")
    width, height = png_size(primary)
    assert 0 < width < 400 and 0 < height < 100, (width, height)
    red, green, blue, _ = png_pixel(primary, width // 8, height // 2)
    assert blue > 150 and red < 120, f"primary should be blue, got {(red, green, blue)}"
    print("screenshots ok:", full, primary)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--exe", type=pathlib.Path, default=DEFAULT_EXE)
    parser.add_argument("--out", type=pathlib.Path)
    args = parser.parse_args()
    if not args.exe.exists():
        sys.exit(f"{args.exe} not found; run `cargo build -p story` first")
    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
        run(args.exe, args.out)
    else:
        with tempfile.TemporaryDirectory() as out:
            run(args.exe, pathlib.Path(out))
    print("ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
