"""Minimal PNG reader (stdlib only) for verifying screenshots.

Supports what the gallery writes: 8-bit RGBA or RGB, non-interlaced.
"""

from __future__ import annotations

import struct
import zlib
from pathlib import Path
from typing import Union

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class PngError(ValueError):
    """The file is not a PNG this reader supports."""


def _read(path: Union[str, Path]) -> bytes:
    data = Path(path).read_bytes()
    if data[:8] != PNG_SIGNATURE:
        raise PngError(f"{path} is not a PNG file")
    return data


def size(path: Union[str, Path]) -> tuple[int, int]:
    """Returns (width, height)."""
    data = _read(path)
    width, height = struct.unpack(">II", data[16:24])
    return width, height


def decode(path: Union[str, Path]) -> tuple[int, int, int, list[bytearray]]:
    """Returns (width, height, channels, rows) with filters undone."""
    data = _read(path)
    width, height, depth, color, _, _, interlace = struct.unpack(">IIBBBBB", data[16:29])
    channels = {6: 4, 2: 3}.get(color)
    if depth != 8 or channels is None or interlace != 0:
        raise PngError(f"{path}: unsupported PNG (depth {depth}, color type {color}, interlace {interlace})")
    idat = bytearray()
    pos = 8
    while pos < len(data):
        length, kind = struct.unpack(">I4s", data[pos:pos + 8])
        if kind == b"IDAT":
            idat += data[pos + 8:pos + 8 + length]
        pos += 12 + length
    raw = zlib.decompress(bytes(idat))
    stride = width * channels
    rows: list[bytearray] = []
    previous = bytearray(stride)
    for row in range(height):
        start = row * (stride + 1)
        kind = raw[start]
        line = bytearray(raw[start + 1:start + 1 + stride])
        for i in range(stride):
            left = line[i - channels] if i >= channels else 0
            up = previous[i]
            corner = previous[i - channels] if i >= channels else 0
            if kind == 1:
                line[i] = (line[i] + left) & 0xFF
            elif kind == 2:
                line[i] = (line[i] + up) & 0xFF
            elif kind == 3:
                line[i] = (line[i] + (left + up) // 2) & 0xFF
            elif kind == 4:
                guess = left + up - corner
                pa, pb, pc = abs(guess - left), abs(guess - up), abs(guess - corner)
                predictor = left if pa <= pb and pa <= pc else up if pb <= pc else corner
                line[i] = (line[i] + predictor) & 0xFF
            elif kind != 0:
                raise PngError(f"{path}: unknown filter type {kind} on row {row}")
        rows.append(line)
        previous = line
    return width, height, channels, rows


def pixel(path: Union[str, Path], x: int, y: int) -> tuple[int, ...]:
    """Returns the channel values at (x, y)."""
    width, height, channels, rows = decode(path)
    if not (0 <= x < width and 0 <= y < height):
        raise PngError(f"pixel ({x}, {y}) is outside {width}x{height}")
    return tuple(rows[y][x * channels:(x + 1) * channels])


def mean_color(path: Union[str, Path]) -> tuple[float, float, float]:
    """Average RGB over the whole image."""
    width, height, channels, rows = decode(path)
    totals = [0, 0, 0]
    for line in rows:
        for x in range(width):
            base = x * channels
            totals[0] += line[base]
            totals[1] += line[base + 1]
            totals[2] += line[base + 2]
    count = max(width * height, 1)
    return (totals[0] / count, totals[1] / count, totals[2] / count)
