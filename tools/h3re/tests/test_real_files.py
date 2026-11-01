"""Optional tests against real game files.

Skipped unless the H3_DATA_DIR environment variable points at a directory
containing game data (*.lod archives, and *.h3m files under a Maps dir).

Only invariants are asserted (entry count, dimension bounds, parse success).
No game data is embedded here, and assertion messages never include file
contents -- only archive-relative paths, member names and exception types.
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from h3re.defimg import MAX_TOTAL_PIXELS, parse_def  # noqa: E402
from h3re.h3m import H3mError, parse_h3m  # noqa: E402
from h3re.lod import LodArchive  # noqa: E402
from h3re.pcx import MAX_DIM, parse_pcx  # noqa: E402
from h3re.txt import parse_txt  # noqa: E402

DATA_DIR = os.environ.get("H3_DATA_DIR")
SKIP_REASON = "H3_DATA_DIR not set; real-game-file tests are optional"

SAMPLE_PER_KIND = 5          # max members decoded per kind per archive
MAX_MEMBER_BYTES = 8 * 1024 * 1024
MAX_H3M_FILES = 50
MAX_H3M_BYTES = 16 * 1024 * 1024


def _files(root: Path, suffix: str):
    out = []
    for dirpath, _dirs, names in os.walk(root):
        for n in names:
            if n.lower().endswith(suffix):
                out.append(Path(dirpath) / n)
    return sorted(out)


def _rel(p: Path) -> str:
    return str(p.relative_to(DATA_DIR))


@unittest.skipUnless(DATA_DIR, SKIP_REASON)
class RealLodTests(unittest.TestCase):
    def test_lod_archives(self):
        root = Path(DATA_DIR)
        lods = _files(root, ".lod")
        if not lods:
            self.skipTest("no *.lod files under H3_DATA_DIR")
        for path in lods:
            with self.subTest(lod=_rel(path)):
                with LodArchive.open(path) as lod:
                    self.assertGreater(len(lod), 0, "archive has no entries")
                    names = lod.list()
                    for ext, check in (
                        (".def", self._check_def),
                        (".pcx", self._check_pcx),
                        (".txt", self._check_txt),
                    ):
                        picked = [
                            n for n in names
                            if n.lower().endswith(ext)
                            and lod.entry(n).size <= MAX_MEMBER_BYTES
                        ][:SAMPLE_PER_KIND]
                        for name in picked:
                            with self.subTest(member=name):
                                try:
                                    data = lod.read(name)
                                except Exception as exc:  # noqa: BLE001
                                    self.fail(f"read failed: {type(exc).__name__}")
                                check(name, data)

    def _check_def(self, name, data):
        try:
            d = parse_def(data)
        except Exception as exc:  # noqa: BLE001
            self.fail(f"DEF decode failed: {type(exc).__name__}")
        self.assertTrue(0 < d.width * d.height <= MAX_TOTAL_PIXELS, "DEF dimensions out of bounds")
        self.assertGreater(len(d.blocks), 0, "DEF has no blocks")
        self.assertEqual(len(d.palette), 256, "DEF palette size")

    def _check_pcx(self, name, data):
        try:
            img = parse_pcx(data)
        except Exception as exc:  # noqa: BLE001
            self.fail(f"PCX decode failed: {type(exc).__name__}")
        self.assertTrue(1 <= img.width <= MAX_DIM, "PCX width out of bounds")
        self.assertTrue(1 <= img.height <= MAX_DIM, "PCX height out of bounds")

    def _check_txt(self, name, data):
        try:
            t = parse_txt(data)
        except Exception as exc:  # noqa: BLE001
            self.fail(f"TXT parse failed: {type(exc).__name__}")
        self.assertGreaterEqual(len(t.rows), 0)


@unittest.skipUnless(DATA_DIR, SKIP_REASON)
class RealMapTests(unittest.TestCase):
    def test_h3m_headers(self):
        root = Path(DATA_DIR)
        maps = []
        for d, _dirs, _n in os.walk(root):
            if Path(d).name.lower() == "maps":
                maps += _files(Path(d), ".h3m")
        maps = sorted(set(maps))[:MAX_H3M_FILES]
        if not maps:
            self.skipTest("no *.h3m files under a Maps directory in H3_DATA_DIR")
        for path in maps:
            with self.subTest(h3m=_rel(path)):
                if path.stat().st_size > MAX_H3M_BYTES:
                    self.skipTest("map file larger than test cap")
                try:
                    h = parse_h3m(path.read_bytes())
                except H3mError as exc:
                    if "unsupported map format" in str(exc):
                        self.skipTest("unsupported map version")
                    self.fail("H3M header parse failed: H3mError")
                except Exception as exc:  # noqa: BLE001
                    self.fail(f"H3M header parse failed: {type(exc).__name__}")
                self.assertTrue(1 <= h.size <= 1024, "map size out of bounds")
                self.assertEqual(len(h.players), 8, "player count")


if __name__ == "__main__":
    unittest.main()
