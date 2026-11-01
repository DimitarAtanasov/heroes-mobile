"""Clean-room parser for the HoMM3 .DEF sprite container (stdlib only).

See docs/specs/def.md for the layout.  All reads are bounds-checked and raise
DefError on malformed data.
"""
from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass, field, replace

__all__ = ["DefError", "EmptyImageError", "Frame", "Block", "DefFile",
           "parse_def", "frame_to_canvas", "frame_is_empty", "frame_to_png",
           "to_rgba", "to_rgb", "write_png", "write_ppm", "MAX_TOTAL_PIXELS",
           "SPECIAL_COLORS", "SPECIAL_ALPHA", "OVERLAY_INDEX", "COLOR_TOLERANCE"]

MAX_BLOCKS = 256
MAX_ENTRIES = 4096
MAX_DIM = 8192
# Default budget of decoded pixels (summed over distinct frames) per file.
MAX_TOTAL_PIXELS = 64 * 1024 * 1024


# Special palette indices: only 0-7 are reserved (8 and up are ordinary colours).
SPECIAL_COLORS = ((0, 255, 255), (255, 150, 255), (255, 100, 255), (255, 50, 255),
                  (255, 0, 255), (255, 255, 0), (180, 0, 255), (0, 255, 0))
# Target alpha per special index (None = leave opaque palette colour).
SPECIAL_ALPHA = (0, 64, 64, 128, 128, None, 128, 64)
# Indices whose alpha applies only if the palette colour matches SPECIAL_COLORS.
_CONDITIONAL = (2, 3)
COLOR_TOLERANCE = 8  # max per-channel difference (inclusive) for a match
OVERLAY_INDEX = 5    # selection / owner-flag overlay; kept as opaque palette colour


class DefError(ValueError):
    """Raised when a .DEF file is malformed."""


class EmptyImageError(ValueError):
    """Raised when asked to encode an image with a zero dimension."""


class _Reader:
    def __init__(self, data: bytes):
        self.data = data

    def check(self, off: int, n: int, what: str) -> None:
        if off < 0 or n < 0 or off + n > len(self.data):
            raise DefError(f"truncated data reading {what}: need {n} bytes at "
                           f"offset {off}, file size {len(self.data)}")

    def u32(self, off: int, what: str) -> int:
        self.check(off, 4, what)
        return struct.unpack_from("<I", self.data, off)[0]

    def i32(self, off: int, what: str) -> int:
        self.check(off, 4, what)
        return struct.unpack_from("<i", self.data, off)[0]

    def u16(self, off: int, what: str) -> int:
        self.check(off, 2, what)
        return struct.unpack_from("<H", self.data, off)[0]

    def u8(self, off: int, what: str) -> int:
        self.check(off, 1, what)
        return self.data[off]

    def raw(self, off: int, n: int, what: str) -> bytes:
        self.check(off, n, what)
        return self.data[off:off + n]


@dataclass
class Frame:
    name: str
    offset: int
    size: int
    fmt: int
    full_width: int
    full_height: int
    width: int
    height: int
    x: int
    y: int
    pixels: bytes  # width*height palette indices (row-major)


@dataclass
class Block:
    block_id: int
    frames: list = field(default_factory=list)


@dataclass
class DefFile:
    type: int
    width: int
    height: int
    palette: list  # 256 (r, g, b) tuples
    blocks: list


def _decode_runs(r: _Reader, pos: int, count: int, out: bytearray, what: str) -> None:
    """Format 2/3 run decoding: append exactly `count` pixels; return the end position."""
    got = 0
    while got < count:
        b = r.u8(pos, what)
        pos += 1
        code = b >> 5
        n = (b & 0x1F) + 1
        if got + n > count:
            raise DefError(f"{what}: run overruns line ({got}+{n} > {count})")
        if code == 7:
            out += r.raw(pos, n, what)
            pos += n
        else:
            out += bytes([code]) * n
        got += n
    return pos


def _decode_frame(r: _Reader, off: int, name: str, budget: list) -> Frame:
    size = r.u32(off, "frame size")
    fmt = r.u32(off + 4, "frame format")
    fw = r.u32(off + 8, "frame full width")
    fh = r.u32(off + 12, "frame full height")
    w = r.u32(off + 16, "frame width")
    h = r.u32(off + 20, "frame height")
    x = r.i32(off + 24, "frame x")
    y = r.i32(off + 28, "frame y")
    if fmt > 3:
        raise DefError(f"frame {name!r}: unknown compression format {fmt}")
    for v in (fw, fh, w, h):
        if v > MAX_DIM:
            raise DefError(f"frame {name!r}: dimension {v} too large")
    # Legacy format-1 quirk: frame larger than the canvas in both directions.
    # Margins are ignored, the image is the full size, and the pixel data
    # begins 16 bytes earlier (the header is only 16 bytes long).
    legacy = fmt == 1 and w > fw and h > fh
    dstart = off + 32
    if legacy:
        w, h, x, y = fw, fh, 0, 0
        dstart = off + 16
    # `size` is the length of the pixel data following the 32-byte header.
    # Confine all decoding to that window so it is validated against what is
    # actually read (and cannot read neighbouring frames).
    r.check(off + 32, size, f"frame {name!r} data (declared size)")
    if fmt == 0 and size != w * h:
        raise DefError(f"frame {name!r}: raw size {size} != width*height {w * h}")
    npix = w * h
    if npix > budget[0]:
        raise DefError(f"frame {name!r}: decoded pixel budget exceeded "
                       f"({npix} > {budget[0]} remaining)")
    budget[0] -= npix
    r = _Reader(r.raw(dstart, size + (off + 32 - dstart), "frame data"))
    base = 0
    out = bytearray()
    if w == 0 or h == 0:
        pass
    elif fmt == 0:
        out += r.raw(base, w * h, "raw frame pixels")
    elif fmt == 1:
        for row in range(h):
            lo = r.u32(base + 4 * row, "line offset")
            pos = base + lo
            got = 0
            while got < w:
                code = r.u8(pos, "rle code")
                n = r.u8(pos + 1, "rle length") + 1
                pos += 2
                if got + n > w:
                    raise DefError(f"frame {name!r}: run overruns line {row}")
                if code == 0xFF:
                    out += r.raw(pos, n, "rle raw run")
                    pos += n
                else:
                    out += bytes([code]) * n
                got += n
    elif fmt == 2:
        # Only the first u16 of the whole frame is read; rows then follow
        # one another sequentially.
        pos = base + r.u16(base, "line offset")
        for row in range(h):
            pos = _decode_runs(r, pos, w, out, f"frame {name!r} line {row}")
    else:  # fmt == 3
        # Offset table row stride is 2*(w//32) bytes (floor); only the first
        # u16 of each row is read, then the row is decoded sequentially.
        stride = 2 * (w // 32)
        for row in range(h):
            lo = r.u16(base + stride * row, "line offset")
            _decode_runs(r, base + lo, w, out, f"frame {name!r} line {row}")
    return Frame(name, off, size, fmt, fw, fh, w, h, x, y, bytes(out))


def parse_def(data: bytes, max_pixels: int = MAX_TOTAL_PIXELS) -> DefFile:
    """Parse a .DEF file from bytes.

    Frames referenced by several entries (same offset) are decoded once and
    share their pixel buffer.  The total pixels decoded across distinct frames
    may not exceed `max_pixels`, otherwise DefError is raised.
    """
    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise DefError("data must be bytes-like")
    r = _Reader(bytes(data))
    dtype = r.u32(0, "type")
    width = r.u32(4, "width")
    height = r.u32(8, "height")
    nblocks = r.u32(12, "block count")
    if nblocks > MAX_BLOCKS:
        raise DefError(f"implausible block count {nblocks}")
    pal_raw = r.raw(16, 768, "palette")
    palette = [tuple(pal_raw[i * 3:i * 3 + 3]) for i in range(256)]
    pos = 16 + 768
    blocks = []
    budget = [max_pixels]
    cache = {}
    for _ in range(nblocks):
        bid = r.u32(pos, "block id")
        n = r.u32(pos + 4, "block entry count")
        if n > MAX_ENTRIES:
            raise DefError(f"implausible entry count {n} in block {bid}")
        pos += 16  # id, count, 2 unknown u32
        names = []
        for i in range(n):
            raw = r.raw(pos + 13 * i, 13, "frame name")
            names.append(raw.split(b"\0", 1)[0].decode("latin-1"))
        pos += 13 * n
        offs = [r.u32(pos + 4 * i, "frame offset") for i in range(n)]
        pos += 4 * n
        block = Block(bid)
        for nm, fo in zip(names, offs):
            fr = cache.get(fo)
            if fr is None:
                fr = cache[fo] = _decode_frame(r, fo, nm, budget)
            block.frames.append(replace(fr, name=nm))
        blocks.append(block)
    return DefFile(dtype, width, height, palette, blocks)


def frame_to_canvas(frame: Frame, transparent: int = 0) -> bytes:
    """Place the frame on its full_width x full_height canvas (indices).

    Uncovered pixels are filled with `transparent`.  Parts outside the canvas
    are clipped.
    """
    fw, fh = frame.full_width, frame.full_height
    canvas = bytearray([transparent]) * (fw * fh)
    for row in range(frame.height):
        cy = frame.y + row
        if not 0 <= cy < fh:
            continue
        x0 = max(0, frame.x)
        x1 = min(fw, frame.x + frame.width)
        if x0 >= x1:
            continue
        src = row * frame.width + (x0 - frame.x)
        canvas[cy * fw + x0:cy * fw + x1] = frame.pixels[src:src + (x1 - x0)]
    return bytes(canvas)


def frame_is_empty(frame: Frame) -> bool:
    """True if the frame (or its canvas) has a zero dimension."""
    return (frame.width == 0 or frame.height == 0
            or frame.full_width == 0 or frame.full_height == 0)


def frame_to_png(frame: Frame, palette, canvas: bool = True):
    """Encode a frame as RGBA PNG, or return None if it is empty.

    With canvas=True the full_width x full_height canvas is used, otherwise
    just the width x height image.
    """
    if frame_is_empty(frame):
        return None
    if canvas:
        return write_png(frame.full_width, frame.full_height,
                         to_rgba(frame_to_canvas(frame), palette))
    return write_png(frame.width, frame.height, to_rgba(frame.pixels, palette))


def to_rgb(pixels: bytes, palette) -> bytes:
    out = bytearray()
    for p in pixels:
        out += bytes(palette[p])
    return bytes(out)


def _matches(rgb, ref) -> bool:
    return all(abs(a - b) <= COLOR_TOLERANCE for a, b in zip(rgb, ref))


def to_rgba(pixels: bytes, palette, shadow_alpha: bool = True) -> bytes:
    """Convert indices to RGBA.

    Index 0 is fully transparent.  With shadow_alpha, special indices become
    semi-transparent black with the alphas in SPECIAL_ALPHA (1:64, 2:64,
    3:128, 4:128, 6:128, 7:64); indices 2 and 3 only when the palette colour
    is within COLOR_TOLERANCE per channel of SPECIAL_COLORS[index].  Index 5
    (OVERLAY_INDEX, selection/owner-flag overlay) and all indices >= 8 keep
    their opaque palette colour.
    """
    out = bytearray()
    for p in pixels:
        if p == 0:
            out += b"\0\0\0\0"
            continue
        a = SPECIAL_ALPHA[p] if shadow_alpha and p < 8 else None
        if a is not None and p in _CONDITIONAL and not _matches(palette[p], SPECIAL_COLORS[p]):
            a = None
        if a is None:
            out += bytes(palette[p]) + b"\xff"
        else:
            out += bytes([0, 0, 0, a])
    return bytes(out)


def write_ppm(width: int, height: int, rgb: bytes) -> bytes:
    """Return binary PPM (P6) bytes."""
    if len(rgb) != width * height * 3:
        raise ValueError("rgb length does not match dimensions")
    return b"P6\n%d %d\n255\n" % (width, height) + bytes(rgb)


def write_png(width: int, height: int, data: bytes, channels: int = 4) -> bytes:
    """Return PNG bytes for 8-bit RGB (channels=3) or RGBA (channels=4) data."""
    if channels not in (3, 4):
        raise ValueError("channels must be 3 or 4")
    if width == 0 or height == 0:
        raise EmptyImageError(f"cannot encode empty image ({width}x{height}); "
                              "use frame_is_empty()/frame_to_png() to skip")
    if width < 0 or height < 0:
        raise ValueError("dimensions must be positive")
    if len(data) != width * height * channels:
        raise ValueError("data length does not match dimensions")
    stride = width * channels
    raw = b"".join(b"\0" + data[y * stride:(y + 1) * stride] for y in range(height))

    def chunk(tag: bytes, body: bytes) -> bytes:
        c = struct.pack(">I", len(body)) + tag + body
        return c + struct.pack(">I", zlib.crc32(tag + body) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6 if channels == 4 else 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))
