"""DEF sprite decoder conformance vectors (Kotlin ``Def.kt`` contract), from the Python reference.

``generate()`` returns ``{vector file name: JSON-serialisable content}``; the
orchestrator wires it into ``vectors.generate()`` (which owns serialisation).
Python (``defimg.py``) is authoritative (ADR-0004, docs/specs/conformance-def.md).

All DEF files are SYNTHETIC, built here from a fixed ``random.Random`` seed.
Each case holds the file as hex plus the Python result: either ``error`` (the
exception class name) or the parsed container summary with, per frame, the
pixel hash/dimensions, canvas hash and RGBA hashes (small frames also carry the
full pixels and RGBA as hex). ``truncations`` replays ``parse_def`` on every
prefix of a base file.

Usage:  python3 -m h3re.vectors_def [--out DIR]
"""

import hashlib
import os
import random
import struct
import sys

from . import defimg as D

VECTOR_FORMAT = 1
FILE = "def.json"
SMALL_PIXELS = 64


def _sha(b):
    return hashlib.sha256(bytes(b)).hexdigest()


# --------------------------------------------------------------------------
# builders
# --------------------------------------------------------------------------

def make_palette(variant=0):
    """768 palette bytes with the reserved colours at 0-7 (variants vary 2 and 3)."""
    pal = [((i * 37) & 255, (i * 91 + 13) & 255, (i * 53 + 7) & 255) for i in range(256)]
    for i, c in enumerate(D.SPECIAL_COLORS):
        pal[i] = c
    if variant == 1:      # on the tolerance edge (8) for 2 and 3, still matching
        pal[2] = (255 - 8, 100 + 8, 255 - 8)
        pal[3] = (255 - 8, 50 - 8 + 0, 255 - 0)
    elif variant == 2:    # just outside the tolerance (9)
        pal[2] = (255, 100 - 9, 255)
        pal[3] = (255 - 9, 50, 255)
    elif variant == 3:    # mixed: 2 matches, 3 does not; 5 and 6 recoloured
        pal[2] = (250, 104, 252)
        pal[3] = (255, 50 + 9, 255)
        pal[5] = (1, 2, 3)
        pal[6] = (4, 5, 6)
    return b"".join(bytes(c) for c in pal)


def frame_blob(fmt, fw, fh, w, h, x, y, body, size=None):
    return struct.pack("<8I", len(body) if size is None else size, fmt, fw, fh, w, h,
                       x & 0xFFFFFFFF, y & 0xFFFFFFFF) + body


def build_def(blocks, pal, dtype=0x42, w=8, h=4, share=None):
    """blocks: list of (block_id, [(name_bytes, frame_blob)]). Frames with the same
    blob object (``is``) share one offset when ``share`` is true."""
    head = struct.pack("<4I", dtype, w, h, len(blocks)) + pal
    tabs = 0
    for _bid, ents in blocks:
        tabs += 16 + 17 * len(ents)
    off = len(head) + tabs
    parts, blobs, placed = [], b"", {}
    for bid, ents in blocks:
        names = b"".join(n.ljust(13, b"\0")[:13] for n, _ in ents)
        offs = []
        for _n, blob in ents:
            key = id(blob)
            if share and key in placed:
                offs.append(placed[key])
                continue
            offs.append(off + len(blobs))
            placed[key] = off + len(blobs)
            blobs += blob
        parts.append(struct.pack("<4I", bid, len(ents), 0, 0) + names
                     + struct.pack("<%dI" % len(offs), *offs))
    return head + b"".join(parts) + blobs


def _runs(row, fmt):
    """Run-encode one row of indices (fmt 2/3: code7 raw, len<=32; fmt 1: (code,len-1))."""
    out = bytearray()
    i, n = 0, len(row)
    while i < n:
        v = row[i]
        j = i
        lim = 256 if fmt == 1 else 32
        while j < n and row[j] == v and j - i < lim:
            j += 1
        rep = j - i
        ok_fill = v < 7 if fmt != 1 else v != 0xFF
        if ok_fill and (rep >= 2 or i + 1 >= n):
            out += bytes([v, rep - 1]) if fmt == 1 else bytes([(v << 5) | (rep - 1)])
            i = j
            continue
        # raw chunk up to next repeated pair
        k = i + 1
        while k < n and k - i < lim and not (k + 1 < n and row[k] == row[k + 1] and ok_fill_v(row[k], fmt)):
            k += 1
        chunk = row[i:k]
        out += (bytes([0xFF, len(chunk) - 1]) if fmt == 1 else bytes([0xE0 | (len(chunk) - 1)])) + bytes(chunk)
        i = k
    return bytes(out)


def ok_fill_v(v, fmt):
    return v < 7 if fmt != 1 else v != 0xFF


def encode_body(fmt, w, h, px):
    rows = [px[r * w:(r + 1) * w] for r in range(h)]
    if fmt == 0:
        return bytes(px)
    enc = [_runs(r, fmt) for r in rows]
    if fmt == 1:
        base = 4 * h
        offs, pos = [], base
        for e in enc:
            offs.append(pos)
            pos += len(e)
        return struct.pack("<%dI" % h, *offs) + b"".join(enc)
    stride = 2 * (w // 32)
    if fmt == 2:
        return struct.pack("<H", 2) + b"".join(enc)
    base = stride * h
    offs, pos = [], base
    for e in enc:
        offs.append(pos)
        pos += len(e)
    tab = b""
    for o in offs:
        tab += struct.pack("<%dH" % (stride // 2), *([o] * (stride // 2))) if stride else b""
    return tab + b"".join(enc)


def rand_pixels(rnd, n, mode="mixed"):
    out = []
    while len(out) < n:
        k = rnd.randint(1, 40)
        if mode == "special":
            v = rnd.randint(0, 9)
        else:
            v = rnd.choice((0, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, rnd.randint(10, 255)))
        if rnd.random() < 0.5:
            out += [v] * k
        else:
            out += [rnd.randint(0, 255) if rnd.random() < 0.6 else rnd.randint(0, 9) for _ in range(k)]
    return bytes(out[:n])


def legacy_blob(rnd, fw, fh):
    """Legacy format 1 frame: row offsets 0/1 double as w/h and exceed the full size."""
    px = rand_pixels(rnd, fw * fh)
    enc = [_runs(px[r * fw:(r + 1) * fw], 1) for r in range(fh)]
    base = 4 * fh
    offs, pos = [], base
    for e in enc:
        offs.append(pos)
        pos += len(e)
    win = struct.pack("<%dI" % fh, *offs) + b"".join(enc)
    assert offs[0] > fw and offs[1] > fh and len(win) >= 16
    return struct.pack("<4I", len(win) - 16, 1, fw, fh) + win, px


# --------------------------------------------------------------------------
# recording
# --------------------------------------------------------------------------

def _frame_rec(f, pal):
    rec = {
        "name_hex": f.name.encode("latin-1").hex(),
        "offset": f.offset, "size": f.size, "fmt": f.fmt,
        "full_width": f.full_width, "full_height": f.full_height,
        "width": f.width, "height": f.height, "x": f.x, "y": f.y,
        "pixels_sha256": _sha(f.pixels),
    }
    canvas = D.frame_to_canvas(f)
    rec["canvas_sha256"] = _sha(canvas)
    rec["canvas_rgba_sha256"] = _sha(D.to_rgba(canvas, pal))
    rec["canvas_rgba_noshadow_sha256"] = _sha(D.to_rgba(canvas, pal, shadow_alpha=False))
    rec["rgba_sha256"] = _sha(D.to_rgba(f.pixels, pal))
    rec["rgba_noshadow_sha256"] = _sha(D.to_rgba(f.pixels, pal, shadow_alpha=False))
    if f.width * f.height <= SMALL_PIXELS:
        rec["pixels_hex"] = f.pixels.hex()
        rec["rgba_hex"] = D.to_rgba(f.pixels, pal).hex()
    if f.full_width * f.full_height <= SMALL_PIXELS:
        rec["canvas_hex"] = canvas.hex()
        rec["canvas_rgba_hex"] = D.to_rgba(canvas, pal).hex()
    return rec


def result(data, max_pixels=None):
    try:
        d = D.parse_def(data) if max_pixels is None else D.parse_def(data, max_pixels=max_pixels)
    except D.DefError:
        return {"error": "DefError"}
    pal = d.palette
    return {"ok": {
        "type": d.type, "width": d.width, "height": d.height,
        "blocks": [{"id": b.block_id, "frames": [_frame_rec(f, pal) for f in b.frames]}
                   for b in d.blocks],
    }}


def case(name, data, max_pixels=None, note=""):
    c = {"name": name, "hex": bytes(data).hex(), "note": note}
    if max_pixels is not None:
        c["max_pixels"] = max_pixels
    c.update(result(bytes(data), max_pixels))
    return c


def _put(data, off, fmt, val):
    b = bytearray(data)
    b[off:off + struct.calcsize(fmt)] = struct.pack(fmt, val)
    return bytes(b)


# --------------------------------------------------------------------------
# cases
# --------------------------------------------------------------------------

def _format_cases(rnd):
    cases = []
    pal = make_palette(0)

    def one(name, fmt, fw, fh, w, h, x, y, mode="mixed", pal=pal, note=""):
        px = rand_pixels(rnd, w * h, mode)
        body = encode_body(fmt, w, h, px)
        data = build_def([(0, [(b"%s.pcx" % name.encode(), frame_blob(fmt, fw, fh, w, h, x, y, body))])], pal)
        c = case(name, data, note=note)
        if "ok" in c:
            assert bytes.fromhex(c["hex"]) == data
            fr = D.parse_def(data).blocks[0].frames[0]
            assert fr.pixels == px, name
        cases.append(c)

    one("fmt0_small", 0, 8, 4, 8, 4, 0, 0, "special")
    one("fmt0_big", 0, 40, 30, 40, 30, 0, 0)
    one("fmt1_small", 1, 8, 4, 8, 4, 0, 0, "special")
    one("fmt1_long_runs", 1, 300, 5, 300, 5, 0, 0)
    one("fmt2_small", 2, 9, 4, 9, 4, 0, 0, "special")
    one("fmt2_w45", 2, 45, 7, 45, 7, 0, 0)
    one("fmt3_w32", 3, 32, 4, 32, 4, 0, 0)
    one("fmt3_w40_floor_stride", 3, 40, 4, 40, 4, 0, 0)
    one("fmt3_w64", 3, 64, 3, 64, 3, 0, 0)
    one("fmt3_w96", 3, 96, 5, 96, 5, 0, 0)
    one("fmt3_w100", 3, 100, 6, 100, 6, 0, 0)
    # margins
    one("margin_inside", 0, 10, 8, 4, 3, 2, 3, "special")
    one("margin_negative_clip", 0, 6, 6, 5, 5, -2, -3, "special")
    one("margin_right_bottom_clip", 0, 6, 6, 5, 5, 4, 3, "special")
    one("margin_fully_outside", 0, 6, 6, 3, 3, 10, 10, "special")
    one("margin_fully_outside_neg", 0, 6, 6, 3, 3, -20, -20, "special")
    one("margin_extreme", 0, 6, 6, 3, 3, -2147483648, 2147483647, "special")
    one("image_wider_than_canvas_only", 0, 3, 8, 6, 4, 0, 0, "special")
    one("image_taller_than_canvas_only_fmt1", 1, 8, 3, 4, 6, 1, 1, "special")
    one("zero_width", 0, 5, 5, 0, 4, 0, 0)
    one("zero_height_fmt2", 2, 5, 5, 4, 0, 0, 0)
    one("zero_canvas", 0, 0, 0, 3, 3, 0, 0)
    one("zero_all_fmt3", 3, 0, 0, 0, 0, 0, 0)
    # format 3 with w < 32: stride 0, every row reads the same first u16 (quirk)
    px_row = bytes([1, 1, 1, 9, 9, 2, 2, 2, 2, 8])
    row = _runs(px_row, 2)
    body = struct.pack("<H", 2) + row
    data = build_def([(0, [(b"stride0.pcx", frame_blob(3, 10, 3, 10, 3, 0, 0, body))])], pal)
    cases.append(case("fmt3_w10_stride0_rows_repeat", data,
                      note="stride 0: all rows decode from the first row's data"))
    # format 2: only the first u16 is read
    body = struct.pack("<2H", 4, 0xFFFF) + bytes([(2 << 5) | 3]) + bytes([(5 << 5) | 3])
    cases.append(case("fmt2_first_u16_only", build_def(
        [(0, [(b"f2.pcx", frame_blob(2, 4, 2, 4, 2, 0, 0, body))])], pal)))
    # legacy format 1
    for i, (fw, fh) in enumerate(((5, 4), (12, 6), (3, 5))):
        blob, px = legacy_blob(rnd, fw, fh)
        data = build_def([(0, [(b"leg%d.pcx" % i, blob)])], pal)
        c = case("legacy_fmt1_%d" % i, data, note="w,h come from row offsets 0/1")
        if "ok" in c:
            f = c["ok"]["blocks"][0]["frames"][0]
            assert (f["width"], f["height"], f["x"], f["y"]) == (fw, fh, 0, 0)
            assert D.parse_def(data).blocks[0].frames[0].pixels == px
        cases.append(c)
    # w > fw but h <= fh: not legacy (plain format 1)
    px = rand_pixels(rnd, 6 * 2)
    body = encode_body(1, 6, 2, px)
    cases.append(case("fmt1_w_gt_fw_only_not_legacy", build_def(
        [(0, [(b"nl.pcx", frame_blob(1, 3, 4, 6, 2, 1, 1, body))])], pal)))
    # palettes: special indices
    for v in range(4):
        px = bytes(range(10)) * 2 + bytes([2, 3, 2, 3, 0, 5, 6, 7, 8, 9, 255, 1])
        body = encode_body(0, 8, 4, px)
        cases.append(case("special_palette_variant_%d" % v, build_def(
            [(0, [(b"sp.pcx", frame_blob(0, 8, 4, 8, 4, 0, 0, body))])], make_palette(v))))
    # exact per-channel tolerance sweep on index 2 and 3 (diff 0..10, each channel)
    sweep = []
    for ch in range(3):
        for d in range(0, 11):
            for sign in (1, -1):
                pal2 = [list(c) for c in (make_palette(0)[i * 3:i * 3 + 3] for i in range(256))]
                pal2 = [list(make_palette(0)[i * 3:i * 3 + 3]) for i in range(256)]
                for idx in (2, 3):
                    ref = list(D.SPECIAL_COLORS[idx])
                    ref[ch] = max(0, min(255, ref[ch] + sign * d))
                    pal2[idx] = ref
                pb = b"".join(bytes(c) for c in pal2)
                body = encode_body(0, 2, 1, bytes([2, 3]))
                sweep.append(case("tolerance_ch%d_d%d_s%d" % (ch, d, sign), build_def(
                    [(0, [(b"t.pcx", frame_blob(0, 2, 1, 2, 1, 0, 0, body))])], pb)))
    cases += sweep
    return cases


def _structure_cases(rnd):
    cases = []
    pal = make_palette(3)
    # shared offsets and multiple blocks
    f_a = frame_blob(0, 4, 2, 4, 2, 0, 0, bytes(range(1, 9)))
    f_b = frame_blob(2, 8, 2, 8, 2, 1, 1, encode_body(2, 8, 2, rand_pixels(rnd, 16)))
    f_c = frame_blob(1, 5, 5, 5, 5, 0, 0, encode_body(1, 5, 5, rand_pixels(rnd, 25)))
    data = build_def([(7, [(b"A0", f_a), (b"A1", f_a), (b"B", f_b)]),
                      (0xFFFFFFFF, [(b"A2", f_a), (b"C", f_c), (b"B2", f_b)]),
                      (3, [])], pal, share=True)
    cases.append(case("shared_offsets_multi_block", data))
    # high bytes and un-terminated 13 char name, text after the NUL
    names = [b"\xe9\xe8\xff.pcx", b"ABCDEFGHIJKLM", b"ab\0cd", b""]
    data = build_def([(1, [(n, frame_blob(0, 1, 1, 1, 1, 0, 0, bytes([i + 1])))
                           for i, n in enumerate(names)])], pal)
    cases.append(case("names_latin1_nonul_embedded_nul", data))
    # no blocks at all, and a block with no entries
    cases.append(case("no_blocks", build_def([], pal, dtype=0x40, w=0, h=0)))
    # size field larger than data actually used (trailing slack inside window): ok
    body = encode_body(1, 4, 1, bytes([3, 3, 4, 5]))
    cases.append(case("fmt1_size_slack", build_def(
        [(0, [(b"s.pcx", frame_blob(1, 4, 1, 4, 1, 0, 0, body + b"\0" * 6))])], pal)))
    # frame-level bytes after the file's last frame (trailing garbage) is ignored
    cases.append(case("trailing_garbage", build_def(
        [(0, [(b"s.pcx", frame_blob(0, 1, 1, 1, 1, 0, 0, b"\x05"))])], pal) + b"\xde\xad"))
    # frame offsets overlapping another frame's bytes (frame b points into frame a)
    return cases


def _bad_cases(rnd, base):
    """Targeted malformed inputs derived from small valid files."""
    pal = make_palette(0)
    cases = []

    def single(fmt, fw, fh, w, h, x, y, body, size=None):
        return build_def([(0, [(b"x.pcx", frame_blob(fmt, fw, fh, w, h, x, y, body, size))])], pal)

    good0 = single(0, 4, 2, 4, 2, 0, 0, bytes(range(8)))
    hdr = 16 + 768
    cases += [
        case("empty_input", b""),
        case("short_header", b"\x00" * 15),
        case("palette_truncated", good0[:16 + 767]),
        case("blocks_257", _put(good0, 12, "<I", 257)),
        case("blocks_256_missing", _put(good0, 12, "<I", 256)),
        case("blocks_huge", _put(good0, 12, "<I", 0xFFFFFFFF)),
        case("entries_4097", _put(good0, hdr + 4, "<I", 4097)),
        case("entries_4096_missing", _put(good0, hdr + 4, "<I", 4096)),
        case("entries_zero_but_data", _put(good0, hdr + 4, "<I", 0)),
        case("frame_offset_past_end", _put(good0, hdr + 16 + 13, "<I", len(good0))),
        case("frame_offset_huge", _put(good0, hdr + 16 + 13, "<I", 0xFFFFFFFF)),
        case("frame_offset_into_header", _put(good0, hdr + 16 + 13, "<I", 5)),
        case("frame_offset_last_header_byte", _put(good0, hdr + 16 + 13, "<I", len(good0) - 8 - 31)),
    ]
    fo = hdr + 16 + 13 + 4  # first frame offset
    cases += [
        case("fmt_4", _put(good0, fo + 4, "<I", 4)),
        case("fmt_huge", _put(good0, fo + 4, "<I", 0xFFFFFFFF)),
        case("fullw_8193", _put(good0, fo + 8, "<I", 8193)),
        case("fullh_8193", _put(good0, fo + 12, "<I", 8193)),
        case("w_8193", _put(good0, fo + 16, "<I", 8193)),
        case("h_huge", _put(good0, fo + 20, "<I", 0xFFFFFFFF)),
        case("size_gt_file", _put(good0, fo, "<I", 1000)),
        case("size_huge", _put(good0, fo, "<I", 0xFFFFFFFF)),
        case("raw_size_lt_wh", _put(good0, fo, "<I", 7)),
        case("raw_size_gt_wh", _put(good0, fo, "<I", 9)),
        case("raw_size_zero", _put(good0, fo, "<I", 0)),
    ]
    # RLE faults
    cases += [
        case("fmt1_run_overruns_line", single(1, 4, 1, 4, 1, 0, 0, struct.pack("<I", 4) + bytes([1, 99]))),
        case("fmt1_line_offset_oob", single(1, 4, 1, 4, 1, 0, 0, struct.pack("<I", 1000) + bytes([1, 3]))),
        case("fmt1_line_offset_huge", single(1, 4, 1, 4, 1, 0, 0, struct.pack("<I", 0xFFFFFFFF) + bytes([1, 3]))),
        case("fmt1_line_offset_back_into_table", single(1, 2, 2, 2, 2, 0, 0, struct.pack("<2I", 0, 0) + bytes([1, 1]))),
        case("fmt1_raw_run_truncated", single(1, 4, 1, 4, 1, 0, 0, struct.pack("<I", 4) + bytes([0xFF, 3, 1, 2]))),
        case("fmt1_size_only_table", single(1, 4, 1, 4, 1, 0, 0, struct.pack("<I", 4) + bytes([5, 3]), size=4)),
        case("fmt1_table_truncated", single(1, 4, 3, 4, 3, 0, 0, struct.pack("<2I", 8, 8))),
        case("fmt2_run_overruns", single(2, 4, 1, 4, 1, 0, 0, struct.pack("<H", 2) + bytes([(1 << 5) | 7]))),
        case("fmt2_first_offset_oob", single(2, 4, 1, 4, 1, 0, 0, struct.pack("<H", 500) + bytes([(1 << 5) | 3]))),
        case("fmt2_only_one_byte_body", single(2, 4, 1, 4, 1, 0, 0, b"\x02")),
        case("fmt2_raw_truncated", single(2, 4, 1, 4, 1, 0, 0, struct.pack("<H", 2) + bytes([0xE3, 1, 2]))),
        case("fmt2_second_row_missing", single(2, 4, 2, 4, 2, 0, 0, struct.pack("<H", 2) + bytes([(1 << 5) | 3]))),
        case("fmt3_row_offset_oob", single(3, 32, 1, 32, 1, 0, 0, struct.pack("<H", 900) + bytes([(1 << 5) | 31]))),
        case("fmt3_run_overruns", single(3, 32, 1, 32, 1, 0, 0, struct.pack("<H", 2) + bytes([(1 << 5) | 31, (1 << 5) | 0]))),
        case("fmt3_table_truncated", single(3, 64, 3, 64, 3, 0, 0, struct.pack("<2H", 8, 9))),
        case("fmt3_ok_exact", single(3, 32, 1, 32, 1, 0, 0, struct.pack("<H", 2) + bytes([(4 << 5) | 31]))),
    ]
    # legacy bad: window bigger than the file
    blob, _ = legacy_blob(rnd, 5, 4)
    blob = _put(blob, 0, "<I", 100000)
    cases.append(case("legacy_size_lie", build_def([(0, [(b"l.pcx", blob)])], pal)))
    blob, _ = legacy_blob(rnd, 5, 4)
    blob = _put(blob, 0, "<I", 0)  # window is only 16 bytes: rows lie outside
    cases.append(case("legacy_size_zero", build_def([(0, [(b"l.pcx", blob)])], pal)))
    # pixel budget (explicit max_pixels)
    a = frame_blob(0, 4, 2, 4, 2, 0, 0, bytes(8))
    b = frame_blob(0, 4, 2, 4, 2, 0, 0, bytes(range(8)))
    two = build_def([(0, [(b"a", a), (b"b", b)])], pal)
    cases += [case("budget_exact_16", two, max_pixels=16),
              case("budget_15", two, max_pixels=15),
              case("budget_0", two, max_pixels=0),
              case("budget_zero_pixel_frame", build_def([(0, [(b"a", frame_blob(0, 4, 4, 0, 0, 0, 0, b""))])], pal),
                   max_pixels=0),
              case("budget_shared_charged_once", build_def([(0, [(b"a", a)] * 50)], pal, share=True), max_pixels=8),
              case("budget_default_ok", two)]
    # legacy frames are charged for the full size
    leg, _ = legacy_blob(rnd, 12, 6)
    legd = build_def([(0, [(b"l", leg)])], pal)
    cases += [case("budget_legacy_72", legd, max_pixels=72), case("budget_legacy_71", legd, max_pixels=71)]
    # RLE bomb: 8192x8192 from tiny data (fits the default budget exactly, truncated
    # rows then fail or pass depending on the data; Python decides)
    line = bytes([0, 255]) * 32
    bomb_body = b"".join(struct.pack("<I", 4 * 8192) for _ in range(8192)) + line
    bomb = frame_blob(1, 8192, 8192, 8192, 8192, 0, 0, bomb_body)
    cases.append(case("rle_bomb_shared_100_budget_1000",
                      build_def([(0, [(b"b%d" % i, bomb) for i in range(100)])], pal, share=True),
                      max_pixels=1000))
    cases.append(case("rle_bomb_budget_1000_single",
                      build_def([(0, [(b"b", bomb)])], pal), max_pixels=1000))
    # two distinct bombs of 8192x8192: second exceeds the default 64M budget
    bomb2 = frame_blob(1, 8192, 8192, 8192, 8192, 0, 0, bomb_body + b"\0")
    two_b = build_def([(0, [(b"b1", bomb), (b"b2", bomb2)])], pal)
    cases.append(case("rle_two_bombs_default_budget", two_b, note="1st decodes 64M px, 2nd exceeds budget"))
    return cases


def _random_corruptions(rnd, data, n):
    """Single/multi-byte corruptions of a valid file; Python decides each result."""
    out = []
    for i in range(n):
        b = bytearray(data)
        for _ in range(rnd.randint(1, 3)):
            p = rnd.randrange(len(b))
            b[p] = rnd.randrange(256)
        out.append(case("corrupt_%03d" % i, bytes(b)))
    return out


def generate():
    rnd = random.Random(0xDEF5)
    cases = _format_cases(rnd) + _structure_cases(rnd)
    cases += _bad_cases(rnd, None)

    # a rich base file holding every format for truncation and corruption sweeps
    pal = make_palette(3)
    ents = []
    for i, (fmt, fw, fh, w, h, x, y) in enumerate(
            ((0, 6, 4, 5, 3, 1, 1), (1, 9, 4, 9, 4, 0, 0), (2, 10, 3, 10, 3, 0, 0),
             (3, 40, 3, 40, 3, 0, 0), (3, 32, 2, 32, 2, 0, 0))):
        px = rand_pixels(rnd, w * h)
        ents.append((b"R%d.pcx" % i, frame_blob(fmt, fw, fh, w, h, x, y, encode_body(fmt, w, h, px))))
    leg, _ = legacy_blob(rnd, 5, 4)
    ents.append((b"LEG.pcx", leg))
    base = build_def([(0, ents[:3]), (1, ents[3:])], pal)
    cases.append(case("truncation_base", base))
    cases += _random_corruptions(rnd, base, 120)

    trunc = []
    for cut in range(len(base) + 1):
        r = result(base[:cut])
        trunc.append([cut, "error" if "error" in r else "ok"])
    # an ok truncation also carries its frame count to catch partial parses
    for t in trunc:
        if t[1] == "ok":
            r = result(base[:t[0]])["ok"]
            t.append(sum(len(b["frames"]) for b in r["blocks"]))
    return {FILE: {
        "format_version": VECTOR_FORMAT,
        "constants": {
            "max_blocks": D.MAX_BLOCKS, "max_entries": D.MAX_ENTRIES, "max_dim": D.MAX_DIM,
            "max_total_pixels": D.MAX_TOTAL_PIXELS, "color_tolerance": D.COLOR_TOLERANCE,
            "overlay_index": D.OVERLAY_INDEX,
            "special_colors": [list(c) for c in D.SPECIAL_COLORS],
            "special_alpha": [-1 if a is None else a for a in D.SPECIAL_ALPHA],
        },
        "cases": cases,
        "truncation_base_hex": base.hex(),
        "truncations": trunc,
    }}


def main(argv=None):
    import argparse
    from . import vectors as V
    ap = argparse.ArgumentParser(prog="python3 -m h3re.vectors_def")
    ap.add_argument("--out", default=V.DEFAULT_OUT)
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    for name, obj in generate().items():
        with open(os.path.join(a.out, name), "wb") as f:
            f.write(V._dump(obj))
        print("wrote", os.path.join(a.out, name))
    return 0


if __name__ == "__main__":
    sys.exit(main())
