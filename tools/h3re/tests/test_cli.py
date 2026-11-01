"""Tests for the h3re command-line interface (h3re/__main__.py).

Fixtures are synthetic and written into a temporary directory. No game files
are used or required.
"""

from __future__ import annotations

import contextlib
import gzip
import io
import os
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PKG_ROOT))

from h3re import h3m  # noqa: E402
from h3re.__main__ import main  # noqa: E402

# ----------------------------------------------------------------- builders


def lod_bytes(members: list[tuple[str, bytes]], magic: bytes = b"LOD\x00") -> bytes:
    """Uncompressed LOD archive. Each member is (name, data)."""
    header = magic + struct.pack("<II", 200, len(members)) + bytes(80)
    payload_start = 92 + 32 * len(members)
    directory = b""
    payload = b""
    for name, data in members:
        offset = payload_start + len(payload)
        directory += struct.pack("<16sIIII", name.encode("latin-1"), offset, len(data), 1, 0)
        payload += data
    return header + directory + payload


_PALETTE = bytes(v for i in range(256) for v in (i, 255 - i, 128))


def def_bytes(frames) -> bytes:
    """One-block DEF of raw (format 0) frames.

    Each frame is (name, full_w, full_h, w, h, x, y, pixels).
    """
    n = len(frames)
    head = struct.pack("<4I", 0x42, 8, 4, 1) + _PALETTE
    block_head = struct.pack("<4I", 0, n, 0, 0)
    names = b"".join(f[0].encode("latin-1").ljust(13, b"\0") for f in frames)
    pos = len(head) + len(block_head) + len(names) + 4 * n
    offsets = []
    body = b""
    for _name, fw, fh, w, h, x, y, pixels in frames:
        offsets.append(pos + len(body))
        body += struct.pack(
            "<8I", len(pixels), 0, fw, fh, w, h, x & 0xFFFFFFFF, y & 0xFFFFFFFF
        ) + pixels
    return head + block_head + names + struct.pack(f"<{n}I", *offsets) + body


def _s(text: str) -> bytes:
    raw = text.encode("cp1252")
    return struct.pack("<I", len(raw)) + raw


def h3m_bytes(name: str = "Test Map", desc: str = "A description\nline two") -> bytes:
    """Uncompressed SoD map header with one active player and no conditions."""
    out = struct.pack("<I", h3m.SOD) + b"\x01" + struct.pack("<I", 36) + b"\x00"
    out += _s(name) + _s(desc) + b"\x02" + b"\x00"  # difficulty, max hero level
    active = (
        b"\x01\x01"  # can_human, can_computer
        + b"\x00\x00"  # ai behavior, customized towns
        + b"\xff\x01"  # allowed factions (u16)
        + b"\x00\x00\x00\xff"  # random faction, main town, random hero, no hero
        + b"\x00"  # placeholder
        + struct.pack("<I", 0)  # hero count
    )
    inactive = b"\x00\x00" + bytes(13)
    out += active + inactive * 7
    out += b"\xff" + b"\xff" + b"\x00"  # victory none, loss none, no teams
    # Everything after the teams block, in the order h3m.py reads it (SoD):
    out += bytes(20)  # allowed heroes mask
    out += struct.pack("<I", 0)  # placeholder hero count
    out += b"\x00"  # disposed hero count
    out += bytes(31)  # reserved
    out += bytes(18)  # allowed artifacts mask
    out += bytes(9) + bytes(4)  # allowed spells mask, allowed skills mask
    out += struct.pack("<I", 0)  # rumor count
    out += bytes(156)  # predefined hero flags (all absent)
    return out


def run_cli(*argv: str) -> tuple[object, str, str]:
    """Run main() in-process; return (exit_code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            rc = main(list(argv))
        except SystemExit as exc:  # argparse usage errors
            rc = exc.code
    return rc, out.getvalue(), err.getvalue()


def png_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n", path
    return struct.unpack(">II", data[16:24])


class TempDirTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    def write(self, name: str, data: bytes) -> str:
        path = self.tmp / name
        path.write_bytes(data)
        return str(path)


# --------------------------------------------------------------- lod commands


class LodCommandTests(TempDirTestCase):
    MEMBERS = [("DEF_ONE.DEF", b"abc"), ("TEXT.TXT", b"hello"), ("EMPTY.BIN", b"")]

    def test_lod_list_prints_names_in_directory_order(self):
        rc, out, err = run_cli("lod-list", self.write("a.lod", lod_bytes(self.MEMBERS)))
        self.assertEqual(rc, 0, err)
        self.assertEqual(out.splitlines(), ["DEF_ONE.DEF", "TEXT.TXT", "EMPTY.BIN"])

    def test_lod_list_empty_archive(self):
        rc, out, _ = run_cli("lod-list", self.write("a.lod", lod_bytes([])))
        self.assertEqual((rc, out), (0, ""))

    def test_lod_extract_writes_members(self):
        path = self.write("a.lod", lod_bytes(self.MEMBERS))
        dest = self.tmp / "out"
        rc, out, err = run_cli("lod-extract", path, str(dest))
        self.assertEqual(rc, 0, err)
        self.assertIn("extracted 3 member(s)", out)
        self.assertEqual((dest / "DEF_ONE.DEF").read_bytes(), b"abc")
        self.assertEqual((dest / "TEXT.TXT").read_bytes(), b"hello")
        self.assertEqual((dest / "EMPTY.BIN").read_bytes(), b"")

    def test_lod_extract_refuses_path_traversal_before_writing(self):
        path = self.write("a.lod", lod_bytes([("OK.TXT", b"ok"), ("../evil.bin", b"evil")]))
        dest = self.tmp / "out"
        rc, _, err = run_cli("lod-extract", path, str(dest))
        self.assertEqual(rc, 1)
        self.assertIn("unsafe member name", err)
        self.assertFalse(dest.exists())
        self.assertFalse((self.tmp / "evil.bin").exists())

    def test_lod_list_rejects_bad_magic(self):
        blob = lod_bytes(self.MEMBERS, magic=b"LODX")
        rc, out, err = run_cli("lod-list", self.write("a.lod", blob))
        self.assertEqual(rc, 1)
        self.assertEqual(out, "")
        self.assertIn("bad magic", err)

    def test_lod_list_rejects_truncated_directory(self):
        blob = lod_bytes(self.MEMBERS)[:100]
        rc, _, err = run_cli("lod-list", self.write("a.lod", blob))
        self.assertEqual(rc, 1)
        self.assertTrue(err.startswith("h3re: error: "), err)

    def test_lod_list_missing_file(self):
        missing = str(self.tmp / "nope.lod")
        rc, _, err = run_cli("lod-list", missing)
        self.assertEqual(rc, 1)
        self.assertIn("nope.lod", err)
        self.assertIn("No such file or directory", err)
        self.assertNotIn("Traceback", err)


# --------------------------------------------------------------- def command


class DefCommandTests(TempDirTestCase):
    def test_def_to_png_writes_one_file_per_frame(self):
        frames = [
            ("A.pcx", 4, 2, 4, 2, 0, 0, bytes(range(1, 9))),
            ("B.pcx", 2, 2, 1, 1, 1, 1, b"\x09"),
        ]
        path = self.write("sprite.def", def_bytes(frames))
        out_dir = self.tmp / "out"
        rc, out, err = run_cli("def-to-png", path, str(out_dir))
        self.assertEqual(rc, 0, err)
        self.assertIn("wrote 2 PNG file(s)", out)
        self.assertEqual(
            sorted(p.name for p in out_dir.iterdir()),
            ["00_000_A.pcx.png", "00_001_B.pcx.png"],
        )
        # Canvas size is the full frame size, not the drawn sub-rectangle.
        self.assertEqual(png_size(out_dir / "00_000_A.pcx.png"), (4, 2))
        self.assertEqual(png_size(out_dir / "00_001_B.pcx.png"), (2, 2))

    def test_frame_names_cannot_escape_outdir(self):
        path = self.write("sprite.def", def_bytes([("../evil.pcx", 1, 1, 1, 1, 0, 0, b"\x01")]))
        out_dir = self.tmp / "out"
        rc, _, err = run_cli("def-to-png", path, str(out_dir))
        self.assertEqual(rc, 0, err)
        self.assertEqual(sorted(os.listdir(self.tmp)), ["out", "sprite.def"])
        self.assertEqual(len(list(out_dir.iterdir())), 1)

    def test_zero_size_frame_is_skipped_with_warning(self):
        frames = [
            ("EMPTY.pcx", 0, 0, 0, 0, 0, 0, b""),
            ("OK.pcx", 2, 2, 2, 2, 0, 0, bytes([1, 2, 3, 4])),
        ]
        path = self.write("sprite.def", def_bytes(frames))
        out_dir = self.tmp / "out"
        rc, _, err = run_cli("def-to-png", path, str(out_dir))
        self.assertEqual(rc, 0)
        self.assertIn("skipped 1 frame(s)", err)
        self.assertEqual([p.name for p in out_dir.iterdir()], ["00_001_OK.pcx.png"])

    def test_truncated_def_fails_cleanly(self):
        blob = def_bytes([("A.pcx", 4, 2, 4, 2, 0, 0, bytes(8))])[:-1]
        out_dir = self.tmp / "out"
        rc, _, err = run_cli("def-to-png", self.write("bad.def", blob), str(out_dir))
        self.assertEqual(rc, 1)
        self.assertIn("truncated", err)
        self.assertNotIn("Traceback", err)

    def test_missing_def_file(self):
        rc, _, err = run_cli("def-to-png", str(self.tmp / "none.def"), str(self.tmp / "out"))
        self.assertEqual(rc, 1)
        self.assertIn("none.def", err)


# --------------------------------------------------------------- h3m command


class H3mCommandTests(TempDirTestCase):
    def test_h3m_info_summary_from_gzip(self):
        path = self.write("map.h3m", gzip.compress(h3m_bytes()))
        rc, out, err = run_cli("h3m-info", path)
        self.assertEqual(rc, 0, err)
        self.assertIn("SoD (0x1C)", out)
        self.assertIn("36x36", out)
        self.assertIn("Test Map", out)
        self.assertIn("1 active of 8", out)
        self.assertIn("human=yes computer=yes", out)
        self.assertIn("victory:", out)
        self.assertIn("none", out)

    def test_h3m_info_accepts_uncompressed(self):
        rc, out, err = run_cli("h3m-info", self.write("map.h3m", h3m_bytes()))
        self.assertEqual(rc, 0, err)
        self.assertIn("Test Map", out)

    def test_h3m_info_escapes_control_characters(self):
        path = self.write("map.h3m", h3m_bytes(name="A\x1bB", desc="line1\nline2"))
        rc, out, err = run_cli("h3m-info", path)
        self.assertEqual(rc, 0, err)
        self.assertIn("A\\x1bB", out)
        self.assertIn("line1\\nline2", out)
        self.assertNotIn("\x1b", out)

    def test_h3m_info_rejects_garbage(self):
        rc, out, err = run_cli("h3m-info", self.write("junk.h3m", b"not a map at all"))
        self.assertEqual(rc, 1)
        self.assertEqual(out, "")
        self.assertIn("unsupported map format", err)

    def test_h3m_info_rejects_truncated_map(self):
        rc, _, err = run_cli("h3m-info", self.write("cut.h3m", h3m_bytes()[:40]))
        self.assertEqual(rc, 1)
        self.assertIn("truncated", err)
        self.assertNotIn("Traceback", err)

    def test_h3m_info_rejects_bad_gzip(self):
        rc, _, err = run_cli("h3m-info", self.write("bad.h3m", b"\x1f\x8b\x08garbage"))
        self.assertEqual(rc, 1)
        self.assertIn("gzip", err)


# ------------------------------------------------------------------- usage


class UsageTests(unittest.TestCase):
    def test_no_command_is_usage_error(self):
        rc, _, err = run_cli()
        self.assertEqual(rc, 2)
        self.assertIn("usage", err)

    def test_unknown_command_is_usage_error(self):
        rc, _, err = run_cli("lod-frobnicate", "x")
        self.assertEqual(rc, 2)
        self.assertIn("invalid choice", err)

    def test_missing_argument_is_usage_error(self):
        rc, _, _ = run_cli("lod-extract", "only-one-arg")
        self.assertEqual(rc, 2)


# ------------------------------------------------------- module entry point


class ModuleEntryPointTests(unittest.TestCase):
    def run_module(self, *argv: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "-m", "h3re", *argv],
            cwd=PKG_ROOT,
            capture_output=True,
            text=True,
            timeout=60,
        )

    def test_help(self):
        proc = self.run_module("--help")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        for command in ("lod-list", "lod-extract", "def-to-png", "h3m-info"):
            self.assertIn(command, proc.stdout)

    def test_error_exit_has_no_traceback(self):
        proc = self.run_module("lod-list", str(PKG_ROOT / "does-not-exist.lod"))
        self.assertEqual(proc.returncode, 1)
        self.assertTrue(proc.stderr.startswith("h3re: error: "), proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)


if __name__ == "__main__":
    unittest.main()
