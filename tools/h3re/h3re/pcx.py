"""Clean-room parser for the HoMM3 PCX bitmap variant (stdlib only).

See docs/specs/pcx.md for the layout.  All reads are bounds-checked and raise
PcxError on malformed data.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Optional

from .defimg import write_png

__all__ = ["PcxError", "PcxImage", "parse_pcx", "MODE_INDEXED", "MODE_BGR24"]

MODE_INDEXED = "indexed"  # 8-bit palette indices + 256 x RGB palette
MODE_BGR24 = "bgr24"      # 24-bit pixels, stored channel order BGR (confirmed)

MAX_DIM = 8192
HEADER_SIZE = 12
PALETTE_SIZE = 768


class PcxError(ValueError):
    """Raised when a PCX bitmap is malformed."""


@dataclass
class PcxImage:
    width: int
    height: int
    mode: str                  # MODE_INDEXED or MODE_BGR24
    pixels: bytes              # row-major; indices (indexed) or BGR triples (bgr24)
    palette: Optional[list]    # 256 (r, g, b) tuples for indexed, else None

    def to_rgb(self) -> bytes:
        """Return packed 8-bit RGB pixels (width*height*3 bytes, row-major)."""
        if self.mode == MODE_INDEXED:
            pal = self.palette
            out = bytearray()
            for p in self.pixels:
                out += bytes(pal[p])
            return bytes(out)
        if self.mode == MODE_BGR24:
            # Swap B and R.  Stored channel order is BGR (see docs/specs/pcx.md).
            px = self.pixels
            out = bytearray(len(px))
            out[0::3] = px[2::3]
            out[1::3] = px[1::3]
            out[2::3] = px[0::3]
            return bytes(out)
        raise PcxError(f"unknown mode {self.mode!r}")

    def to_png(self) -> bytes:
        """Return PNG bytes (8-bit RGB) via defimg.write_png."""
        return write_png(self.width, self.height, self.to_rgb(), channels=3)


def parse_pcx(data: bytes) -> PcxImage:
    """Parse a HoMM3 PCX bitmap from bytes."""
    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise PcxError("data must be bytes-like")
    data = bytes(data)
    if len(data) < HEADER_SIZE:
        raise PcxError(f"truncated header: need {HEADER_SIZE} bytes, "
                       f"have {len(data)}")
    size, width, height = struct.unpack_from("<3I", data, 0)
    if width == 0 or height == 0:
        raise PcxError(f"empty image dimensions {width}x{height}")
    if width > MAX_DIM or height > MAX_DIM:
        raise PcxError(f"dimensions {width}x{height} exceed cap {MAX_DIM}")

    n = width * height
    body = HEADER_SIZE
    if size == n:
        need = body + n + PALETTE_SIZE
        if len(data) < need:
            raise PcxError(f"truncated indexed data: need {need} bytes, "
                           f"have {len(data)}")
        # The palette is always the LAST 768 bytes of the file, as the engine
        # reads it. Bytes between the pixels and the palette are not used.
        pixels = data[body:body + n]
        pal_raw = data[-PALETTE_SIZE:]
        palette = [tuple(pal_raw[i * 3:i * 3 + 3]) for i in range(256)]
        return PcxImage(width, height, MODE_INDEXED, pixels, palette)
    if size == 3 * n:
        need = body + size
        if len(data) < need:
            raise PcxError(f"truncated 24-bit data: need {need} bytes, "
                           f"have {len(data)}")
        return PcxImage(width, height, MODE_BGR24, data[body:need], None)
    raise PcxError(f"data size {size} matches neither {n} (indexed) nor "
                   f"{3 * n} (24-bit) for {width}x{height}")
