"""Tests for h3re.lod using synthetic archives built in memory.

No real game files are used or required.
"""

from __future__ import annotations

import io
import os
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

# The h3re package lives one level above the tests directory.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from h3re.lod import (  # noqa: E402
    ENTRY_SIZE,
    HEADER_SIZE,
    LodArchive,
    LodFormatError,
)


def member(name: str, data: bytes, *, compress: bool = False, type_: int = 1):
    """Describe one archive member: (name, stored_bytes, size, type, packed)."""
    if compress:
        stored = zlib.compress(data)
        return (name, stored, len(data), type_, len(stored))
    return (name, data, len(data), type_, 0)


def build_lod(members, *, magic: bytes = b"LOD\x00", count: int | None = None) -> bytes:
    """Assemble a LOD archive from member() tuples."""
    n = len(members)
    header = magic + struct.pack("<II", 200, n if count is None else count) + b"\x00" * 80
    directory = bytearray()
    payload = bytearray()
    payload_start = HEADER_SIZE + n * ENTRY_SIZE
    for name, stored, size, type_, packed in members:
        raw_name = name.encode("latin-1")
        assert len(raw_name) <= 16
        offset = payload_start + len(payload)
        entry = struct.pack("<16sIIII", raw_name, offset, size, type_, packed)
        directory += entry + b"\x00" * (ENTRY_SIZE - len(entry))
        payload += stored
    return bytes(header) + bytes(directory) + bytes(payload)


def open_bytes(blob: bytes) -> LodArchive:
    return LodArchive(io.BytesIO(blob), len(blob))


SAMPLE = [
    member("DEF_ONE.DEF", b"raw payload bytes"),
    member("TEXT.TXT", b"hello world " * 50, compress=True),
    member("EMPTY.BIN", b""),
]


class OpenAndListTests(unittest.TestCase):
    def test_list_preserves_directory_order(self):
        with open_bytes(build_lod(SAMPLE)) as arc:
            self.assertEqual(arc.list(), ["DEF_ONE.DEF", "TEXT.TXT", "EMPTY.BIN"])
            self.assertEqual(len(arc), 3)

    def test_open_from_path(self):
        blob = build_lod(SAMPLE)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "fixture.lod")
            with open(path, "wb") as f:
                f.write(blob)
            with LodArchive.open(path) as arc:
                self.assertEqual(arc.read("DEF_ONE.DEF"), b"raw payload bytes")

    def test_empty_archive(self):
        with open_bytes(build_lod([])) as arc:
            self.assertEqual(arc.list(), [])

    def test_close_releases_owned_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "fixture.lod")
            with open(path, "wb") as f:
                f.write(build_lod(SAMPLE))
            arc = LodArchive.open(path)
            fp = arc._fp
            arc.close()
            self.assertTrue(fp.closed)

    def test_close_does_not_close_caller_stream(self):
        stream = io.BytesIO(build_lod(SAMPLE))
        arc = LodArchive(stream, len(stream.getvalue()))
        arc.close()
        self.assertFalse(stream.closed)


class ReadTests(unittest.TestCase):
    def setUp(self):
        self.arc = open_bytes(build_lod(SAMPLE))

    def tearDown(self):
        self.arc.close()

    def test_read_raw_member(self):
        self.assertEqual(self.arc.read("DEF_ONE.DEF"), b"raw payload bytes")

    def test_read_compressed_member(self):
        self.assertEqual(self.arc.read("TEXT.TXT"), b"hello world " * 50)

    def test_read_empty_member(self):
        self.assertEqual(self.arc.read("EMPTY.BIN"), b"")

    def test_lookup_is_case_insensitive(self):
        self.assertEqual(self.arc.read("def_one.def"), b"raw payload bytes")
        self.assertIn("Text.txt", self.arc)

    def test_missing_member_raises_keyerror(self):
        with self.assertRaises(KeyError):
            self.arc.read("NOPE.TXT")
        self.assertNotIn("NOPE.TXT", self.arc)

    def test_entry_metadata(self):
        entry = self.arc.entry("TEXT.TXT")
        self.assertTrue(entry.compressed)
        self.assertEqual(entry.size, len(b"hello world " * 50))
        self.assertEqual(entry.type, 1)

    def test_name_is_truncated_at_nul(self):
        blob = build_lod([member("AB", b"x")])
        # Name field is "AB\0..." already; add junk after the NUL to confirm
        # it is ignored.
        blob = bytearray(blob)
        blob[HEADER_SIZE + 3] = ord("Z")
        with open_bytes(bytes(blob)) as arc:
            self.assertEqual(arc.list(), ["AB"])


class MalformedInputTests(unittest.TestCase):
    def assertRejects(self, blob: bytes):
        with self.assertRaises(LodFormatError):
            open_bytes(blob)

    def test_bad_magic(self):
        self.assertRejects(build_lod(SAMPLE, magic=b"LODX"))

    def test_truncated_header(self):
        self.assertRejects(b"LOD\x00\x01")

    def test_empty_file(self):
        self.assertRejects(b"")

    def test_count_exceeds_limit(self):
        self.assertRejects(build_lod([], count=0xFFFFFFFF))

    def test_directory_truncated(self):
        blob = build_lod(SAMPLE)
        self.assertRejects(blob[: HEADER_SIZE + ENTRY_SIZE])

    def test_count_larger_than_directory(self):
        self.assertRejects(build_lod(SAMPLE, count=len(SAMPLE) + 1))

    def test_raw_payload_out_of_bounds(self):
        blob = bytearray(build_lod([member("A", b"12345678")]))
        # Offset field of entry 0 lives at 8 + 16.
        struct.pack_into("<I", blob, HEADER_SIZE + 16, len(blob))
        self.assertRejects(bytes(blob))

    def test_compressed_payload_out_of_bounds(self):
        blob = bytearray(build_lod([member("A", b"abc" * 10, compress=True)]))
        # Packed-size field lives at 8 + 16 + 12.
        struct.pack_into("<I", blob, HEADER_SIZE + 28, 10**6)
        self.assertRejects(bytes(blob))

    def test_offset_overflow_is_rejected(self):
        blob = bytearray(build_lod([member("A", b"x")]))
        struct.pack_into("<I", blob, HEADER_SIZE + 16, 0xFFFFFFFF)
        struct.pack_into("<I", blob, HEADER_SIZE + 20, 0xFFFFFFFF)
        self.assertRejects(bytes(blob))

    def test_duplicate_names_rejected_when_strict(self):
        blob = build_lod([member("A.TXT", b"1"), member("a.txt", b"2")])
        with self.assertRaises(LodFormatError):
            LodArchive(io.BytesIO(blob), len(blob), strict=True)

    def test_duplicate_names_rejected_when_strict_from_path(self):
        blob = build_lod([member("A.TXT", b"1"), member("a.txt", b"2")])
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "dup.lod")
            Path(path).write_bytes(blob)
            with self.assertRaises(LodFormatError):
                LodArchive.open(path, strict=True)

    def test_duplicate_names_last_entry_wins_by_default(self):
        blob = build_lod([member("A.TXT", b"first"), member("a.txt", b"second")])
        with open_bytes(blob) as arc:
            self.assertEqual(arc.read("A.TXT"), b"second")
            self.assertEqual(arc.read("a.txt"), b"second")
            self.assertEqual(arc.entry("A.TXT").size, len(b"second"))
            self.assertEqual(len(arc), 1)
            self.assertEqual(arc.list(), ["a.txt"])

    def test_duplicate_keeps_first_position_in_listing(self):
        blob = build_lod([
            member("X.BIN", b"x"),
            member("A.TXT", b"1"),
            member("x.bin", b"2"),
        ])
        with open_bytes(blob) as arc:
            self.assertEqual(arc.list(), ["x.bin", "A.TXT"])
            self.assertEqual(arc.read("X.BIN"), b"2")

    def test_duplicate_extract_writes_last_entry_once(self):
        blob = build_lod([member("A.TXT", b"first"), member("a.txt", b"second")])
        with open_bytes(blob) as arc, tempfile.TemporaryDirectory() as tmp:
            dest = os.path.join(tmp, "out")
            written = arc.extract_all(dest)
            self.assertEqual(len(written), 1)
            self.assertEqual(Path(dest, "a.txt").read_bytes(), b"second")

    def test_strict_accepts_unique_names(self):
        blob = build_lod(SAMPLE)
        with LodArchive(io.BytesIO(blob), len(blob), strict=True) as arc:
            self.assertEqual(arc.list(), ["DEF_ONE.DEF", "TEXT.TXT", "EMPTY.BIN"])


    def test_empty_name_rejected(self):
        self.assertRejects(build_lod([member("", b"1")]))


class CorruptPayloadTests(unittest.TestCase):
    def open_with_stream(self, name: str, stored: bytes, declared_size: int, packed: int):
        blob = build_lod([(name, stored, declared_size, 1, packed)])
        return open_bytes(blob)

    def test_corrupt_zlib_data(self):
        with self.open_with_stream("BAD", b"not zlib at all", 20, 15) as arc:
            with self.assertRaises(LodFormatError):
                arc.read("BAD")

    def test_declared_size_too_small_is_detected(self):
        stored = zlib.compress(b"x" * 100)
        with self.open_with_stream("BOMB", stored, 10, len(stored)) as arc:
            with self.assertRaises(LodFormatError):
                arc.read("BOMB")

    def test_declared_size_too_large_is_detected(self):
        stored = zlib.compress(b"x" * 10)
        with self.open_with_stream("SHORT", stored, 50, len(stored)) as arc:
            with self.assertRaises(LodFormatError):
                arc.read("SHORT")

    def test_truncated_zlib_stream(self):
        stored = zlib.compress(b"y" * 500)[:-6]
        with self.open_with_stream("CUT", stored, 500, len(stored)) as arc:
            with self.assertRaises(LodFormatError):
                arc.read("CUT")


class ExtractTests(unittest.TestCase):
    def test_extract_all_writes_members(self):
        with open_bytes(build_lod(SAMPLE)) as arc, tempfile.TemporaryDirectory() as tmp:
            dest = os.path.join(tmp, "out")
            written = arc.extract_all(dest)
            self.assertEqual(len(written), 3)
            self.assertEqual(Path(dest, "DEF_ONE.DEF").read_bytes(), b"raw payload bytes")
            self.assertEqual(Path(dest, "TEXT.TXT").read_bytes(), b"hello world " * 50)
            self.assertEqual(Path(dest, "EMPTY.BIN").read_bytes(), b"")

    def test_path_traversal_names_are_rejected_before_writing(self):
        bad_names = ["../evil.txt", "sub/evil.txt", "..\\evil.txt", "C:evil.txt", "..", "."]
        for bad in bad_names:
            with self.subTest(name=bad):
                blob = build_lod([member("OK.TXT", b"ok"), member(bad, b"evil")])
                with open_bytes(blob) as arc, tempfile.TemporaryDirectory() as tmp:
                    dest = os.path.join(tmp, "out")
                    with self.assertRaises(LodFormatError):
                        arc.extract_all(dest)
                    # Validation happens before anything is created or written.
                    self.assertFalse(os.path.exists(dest))
                    self.assertFalse(Path(tmp, "evil.txt").exists())

    def test_control_characters_in_name_rejected(self):
        blob = build_lod([member("A\x01B", b"x")])
        with open_bytes(blob) as arc, tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(LodFormatError):
                arc.extract_all(os.path.join(tmp, "out"))

    def test_symlink_at_target_is_refused(self):
        if not hasattr(os, "symlink"):
            self.skipTest("no symlink support")
        with tempfile.TemporaryDirectory() as tmp:
            outside = Path(tmp, "outside.txt")
            outside.write_bytes(b"original")
            dest = Path(tmp, "out")
            dest.mkdir()
            try:
                os.symlink(outside, dest / "LINK.TXT")
            except OSError:
                self.skipTest("cannot create symlinks")
            with open_bytes(build_lod([member("LINK.TXT", b"pwned")])) as arc:
                with self.assertRaises(LodFormatError):
                    arc.extract_all(dest)
            self.assertEqual(outside.read_bytes(), b"original")


if __name__ == "__main__":
    unittest.main()
