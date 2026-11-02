"""Tests for h3re.real_report (the `real-report` subcommand).

Every fixture is synthetic and built here from the builders of the format
tests; no game file is used. The report must never carry file content, so
several tests plant canary strings in members and maps and assert they do
not appear, and one pins the exact set of keys and the shape of every string.
"""

from __future__ import annotations

import contextlib
import gzip
import io
import json
import os
import random
import re
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest import mock

PKG_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PKG_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import test_def as TD  # noqa: E402
import test_h3m as TH  # noqa: E402
import test_lod as TL  # noqa: E402
import test_pcx as TP  # noqa: E402
import test_txt as TT  # noqa: E402
from h3re import real_report  # noqa: E402
from h3re.__main__ import main  # noqa: E402

REPO_ROOT = PKG_ROOT.parents[1]

# The complete vocabulary of dictionary keys a report may contain.
ALLOWED_KEYS = frozenset("""
report_schema h3re_version python platform sample_per_kind data_dir exists is_dir
scan_truncated archives maps sprites summary findings
name size_bytes opens error_type entries members def pcx txt other kinds
kind total sampled ok failed skipped_large errors type count
skipped_too_large header_ok objects_ok format map_size levels error
phase reason stage format_id class_id subid
layout lods present defs found_in decodes blocks idle_block_present idle_frames
idle_frame0_nonempty
archives_found archives_open maps_found maps_header_ok maps_objects_ok
""".split())

NAME_OK = re.compile(r"[A-Za-z0-9._ \-/?]+")
TYPE_OK = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

CANARY = "CANARYZXQ"


# ----------------------------------------------------------------- builders


def def_blocks(blocks, canvas=(8, 4)):
    """A DEF with several blocks; each block is a list of (w, h) raw frames."""
    head = struct.pack("<4I", 0x42, canvas[0], canvas[1], len(blocks)) + TD.PAL
    tables = b""
    frames = b""
    table_len = sum(16 + 13 * len(b) + 4 * len(b) for b in blocks)
    for bi, frs in enumerate(blocks):
        n = len(frs)
        names = b"".join((b"F%d_%d.pcx" % (bi, i)).ljust(13, b"\0") for i in range(n))
        offs = []
        for (w, h) in frs:
            offs.append(len(head) + table_len + len(frames))
            frames += TD.frame_bytes(0, w, h, w, h, 0, 0, bytes(w * h))
        tables += (struct.pack("<4I", bi, n, 0, 0) + names
                   + struct.pack("<%dI" % n, *offs))
    return head + tables + frames


def idle_def():
    return def_blocks([[(2, 2)], [(2, 2)], [(2, 2), (2, 2)]])


def no_group2_def():
    return def_blocks([[(2, 2)], [(2, 2)]])


def empty_idle_def():
    return def_blocks([[(2, 2)], [(2, 2)], [(0, 0)]])


def lod(members):
    return TL.build_lod([TL.member(n, d) for n, d in members])


def txt_bytes():
    return TT.build([["Name", "Cost"], [CANARY + "TXT", "60"]])


def valid_map(objects=True):
    raw = TH.build(TH.SOD, size=3)
    if objects:
        raw += TH.u32(0) + TH.u32(0) + TH.u32(0)
    return gzip.compress(raw)


def write(root, rel, data):
    p = Path(root) / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    return p


def all_keys(node):
    if isinstance(node, dict):
        for k, v in node.items():
            yield k
            yield from all_keys(v)
    elif isinstance(node, list):
        for v in node:
            yield from all_keys(v)


def all_strings(node, key=None):
    if isinstance(node, dict):
        for k, v in node.items():
            yield from all_strings(v, k)
    elif isinstance(node, list):
        for v in node:
            yield from all_strings(v, key)
    elif isinstance(node, str):
        yield key, node


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "game"
        self.root.mkdir()

    def report(self, **kw):
        return real_report.build_report(self.root, **kw)

    def archive(self, rep, name):
        return next(a for a in rep["archives"] if a["name"] == name)

    def kind(self, arch, kind):
        return next(k for k in arch["kinds"] if k["kind"] == kind)


# ----------------------------------------------------------------- the tests


class EmptyAndMissing(Base):
    def test_empty_dir(self):
        rep = self.report()
        self.assertEqual(rep["archives"], [])
        self.assertEqual(rep["maps"], [])
        self.assertEqual(rep["data_dir"], {"exists": True, "is_dir": True})
        self.assertEqual(rep["summary"]["archives_found"], 0)
        for code in ("NO_LOD_FOUND", "NO_MAPS_FOUND", "SPRITE_LOD_MISSING",
                     "SPRITE_DEF_MISSING"):
            self.assertIn(code, rep["findings"])
        self.assertNotIn("DATA_DIR_INVALID", rep["findings"])
        self.assertEqual([r["name"] for r in rep["sprites"]["lods"]],
                         ["H3sprite.lod", "H3ab_spr.lod"])
        self.assertEqual([d["name"] for d in rep["sprites"]["defs"]],
                         ["CPKMAN.DEF", "CLCBOW.DEF", "CGRIFF.DEF"])
        self.assertEqual(rep["sprites"]["layout"], "absent")

    def test_missing_dir_is_reported_not_raised(self):
        rep = real_report.build_report(self.root / "nope")
        self.assertEqual(rep["data_dir"], {"exists": False, "is_dir": False})
        self.assertIn("DATA_DIR_INVALID", rep["findings"])
        self.assertNotIn("NO_LOD_FOUND", rep["findings"])

    def test_file_instead_of_dir(self):
        f = write(self.root, "x.lod", b"")
        rep = real_report.build_report(f)
        self.assertEqual(rep["data_dir"], {"exists": True, "is_dir": False})
        self.assertIn("DATA_DIR_INVALID", rep["findings"])

    def test_missing_sprite_archives_with_other_lod_present(self):
        write(self.root, "Data/H3bitmap.lod", lod([("A.PCX", TP.indexed_2x2())]))
        rep = self.report()
        self.assertEqual([r["present"] for r in rep["sprites"]["lods"]], [False, False])
        self.assertIn("SPRITE_LOD_MISSING", rep["findings"])
        self.assertIn("SPRITE_DEF_MISSING", rep["findings"])
        self.assertNotIn("NO_LOD_FOUND", rep["findings"])
        self.assertEqual([d["found_in"] for d in rep["sprites"]["defs"]], [None] * 3)

    def test_only_one_sprite_archive(self):
        write(self.root, "Data/H3sprite.lod", lod([("CPKMAN.DEF", idle_def())]))
        rep = self.report()
        self.assertEqual([(r["name"], r["present"], r["opens"]) for r in rep["sprites"]["lods"]],
                         [("H3sprite.lod", True, True), ("H3ab_spr.lod", False, False)])
        self.assertEqual(rep["sprites"]["layout"], "data")


class ArchiveParsing(Base):
    def test_one_valid_archive(self):
        members = [("GOOD1.DEF", idle_def()), ("GOOD2.DEF", idle_def()),
                   ("BAD.DEF", b"not a def"),
                   ("A.PCX", TP.indexed_2x2()), ("B.PCX", b"junk"),
                   ("T.TXT", txt_bytes()), ("README.BIN", b"zz")]
        write(self.root, "Data/H3bitmap.lod", lod(members))
        rep = self.report()
        a = self.archive(rep, "Data/H3bitmap.lod")
        self.assertTrue(a["opens"])
        self.assertIsNone(a["error_type"])
        self.assertEqual(a["entries"], 7)
        self.assertEqual(a["members"], {"def": 3, "pcx": 2, "txt": 1, "other": 1})
        self.assertEqual([k["kind"] for k in a["kinds"]], ["def", "pcx", "txt"])
        d = self.kind(a, "def")
        self.assertEqual((d["total"], d["sampled"], d["ok"], d["failed"]), (3, 3, 2, 1))
        self.assertEqual(d["errors"], [{"type": "DefError", "count": 1}])
        p = self.kind(a, "pcx")
        self.assertEqual((p["ok"], p["failed"]), (1, 1))
        self.assertEqual(p["errors"], [{"type": "PcxError", "count": 1}])
        t = self.kind(a, "txt")
        self.assertEqual((t["ok"], t["failed"], t["errors"]), (1, 0, []))
        self.assertEqual(rep["summary"]["archives_open"], 1)
        self.assertIn("DEF_DECODE_FAILED", rep["findings"])
        self.assertIn("PCX_DECODE_FAILED", rep["findings"])
        self.assertNotIn("TXT_PARSE_FAILED", rep["findings"])

    def test_sample_limit(self):
        members = [("D%02d.DEF" % i, idle_def()) for i in range(12)]
        write(self.root, "a.lod", lod(members))
        d = self.kind(self.archive(self.report(), "a.lod"), "def")
        self.assertEqual((d["total"], d["sampled"]), (12, 5))
        d = self.kind(self.archive(self.report(sample=2), "a.lod"), "def")
        self.assertEqual(d["sampled"], 2)
        d = self.kind(self.archive(self.report(sample=0), "a.lod"), "def")
        self.assertEqual(d["sampled"], 0)
        d = self.kind(self.archive(self.report(sample=10**9), "a.lod"), "def")
        self.assertEqual(d["sampled"], 12)

    def test_sample_picks_the_first_by_name_not_by_directory_order(self):
        # Directory order puts the corrupt member last; sorted order puts it first.
        write(self.root, "a.lod", lod([("Z.DEF", idle_def()), ("A.DEF", b"junk")]))
        d = self.kind(self.archive(self.report(sample=1), "a.lod"), "def")
        self.assertEqual((d["ok"], d["failed"]), (0, 1))

    def test_sampled_members_are_the_first_two_in_sorted_order_from_a_scrambled_directory(self):
        # Directory order B, D, A, C. The first two by sorted name are A and B (both corrupt). Sorted
        # descending would pick D and C (both good); directory order picks B and D; reversed directory
        # order picks C and A. Only the real ordering gives 0 ok and 2 failed.
        write(self.root, "a.lod", lod([("B.DEF", b"junk"), ("D.DEF", idle_def()),
                                       ("A.DEF", b"junk"), ("C.DEF", idle_def())]))
        d = self.kind(self.archive(self.report(sample=2), "a.lod"), "def")
        self.assertEqual((d["total"], d["sampled"], d["ok"], d["failed"]), (4, 2, 0, 2))
        # one step wider: A, B, C are sampled and D is not
        d = self.kind(self.archive(self.report(sample=3), "a.lod"), "def")
        self.assertEqual((d["sampled"], d["ok"], d["failed"]), (3, 1, 2))

    def test_member_over_cap_is_skipped_not_decoded(self):
        big = TL.member("BIG.DEF", b"\xff" * (8 * 1024 * 1024 + 1), compress=True)
        small = TL.member("SMALL.DEF", idle_def())
        write(self.root, "a.lod", TL.build_lod([big, small]))
        d = self.kind(self.archive(self.report(), "a.lod"), "def")
        self.assertEqual((d["skipped_large"], d["ok"], d["failed"]), (1, 1, 0))
        # exactly at the 8 MiB cap is decoded (and fails as a DEF), not skipped
        at = TL.member("AT.DEF", b"\xff" * (8 * 1024 * 1024), compress=True)
        write(self.root, "b.lod", TL.build_lod([at]))
        d = self.kind(self.archive(self.report(), "b.lod"), "def")
        self.assertEqual((d["skipped_large"], d["failed"]), (0, 1))

    def test_corrupt_member_payload_counts_as_failed(self):
        good = TL.member("X.DEF", idle_def(), compress=True)
        name, stored, size, type_, packed = good
        broken = (name, b"\xff" * len(stored), size, type_, packed)
        write(self.root, "a.lod", TL.build_lod([broken]))
        d = self.kind(self.archive(self.report(), "a.lod"), "def")
        self.assertEqual(d["failed"], 1)
        self.assertEqual(d["errors"], [{"type": "LodFormatError", "count": 1}])

    def test_corrupt_archives(self):
        write(self.root, "Data/badmagic.lod", b"XXXX" + bytes(200))
        write(self.root, "Data/short.lod", b"LOD\x00" + bytes(10))
        write(self.root, "Data/empty.lod", b"")
        good = lod([("A.DEF", idle_def())])
        write(self.root, "Data/cut.lod", good[:100])
        rep = self.report()
        self.assertEqual(len(rep["archives"]), 4)
        for a in rep["archives"]:
            if a["name"].endswith("empty.lod") or a["name"].endswith("short.lod") \
                    or a["name"].endswith("badmagic.lod") or a["name"].endswith("cut.lod"):
                self.assertFalse(a["opens"], a["name"])
                self.assertEqual(a["error_type"], "LodFormatError", a["name"])
                self.assertEqual((a["entries"], a["members"], a["kinds"]), (None, None, []))
        self.assertEqual(rep["summary"]["archives_found"], 4)
        self.assertEqual(rep["summary"]["archives_open"], 0)
        self.assertIn("LOD_OPEN_FAILED", rep["findings"])

    def test_case_insensitive_names_and_nested_dirs(self):
        write(self.root, "DATA/Sub/WEIRD.LoD", lod([("A.def", idle_def())]))
        rep = self.report()
        self.assertEqual([a["name"] for a in rep["archives"]], ["DATA/Sub/WEIRD.LoD"])
        self.assertEqual(self.kind(rep["archives"][0], "def")["ok"], 1)

    def test_broken_symlink_named_lod_is_recorded(self):
        try:
            os.symlink(self.root / "missing-target", self.root / "dead.lod")
        except (OSError, NotImplementedError):
            self.skipTest("symlinks unavailable")
        a = self.archive(self.report(), "dead.lod")
        self.assertFalse(a["opens"])
        self.assertEqual(a["error_type"], "FileNotFoundError")

    def test_scan_depth_and_file_cap(self):
        deep = "/".join(["d"] * 8) + "/deep.lod"
        write(self.root, deep, lod([]))
        write(self.root, "ok.lod", lod([]))
        self.assertEqual([a["name"] for a in self.report()["archives"]], ["ok.lod"])
        with mock.patch.object(real_report, "MAX_LOD_FILES", 1):
            write(self.root, "ok2.lod", lod([]))
            rep = self.report()
        self.assertEqual(len(rep["archives"]), 1)
        self.assertTrue(rep["scan_truncated"])
        self.assertIn("SCAN_TRUNCATED", rep["findings"])


class SpriteCheck(Base):
    def test_all_present_and_decoding(self):
        write(self.root, "Data/H3sprite.lod",
              lod([("CPKMAN.DEF", idle_def()), ("CLCBOW.DEF", idle_def())]))
        write(self.root, "Data/H3ab_spr.lod", lod([("CGRIFF.DEF", idle_def())]))
        sp = self.report()["sprites"]
        self.assertEqual(sp["layout"], "data")
        self.assertEqual([(d["name"], d["found_in"], d["decodes"], d["idle_frame0_nonempty"])
                          for d in sp["defs"]],
                         [("CPKMAN.DEF", "H3sprite.lod", True, True),
                          ("CLCBOW.DEF", "H3sprite.lod", True, True),
                          ("CGRIFF.DEF", "H3ab_spr.lod", True, True)])
        d = sp["defs"][0]
        self.assertEqual((d["blocks"], d["idle_block_present"], d["idle_frames"]), (3, True, 2))
        self.assertEqual(self.report()["findings"].count("SPRITE_NO_IDLE"), 0)
        for code in ("SPRITE_LOD_MISSING", "SPRITE_DEF_MISSING", "SPRITE_DEF_BAD"):
            self.assertNotIn(code, self.report()["findings"])

    def test_def_without_group_2(self):
        write(self.root, "H3sprite.lod", lod([("CPKMAN.DEF", no_group2_def())]))
        rep = self.report()
        d = rep["sprites"]["defs"][0]
        self.assertEqual(rep["sprites"]["layout"], "root")
        self.assertTrue(d["decodes"])
        self.assertEqual((d["blocks"], d["idle_block_present"], d["idle_frames"],
                          d["idle_frame0_nonempty"]), (2, False, None, False))
        self.assertIn("SPRITE_NO_IDLE", rep["findings"])

    def test_group_2_with_empty_frame_zero(self):
        write(self.root, "Data/H3sprite.lod", lod([("CPKMAN.DEF", empty_idle_def())]))
        d = self.report()["sprites"]["defs"][0]
        self.assertTrue(d["idle_block_present"])
        self.assertEqual(d["idle_frames"], 1)
        self.assertFalse(d["idle_frame0_nonempty"])

    def test_group_2_with_no_frames(self):
        write(self.root, "Data/H3sprite.lod", lod([("CPKMAN.DEF", def_blocks([[(2, 2)], [(2, 2)], []]))]))
        d = self.report()["sprites"]["defs"][0]
        self.assertEqual((d["idle_block_present"], d["idle_frames"], d["idle_frame0_nonempty"]),
                         (True, 0, False))

    def test_corrupt_def_and_corrupt_sprite_archive(self):
        write(self.root, "Data/H3sprite.lod", lod([("CPKMAN.DEF", b"junk")]))
        write(self.root, "Data/H3ab_spr.lod", b"garbage" * 30)
        rep = self.report()
        d = rep["sprites"]["defs"][0]
        self.assertEqual((d["found_in"], d["decodes"], d["error_type"]),
                         ("H3sprite.lod", False, "DefError"))
        lods = rep["sprites"]["lods"]
        self.assertEqual((lods[1]["present"], lods[1]["opens"], lods[1]["error_type"]),
                         (True, False, "LodFormatError"))
        self.assertIn("SPRITE_DEF_BAD", rep["findings"])
        self.assertIn("SPRITE_LOD_BAD", rep["findings"])

    def test_first_archive_wins_and_names_match_case_insensitively(self):
        write(self.root, "data/H3SPRITE.LOD", lod([("cpkman.def", no_group2_def())]))
        write(self.root, "data/h3ab_spr.lod", lod([("CPKMAN.DEF", idle_def())]))
        d = self.report()["sprites"]["defs"][0]
        self.assertEqual(d["found_in"], "H3sprite.lod")
        self.assertFalse(d["idle_block_present"])

    def test_data_dir_wins_over_root_and_nested_is_flagged(self):
        write(self.root, "H3sprite.lod", lod([("CPKMAN.DEF", no_group2_def())]))
        write(self.root, "Data/H3sprite.lod", lod([("CPKMAN.DEF", idle_def())]))
        sp = self.report()["sprites"]
        self.assertEqual(sp["layout"], "data")
        self.assertTrue(sp["defs"][0]["idle_block_present"])
        other = Path(self._tmp.name) / "nested"
        write(other, "game/Data/H3sprite.lod", lod([("CPKMAN.DEF", idle_def())]))
        self.assertEqual(real_report.build_report(other)["sprites"]["layout"], "nested")

    def test_matches_the_android_loader_contract(self):
        """The hard-coded names must not drift from what the Android code asks for."""
        kt_loader = REPO_ROOT / "android/app/src/main/kotlin/h3/app/SpriteLoader.kt"
        kt_plan = REPO_ROOT / "android/presenter/src/main/kotlin/h3/presenter/ui/SpriteLoadPlan.kt"
        if not (kt_loader.is_file() and kt_plan.is_file()):
            self.skipTest("android sources not in this tree")
        m = re.search(r"LOD_NAMES\s*=\s*listOf\(([^)]*)\)", kt_loader.read_text(encoding="utf-8"))
        self.assertIsNotNone(m)
        self.assertEqual(tuple(re.findall(r'"([^"]+)"', m.group(1))), real_report.SPRITE_LODS)
        m = re.search(r"DEFAULT_TABLE[^=]*=\s*linkedMapOf\((.*?)\n    \)",
                      kt_plan.read_text(encoding="utf-8"), re.S)
        self.assertIsNotNone(m)
        self.assertEqual(tuple(re.findall(r'to "([^"]+\.DEF)"', m.group(1))), real_report.SPRITE_DEFS)
        # pinned literals as well, so a drift in both places is still noticed
        self.assertEqual(real_report.SPRITE_LODS, ("H3sprite.lod", "H3ab_spr.lod"))
        self.assertEqual(real_report.SPRITE_DEFS, ("CPKMAN.DEF", "CLCBOW.DEF", "CGRIFF.DEF"))
        self.assertEqual(real_report.IDLE_GROUP, 2)


class MapParsing(Base):
    def test_maps_only_counted_under_a_maps_directory(self):
        write(self.root, "Maps/a.h3m", valid_map())
        write(self.root, "maps/sub/b.H3M", valid_map())
        write(self.root, "Other/c.h3m", valid_map())
        write(self.root, "d.h3m", valid_map())
        rep = self.report()
        self.assertEqual([m["name"] for m in rep["maps"]], ["Maps/a.h3m", "maps/sub/b.H3M"])

    def test_valid_map_header_and_objects(self):
        write(self.root, "Maps/ok.h3m", valid_map())
        m = self.report()["maps"][0]
        self.assertEqual((m["header_ok"], m["objects_ok"], m["error"]), (True, True, None))
        self.assertEqual((m["format"], m["map_size"], m["levels"]), ("SoD", 3, 1))
        self.assertFalse(m["skipped_too_large"])

    def test_header_ok_but_objects_truncated_names_the_stage(self):
        write(self.root, "Maps/noobj.h3m", valid_map(objects=False))
        rep = self.report()
        m = rep["maps"][0]
        self.assertEqual((m["header_ok"], m["objects_ok"]), (True, False))
        self.assertEqual(m["error"]["phase"], "objects")
        self.assertEqual(m["error"]["type"], "H3mError")
        self.assertEqual(m["error"]["reason"], "truncated")
        self.assertRegex(m["error"]["stage"], r"^[a-z][a-z0-9 _()\-]*$")
        self.assertIn("MAP_OBJECTS_FAILED", rep["findings"])
        self.assertNotIn("MAP_HEADER_FAILED", rep["findings"])

    def test_header_truncated_names_the_stage(self):
        raw = gzip.compress(TH.build(TH.SOD, size=3)[:20])
        write(self.root, "Maps/cut.h3m", raw)
        rep = self.report()
        m = rep["maps"][0]
        self.assertFalse(m["header_ok"])
        self.assertIsNone(m["objects_ok"])
        self.assertEqual(m["error"]["phase"], "header")
        self.assertEqual(m["error"]["reason"], "truncated")
        self.assertIsInstance(m["error"]["stage"], str)
        self.assertIn("MAP_HEADER_FAILED", rep["findings"])

    def test_hota_is_an_unsupported_format_with_its_id(self):
        write(self.root, "Maps/hota.h3m", struct.pack("<I", 0x20) + bytes(64))
        rep = self.report()
        e = rep["maps"][0]["error"]
        self.assertEqual((e["reason"], e["format_id"], e["phase"]), ("unsupported_format", 0x20, "header"))
        self.assertIn("MAP_UNSUPPORTED_FORMAT", rep["findings"])
        self.assertNotIn("MAP_HEADER_FAILED", rep["findings"])

    def test_unsupported_object_reports_class_and_subid_only(self):
        temps = [TH.tmpl("OK", 137, 0), TH.tmpl("BAD", 9999, 7)]
        objs = [(0, (0, 0, 0), "generic", {}, b""), (1, (1, 1, 0), "x", {}, b"\xAA" * 64)]
        raw = TH.map_with(TH.SOD, TH.e_objects(TH.SOD, temps, objs, []))
        write(self.root, "Maps/u.h3m", gzip.compress(raw))
        m = self.report()["maps"][0]
        self.assertTrue(m["header_ok"])
        self.assertFalse(m["objects_ok"])
        self.assertEqual((m["error"]["type"], m["error"]["reason"], m["error"]["class_id"],
                          m["error"]["subid"]),
                         ("H3mUnsupportedObject", "unsupported_object", 9999, 7))

    def test_error_inside_an_object_body_keeps_the_class_id(self):
        temps, objs, events = TH.object_fixture(TH.SOD)
        full = TH.map_with(TH.SOD, TH.e_objects(TH.SOD, temps, objs[:2], events))
        o = real_report.h3m.parse_h3m_bytes(full, objects=True).objects[1]  # the hero
        write(self.root, "Maps/b.h3m", gzip.compress(full[:o.offset + 20]))
        e = self.report()["maps"][0]["error"]
        self.assertEqual((e["phase"], e["reason"], e["stage"], e["class_id"], e["subid"]),
                         ("objects", "truncated", "object_body", 34, None))

    def test_garbage_and_bad_gzip(self):
        write(self.root, "Maps/g1.h3m", b"\x1f\x8bnot really gzip")
        write(self.root, "Maps/g2.h3m", b"")
        write(self.root, "Maps/g3.h3m", bytes(range(256)))
        reasons = {m["name"]: m["error"]["reason"] for m in self.report()["maps"]}
        self.assertEqual(reasons["Maps/g1.h3m"], "gzip")
        self.assertIn(reasons["Maps/g2.h3m"], {"truncated"})
        self.assertIn(reasons["Maps/g3.h3m"], {"unsupported_format", "invalid_value", "truncated"})

    def test_oversize_map_is_skipped(self):
        with mock.patch.object(real_report, "MAX_H3M_BYTES", 10):
            write(self.root, "Maps/big.h3m", bytes(11))
            write(self.root, "Maps/edge.h3m", bytes(10))
            maps = {m["name"]: m for m in self.report()["maps"]}
        self.assertTrue(maps["Maps/big.h3m"]["skipped_too_large"])
        self.assertIsNone(maps["Maps/big.h3m"]["error"])
        self.assertFalse(maps["Maps/edge.h3m"]["skipped_too_large"])
        self.assertIn("error", maps["Maps/edge.h3m"])
        self.assertIsNotNone(maps["Maps/edge.h3m"]["error"])
        # the real cap, pinned as a literal
        self.assertEqual(real_report.MAX_H3M_BYTES, 16 * 1024 * 1024)
        self.assertEqual(real_report.MAX_MEMBER_BYTES, 8 * 1024 * 1024)

    def test_oversize_map_does_not_raise_a_finding(self):
        with mock.patch.object(real_report, "MAX_H3M_BYTES", 10):
            write(self.root, "Maps/big.h3m", bytes(11))
            rep = self.report()
        self.assertNotIn("MAP_HEADER_FAILED", rep["findings"])

    def test_map_count_cap(self):
        with mock.patch.object(real_report, "MAX_H3M_FILES", 2):
            for n in "abc":
                write(self.root, f"Maps/{n}.h3m", valid_map())
            rep = self.report()
        self.assertEqual([m["name"] for m in rep["maps"]], ["Maps/a.h3m", "Maps/b.h3m"])
        self.assertTrue(rep["scan_truncated"])


class NoPayload(Base):
    def populate(self, root):
        members = [("SECRETNAME.DEF", idle_def()), ("CPKMAN.DEF", idle_def()),
                   ("PRIVATE.TXT", txt_bytes()), ("PIC.PCX", TP.indexed_2x2())]
        write(root, "Data/H3sprite.lod", lod(members))
        write(root, "Data/H3bitmap.lod", b"junk" * 20)
        write(root, "Maps/m.h3m", valid_map())
        write(root, "Maps/n.h3m", valid_map(objects=False))

    def test_keys_are_an_allowlist(self):
        self.populate(self.root)
        write(self.root, "Data/zzz.lod", lod([("X.DEF", b"bad")]))
        rep = self.report()
        keys = set(all_keys(rep))
        self.assertEqual(keys - ALLOWED_KEYS, set())
        # the allowlist is not vacuous: most of it is in use in this fixture
        self.assertGreaterEqual(len(keys & ALLOWED_KEYS), 55)
        text = real_report.render(rep)
        self.assertEqual(set(all_keys(json.loads(text))) - ALLOWED_KEYS, set())

    def test_every_string_has_a_safe_shape(self):
        self.populate(self.root)
        rep = self.report()
        for key, s in all_strings(rep):
            if key in ("name", "found_in"):
                self.assertRegex(s, NAME_OK.pattern, (key, s))
            elif key in ("type", "error_type"):
                self.assertRegex(s, TYPE_OK.pattern, (key, s))
            elif key in ("kind", "phase", "reason", "stage", "format", "layout", "platform",
                         "python", "h3re_version"):
                self.assertRegex(s, r"^[A-Za-z0-9 _()\-.+]{1,40}$", (key, s))
            elif key == "findings":
                self.assertRegex(s, r"^[A-Z_]+$", s)
            else:
                self.fail(f"unexpected string under {key!r}")

    def test_member_names_other_than_requested_defs_do_not_appear(self):
        self.populate(self.root)
        text = real_report.render(self.report())
        for leaked in ("SECRETNAME", "PRIVATE", "PIC.PCX", "Test Map", "A description",
                       "Orrin", "Bob", "Tavern", "Dragons", CANARY):
            self.assertNotIn(leaked, text)

    def test_hostile_file_names_are_sanitized(self):
        name = "Data/\u00e9vil\"\\<script>\n.lod"
        try:
            write(self.root, name, lod([]))
        except (OSError, ValueError):
            self.skipTest("file system rejects the name")
        rep = self.report()
        n = rep["archives"][0]["name"]
        self.assertRegex(n, NAME_OK.pattern)
        self.assertNotIn("script>", n)

    def test_platform_is_exactly_sys_platform(self):
        rep = self.report()
        self.assertEqual(rep["platform"], sys.platform)
        self.assertIn(rep["platform"], {"linux", "win32", "darwin", "cygwin", "freebsd"} | {sys.platform})
        self.assertRegex(rep["python"], r"^3\.\d+\.\d+$")
        self.assertEqual(rep["h3re_version"], "unversioned")

    def test_no_clock_path_or_user_data(self):
        self.populate(self.root)
        text = real_report.render(self.report())
        self.assertNotIn(self._tmp.name, text)
        self.assertNotIn(str(Path.home()), text)
        self.assertNotRegex(text, r"time|date|hash|sha|user|host", )

    def test_nothing_is_written_into_the_game_dir(self):
        self.populate(self.root)

        def snapshot():
            return sorted((str(p.relative_to(self.root)), p.stat().st_size, p.stat().st_mtime_ns)
                          for p in self.root.rglob("*"))
        before = snapshot()
        self.report()
        self.assertEqual(snapshot(), before)


class Determinism(Base):
    def test_same_input_same_bytes_and_creation_order_is_irrelevant(self):
        names = ["Data/b.lod", "Data/A.lod", "Data/a.lod", "Data/H3sprite.lod", "Data/Z.lod"]
        maps = ["Maps/z.h3m", "Maps/B.h3m", "Maps/a.h3m"]
        roots = []
        for order in (names, list(reversed(names))):
            r = Path(self._tmp.name) / f"g{len(roots)}"
            for n in order:
                write(r, n, lod([("CPKMAN.DEF", idle_def()), ("Q.DEF", b"x")]))
            for n in (maps if len(roots) == 0 else list(reversed(maps))):
                write(r, n, valid_map())
            roots.append(r)
        texts = [real_report.render(real_report.build_report(r)) for r in roots]
        self.assertEqual(texts[0], texts[1])
        self.assertEqual(texts[0], real_report.render(real_report.build_report(roots[0])))
        rep = json.loads(texts[0])
        got = [a["name"] for a in rep["archives"]]
        self.assertEqual(got, ["Data/A.lod", "Data/H3sprite.lod", "Data/Z.lod", "Data/a.lod", "Data/b.lod"])
        self.assertEqual([m["name"] for m in rep["maps"]], ["Maps/B.h3m", "Maps/a.h3m", "Maps/z.h3m"])
        self.assertEqual(rep["findings"], sorted(rep["findings"]))
        # json keys are sorted
        self.assertEqual(texts[0], json.dumps(rep, indent=2, sort_keys=True) + "\n")

    def test_order_is_by_relative_name_not_by_walk_order(self):
        for n in ("z.lod", "Data/c.lod", "Data/a.lod", "Data/Sub/b.lod"):
            write(self.root, n, lod([]))
        got = [a["name"] for a in self.report()["archives"]]
        self.assertEqual(got, ["Data/Sub/b.lod", "Data/a.lod", "Data/c.lod", "z.lod"])

    def test_names_that_sanitize_alike_keep_a_fixed_order(self):
        try:
            write(self.root, "\u00e9.lod", lod([("A.DEF", idle_def()), ("B.DEF", idle_def())]))
            write(self.root, "\u00e8.lod", lod([("A.DEF", idle_def())]))
        except (OSError, ValueError):
            self.skipTest("file system rejects the names")
        rep = self.report()
        self.assertEqual([a["name"] for a in rep["archives"]], ["?.lod", "?.lod"])
        self.assertEqual([a["entries"] for a in rep["archives"]], [1, 2])

    def test_directories_that_sanitize_alike_keep_a_fixed_order(self):
        names = ["d%s/a.lod" % c for c in "\u00e9\u00e8\u00ea\u00eb\u00e0\u00e1\u00e2\u00e3"]
        try:
            for i, n in enumerate(names):
                write(self.root, n, lod([("A%d.DEF" % k, idle_def()) for k in range(i + 1)]))
        except (OSError, ValueError):
            self.skipTest("file system rejects the names")
        # sorted by the raw directory name (code point): e0 e1 e2 e3 e8 e9 ea eb
        expected = [names.index("d%s/a.lod" % c) + 1 for c in "\u00e0\u00e1\u00e2\u00e3\u00e8\u00e9\u00ea\u00eb"]
        rep = self.report()
        self.assertEqual([a["entries"] for a in rep["archives"]], expected)

    def test_error_lists_are_sorted_by_type(self):
        # one DEF raising DefError and one member raising LodFormatError
        good = TL.member("X.DEF", idle_def(), compress=True)
        broken = (good[0], b"\xff" * len(good[1]), good[2], good[3], good[4])
        write(self.root, "a.lod", TL.build_lod([broken, TL.member("Y.DEF", b"junk")]))
        errs = self.kind(self.archive(self.report(), "a.lod"), "def")["errors"]
        self.assertEqual([e["type"] for e in errs], ["DefError", "LodFormatError"])


class Hostile(Base):
    def test_never_throws_on_hostile_bytes(self):
        rnd = random.Random(20260101)
        blobs = [b"", b"\x00", b"LOD\x00", b"LOD\x00" + struct.pack("<II", 200, 0xFFFFFFFF) + bytes(80),
                 b"LOD\x00" + struct.pack("<II", 200, 1 << 20) + bytes(80),
                 b"\xff" * 4096, bytes(100000), b"\x1f\x8b\x08\x00" + bytes(40),
                 gzip.compress(bytes(2 * 1024 * 1024)), struct.pack("<I", 0x1C) + b"\xff" * 50]
        blobs += [bytes(rnd.randrange(256) for _ in range(rnd.randrange(1, 400))) for _ in range(40)]
        good = lod([("CPKMAN.DEF", idle_def()), ("A.PCX", TP.indexed_2x2()), ("T.TXT", txt_bytes())])
        blobs += [good[:i] for i in range(0, len(good), 17)]
        mm = valid_map()
        blobs += [mm[:i] for i in range(0, len(mm), 7)]
        raw = bytearray(TH.build(TH.SOD, size=3) + TH.u32(0) * 3)
        for _ in range(40):
            mutated = bytearray(raw)
            for _ in range(3):
                mutated[rnd.randrange(len(mutated))] = rnd.randrange(256)
            blobs.append(gzip.compress(bytes(mutated)))
        for i, b in enumerate(blobs):
            write(self.root, f"Data/h{i:03d}.lod", b)
            write(self.root, f"Data/H3sprite{i:03d}.lod", b)
            write(self.root, f"Maps/m{i:03d}.h3m", b)
        write(self.root, "Data/H3sprite.lod", good[:200])
        rep = self.report(sample=50)  # must not raise
        text = real_report.render(rep)
        self.assertEqual(set(all_keys(json.loads(text))) - ALLOWED_KEYS, set())
        self.assertGreaterEqual(len(rep["findings"]), 6)
        self.assertEqual(rep["findings"], sorted(rep["findings"]))
        # the cap on files applies; the report is still complete JSON
        self.assertLessEqual(len(rep["archives"]), 200)
        self.assertLessEqual(len(rep["maps"]), 100)

    def test_hostile_content_inside_a_valid_container(self):
        junk = bytes(random.Random(7).randrange(256) for _ in range(5000))
        members = [("A.DEF", junk), ("B.PCX", junk), ("C.TXT", junk), ("D.TXT", b"\xff\xfe\x00\x80" * 50),
                   ("E.DEF", struct.pack("<4I", 0, 0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF) + bytes(800))]
        write(self.root, "Data/H3sprite.lod", lod(members + [("CPKMAN.DEF", junk)]))
        rep = self.report()
        self.assertTrue(rep["archives"][0]["opens"])
        self.assertEqual(rep["sprites"]["defs"][0]["error_type"], "DefError")

    def test_unexpected_exception_types_are_recorded_by_name(self):
        write(self.root, "a.lod", lod([("A.DEF", idle_def())]))
        with mock.patch.object(real_report.defimg, "parse_def", side_effect=RecursionError("secret text")):
            rep = self.report()
        d = self.kind(self.archive(rep, "a.lod"), "def")
        self.assertEqual(d["errors"], [{"type": "RecursionError", "count": 1}])
        self.assertNotIn("secret", real_report.render(rep))

    def test_exception_messages_never_reach_the_report(self):
        write(self.root, "a.lod", lod([("A.DEF", idle_def())]))
        write(self.root, "Maps/m.h3m", valid_map())
        boom = ValueError(CANARY)
        with mock.patch.object(real_report.defimg, "parse_def", side_effect=boom), \
                mock.patch.object(real_report.h3m, "parse_h3m", side_effect=boom), \
                mock.patch.object(real_report.lod.LodArchive, "open", side_effect=boom):
            rep = self.report()
        self.assertNotIn(CANARY, real_report.render(rep))
        self.assertEqual(rep["maps"][0]["error"]["type"], "ValueError")
        self.assertEqual(rep["maps"][0]["error"]["reason"], "other")


class Cli(Base):
    def run_main(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def test_stdout_json_when_no_out(self):
        write(self.root, "Data/H3sprite.lod", lod([("CPKMAN.DEF", idle_def())]))
        code, out, err = self.run_main("real-report", str(self.root))
        self.assertEqual((code, err), (0, ""))
        rep = json.loads(out)
        self.assertEqual(rep["report_schema"], 1)
        self.assertEqual(out, real_report.render(real_report.build_report(self.root)))

    def test_out_file_and_summary_line(self):
        write(self.root, "Data/H3sprite.lod", lod([("CPKMAN.DEF", idle_def())]))
        dest = Path(self._tmp.name) / "report.json"
        code, out, err = self.run_main("real-report", str(self.root), "--out", str(dest))
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(json.loads(dest.read_text(encoding="utf-8"))["summary"]["archives_found"], 1)
        self.assertTrue(out.startswith("wrote "))
        self.assertEqual(len(out.splitlines()), 1)
        self.assertNotIn("{", out)
        self.assertEqual(dest.read_bytes(), real_report.render(real_report.build_report(self.root)).encode())

    def test_missing_dir_exits_1_but_still_reports(self):
        code, out, err = self.run_main("real-report", str(self.root / "nope"))
        self.assertEqual(code, 1)
        self.assertIn("DATA_DIR_INVALID", json.loads(out)["findings"])
        self.assertEqual(err.count("\n"), 1)

    def test_refuses_to_write_inside_the_game_dir(self):
        dest = self.root / "report.json"
        code, out, err = self.run_main("real-report", str(self.root), "--out", str(dest))
        self.assertEqual(code, 1)
        self.assertFalse(dest.exists())
        self.assertIn("cannot write report", err)
        json.loads(out)  # report still printed

    def test_unwritable_out_exits_1(self):
        code, out, err = self.run_main("real-report", str(self.root), "--out",
                                       str(Path(self._tmp.name) / "no/such/dir/r.json"))
        self.assertEqual(code, 1)
        self.assertIn("cannot write report", err)

    def test_sample_option_and_usage_error(self):
        write(self.root, "a.lod", lod([("A.DEF", idle_def()), ("B.DEF", idle_def())]))
        code, out, _ = self.run_main("real-report", str(self.root), "--sample", "1")
        self.assertEqual(json.loads(out)["archives"][0]["kinds"][0]["sampled"], 1)
        with self.assertRaises(SystemExit) as cm, contextlib.redirect_stderr(io.StringIO()):
            main(["real-report"])
        self.assertEqual(cm.exception.code, 2)

    def test_runs_as_a_module(self):
        import subprocess
        write(self.root, "a.lod", lod([]))
        p = subprocess.run([sys.executable, "-m", "h3re", "real-report", str(self.root)],
                           cwd=PKG_ROOT, capture_output=True, text=True, timeout=60)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(json.loads(p.stdout)["summary"]["archives_found"], 1)


if __name__ == "__main__":
    unittest.main()
