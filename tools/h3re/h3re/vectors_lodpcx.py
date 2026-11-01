"""LOD archive and PCX bitmap conformance vectors (battle-independent, synthetic only).

``generate()`` returns ``{vector file name: JSON-serialisable content}``; the
orchestrator wires it into ``vectors.generate()`` (which owns serialisation).
Python is authoritative (ADR-0004, ADR-0007). Every archive and bitmap here is
built in memory from synthetic bytes: no game data is read or written.

Each expectation is produced by running the Python reader (``h3re.lod`` and
``h3re.pcx``) on the case bytes, so the Kotlin port must reproduce it exactly.

Error categories used in the vectors:
  ``LodFormatError``  ``h3re.lod.LodFormatError`` (open or read)
  ``KeyError``        an unknown member name (``LodArchive.read``)
  ``PcxError``        ``h3re.pcx.PcxError``

``lod.json``: ``{"format", "cases": [...]}``. A case is
``{"name", "hex", "strict", "expect"}``. ``expect`` is ``{"open": "LodFormatError"}``
when the archive is refused, otherwise ``{"open": "ok", "list": [...],
"members": [...], "missing": NAME}``. A member is ``{"name", "lookup", "offset",
"size", "type", "packed", "data": hex}`` or, when the payload is refused,
``{..., "error": "LodFormatError"}``. ``lookup`` is the name in lower case and must
read the same member.

``pcx.json``: ``{"format", "cases": [...]}``. A case is ``{"name", "hex",
"expect"}``. ``expect`` is ``{"ok": false, "error": "PcxError"}`` or ``{"ok": true,
"width", "height", "mode", "pixels": hex, "palette": hex | null, "rgb": hex}``.

Usage (through the orchestrator): ``python3 -m h3re.vectors``.
"""

import io
import struct
import zlib

from .lod import ENTRY_SIZE, HEADER_SIZE, MAX_ENTRIES, LodArchive, LodFormatError
from .pcx import PcxError, parse_pcx

VECTOR_FORMAT = 1
LOD_FILE = "lod.json"
PCX_FILE = "pcx.json"
MAGIC = b"LOD\x00"


# --------------------------------------------------------------------------
# LOD builders (synthetic)
# --------------------------------------------------------------------------

def _member(name, data, *, compress=False, type_=1):
    """(name bytes, stored bytes, size, type, packed) for a regular member."""
    if compress:
        stored = zlib.compress(data)
        return (name, stored, len(data), type_, len(stored))
    return (name, data, len(data), type_, 0)


def _lod(members, *, magic=MAGIC, count=None, tail=b""):
    """Assemble an archive. Offsets are computed; ``count`` may be overridden."""
    n = len(members)
    start = HEADER_SIZE + n * ENTRY_SIZE
    directory = bytearray()
    payload = bytearray()
    for name, stored, size, type_, packed in members:
        directory += struct.pack("<16sIIII", name, start + len(payload), size, type_, packed)
        payload += stored
    header = magic + struct.pack("<II", 200, n if count is None else count) + bytes(80)
    return bytes(header) + bytes(directory) + bytes(payload) + tail


def _patch_u32(blob, pos, value):
    out = bytearray(blob)
    struct.pack_into("<I", out, pos, value)
    return bytes(out)


def _entry_pos(index, field):
    """Byte position of a directory field: field 0 offset, 1 size, 2 type, 3 packed."""
    return HEADER_SIZE + index * ENTRY_SIZE + 16 + 4 * field


SAMPLE = [
    _member(b"DEF_ONE.DEF", b"raw payload bytes"),
    _member(b"TEXT.TXT", b"hello world " * 50, compress=True),
    _member(b"EMPTY.BIN", b""),
]

BASE = [
    _member(b"A.BIN", b"abc"),
    _member(b"B.TXT", b"hello hello hello", compress=True),
]


def _oracle(blob, strict):
    """Expectation for an archive, from the Python reader."""
    try:
        arc = LodArchive(io.BytesIO(blob), len(blob), strict=strict)
    except LodFormatError:
        return {"open": "LodFormatError"}
    with arc:
        names = arc.list()
        members = []
        for name in names:
            e = arc.entry(name)
            m = {
                "name": e.name,
                "lookup": e.name.lower(),
                "offset": e.offset,
                "size": e.size,
                "type": e.type,
                "packed": e.packed_size,
            }
            try:
                m["data"] = arc.read(e.name).hex()
            except LodFormatError:
                m["error"] = "LodFormatError"
            members.append(m)
        try:
            arc.read("NOPE.TXT")
        except KeyError:
            pass
        else:  # pragma: no cover - the reader must not invent members
            raise AssertionError("NOPE.TXT unexpectedly present")
        return {"open": "ok", "list": names, "members": members, "missing": "NOPE.TXT"}


def _lod_cases():
    cases = []

    def add(name, blob, strict=False):
        cases.append({"name": name, "hex": blob.hex(), "strict": strict,
                      "expect": _oracle(blob, strict)})

    # ---- valid archives
    add("valid_mixed_raw_compressed_empty", _lod(SAMPLE))
    add("valid_empty_archive", _lod([]))
    add("valid_type_field_opaque", _lod([_member(b"T.BIN", b"xy", type_=0xFFFFFFFF)]))
    add("valid_name_nul_truncated", _lod([_member(b"AB\x00ZZZ", b"x")]))
    add("valid_name_16_bytes_no_nul", _lod([_member(b"ABCDEFGHIJKLMNOP", b"x")]))
    add("valid_latin1_name", _lod([_member(b"\xe9clair.txt", b"latin")]))
    add("valid_empty_compressed_member", _lod([_member(b"E.Z", b"", compress=True)]))
    add("valid_trailing_garbage_after_zlib_ignored",
        _lod([(b"G.Z", zlib.compress(b"abc") + b"JUNK", 3, 1, len(zlib.compress(b"abc"))),]))
    add("valid_trailing_bytes_after_last_payload", _lod(SAMPLE, tail=b"\x00\x01\x02"))
    add("valid_unique_names_strict", _lod(SAMPLE), strict=True)

    # ---- case-insensitive names and duplicates
    dup = [_member(b"A.TXT", b"first"), _member(b"a.txt", b"second")]
    add("duplicate_last_wins_lenient", _lod(dup))
    add("duplicate_strict_rejected", _lod(dup), strict=True)
    add("duplicate_keeps_first_position",
        _lod([_member(b"X.BIN", b"x"), _member(b"A.TXT", b"1"), _member(b"x.bin", b"2")]))
    # Python str.upper() maps U+00DF to "SS", so these two names collide.
    add("duplicate_sharp_s_upper_collides",
        _lod([_member(b"stra\xdfe.txt", b"one"), _member(b"STRASSE.TXT", b"two")]))

    # ---- header and count
    add("bad_magic", _lod(SAMPLE, magic=b"LODX"))
    add("empty_file", b"")
    add("short_header_91_bytes", _lod(SAMPLE)[:91])
    add("count_u32_max", _lod(SAMPLE, count=0xFFFFFFFF))
    add("count_over_cap", _lod([], count=MAX_ENTRIES + 1))
    add("count_at_cap_directory_missing", _lod([], count=MAX_ENTRIES))
    add("count_bomb_small_file", _lod(SAMPLE, count=5000))
    add("count_larger_than_members", _lod(SAMPLE, count=len(SAMPLE) + 1))
    add("count_smaller_than_members", _lod(SAMPLE, count=1))

    # ---- directory and payload bounds
    add("raw_offset_past_end", _patch_u32(_lod(SAMPLE), _entry_pos(0, 0), len(_lod(SAMPLE))))
    add("offset_and_size_u32_overflow",
        _patch_u32(_patch_u32(_lod([_member(b"A", b"x")]), _entry_pos(0, 0), 0xFFFFFFFF),
                   _entry_pos(0, 1), 0xFFFFFFFF))
    add("packed_size_past_end", _patch_u32(_lod(SAMPLE), _entry_pos(1, 3), 10**6))
    add("empty_name_rejected", _lod([_member(b"", b"1")]))
    add("nul_first_name_rejected", _lod([_member(b"\x00ABC", b"1")]))

    # ---- corrupt payloads (open succeeds, read fails)
    add("corrupt_zlib_not_zlib",
        _lod([(b"BAD", b"not zlib at all", 20, 1, 15)]))
    add("zlib_declared_size_too_small",
        _lod([(b"BOMB", zlib.compress(b"x" * 100), 10, 1, len(zlib.compress(b"x" * 100)))]))
    add("zlib_declared_size_too_large",
        _lod([(b"SHORT", zlib.compress(b"x" * 10), 50, 1, len(zlib.compress(b"x" * 10)))]))
    cut = zlib.compress(b"y" * 500)[:-6]
    add("zlib_truncated_stream", _lod([(b"CUT", cut, 500, 1, len(cut))]))
    bad_adler = zlib.compress(b"z" * 40)[:-1] + bytes([zlib.compress(b"z" * 40)[-1] ^ 0xFF])
    add("zlib_bad_adler32", _lod([(b"ADL", bad_adler, 40, 1, len(bad_adler))]))
    dict_stream = b"\x78\xbb" + b"\x00\x00\x00\x01" + b"payload"
    add("zlib_preset_dictionary_rejected", _lod([(b"DICT", dict_stream, 7, 1, len(dict_stream))]))
    bomb = zlib.compress(b"\x00" * 100000)
    add("zlib_expansion_capped", _lod([(b"ZERO", bomb, 10, 1, len(bomb))]))
    size0 = zlib.compress(b"x")
    add("zlib_size_zero_but_data", _lod([(b"S0", size0, 0, 1, len(size0))]))
    empty_z = zlib.compress(b"")
    add("zlib_empty_stream_size_zero", _lod([(b"EZ", empty_z, 0, 1, len(empty_z))]))

    # ---- every proper prefix of a valid archive is refused
    base = _lod(BASE)
    for k in range(len(base)):
        add("truncated_base_at_%03d" % k, base[:k])
    add("valid_base_archive", base)
    return cases


# --------------------------------------------------------------------------
# PCX builders (synthetic)
# --------------------------------------------------------------------------

PAL = [(i, 255 - i, (i * 7) & 255) for i in range(256)]
PAL_BYTES = b"".join(bytes(c) for c in PAL)


def _pcx_expect(blob):
    try:
        img = parse_pcx(blob)
    except PcxError:
        return {"ok": False, "error": "PcxError"}
    pal = None if img.palette is None else b"".join(bytes(c) for c in img.palette).hex()
    return {
        "ok": True,
        "width": img.width,
        "height": img.height,
        "mode": img.mode,
        "pixels": img.pixels.hex(),
        "palette": pal,
        "rgb": img.to_rgb().hex(),
    }


def _pcx_cases():
    cases = []

    def add(name, blob):
        cases.append({"name": name, "hex": blob.hex(), "expect": _pcx_expect(blob)})

    indexed_2x2 = struct.pack("<3I", 4, 2, 2) + bytes([0, 1, 200, 255]) + PAL_BYTES
    bgr_2x2 = struct.pack("<3I", 12, 2, 2) + bytes([10, 20, 30, 40, 50, 60, 70, 80, 90, 1, 2, 3])
    indexed_1x1 = struct.pack("<3I", 1, 1, 1) + bytes([7]) + PAL_BYTES

    # ---- valid bitmaps
    add("indexed_2x2_valid", indexed_2x2)
    add("indexed_1x1_valid", indexed_1x1)
    add("bgr24_2x2_valid", bgr_2x2)
    add("bgr24_3x1_valid", struct.pack("<3I", 9, 3, 1) + bytes([1, 2, 3, 4, 5, 6, 250, 251, 252]))
    add("indexed_gap_before_palette_tolerated",
        struct.pack("<3I", 4, 2, 2) + bytes([0, 1, 200, 255]) + b"\xaa" * 5 + PAL_BYTES)
    add("indexed_trailing_bytes_shift_palette", indexed_2x2 + b"\x00\x00")
    add("indexed_width_cap_8192x1",
        struct.pack("<3I", 4, 8192, 1) + bytes(range(256)) * 32 + PAL_BYTES)

    # ---- truncation of an indexed and a 24-bit bitmap
    for k in (0, 1, 4, 8, 11, 12, 13, len(indexed_1x1) - 2, len(indexed_1x1) - 1):
        add("indexed_1x1_truncated_at_%03d" % k, indexed_1x1[:k])
    for k in range(len(bgr_2x2)):
        add("bgr24_2x2_truncated_at_%02d" % k, bgr_2x2[:k])

    # ---- malformed headers and sizes
    add("size_matches_neither_mode", struct.pack("<3I", 5, 2, 2) + bytes(5) + bytes(768))
    add("indexed_missing_last_palette_byte", indexed_2x2[:-1])
    add("bgr24_truncated_body", struct.pack("<3I", 12, 2, 2) + bytes(11))
    add("width_over_cap", struct.pack("<3I", 4, 8193, 1) + bytes(4) + bytes(768))
    add("height_over_cap", struct.pack("<3I", 4, 1, 8193) + bytes(4) + bytes(768))
    add("zero_dimensions", struct.pack("<3I", 0, 0, 0))
    add("zero_width", struct.pack("<3I", 4, 0, 2) + bytes(4) + bytes(768))
    add("header_only_11_bytes", b"\x04\x00\x00\x00\x02\x00\x00\x00\x02\x00\x00")
    add("empty_input", b"")
    return cases


# --------------------------------------------------------------------------
# entry point
# --------------------------------------------------------------------------

def generate():
    """Return ``{file name: JSON-serialisable object}`` for the LOD and PCX vectors."""
    return {
        LOD_FILE: {"format": VECTOR_FORMAT, "cases": _lod_cases()},
        PCX_FILE: {"format": VECTOR_FORMAT, "cases": _pcx_cases()},
    }
