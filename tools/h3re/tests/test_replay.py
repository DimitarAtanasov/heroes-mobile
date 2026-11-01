"""Tests for the replay file format (h3re/replay.py, `replay` subcommands)."""

from __future__ import annotations

import contextlib
import io
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PKG_ROOT.parents[1]
sys.path.insert(0, str(PKG_ROOT))

from h3re import battle as B  # noqa: E402
from h3re import replay  # noqa: E402
from h3re.__main__ import main  # noqa: E402

# Same value as GoldenTest.PINNED in tests/test_battle.py (not re-pinned here).
GOLDEN_PINNED = "fbe9015bde1b6e5c165c08fc1604f98ea7c3cdf09cc38528ec2fda496f040e2b"
SEED = 12345


def golden_scenario():
    text = (REPO_ROOT / "docs" / "specs" / "battle-scenario.md").read_text(encoding="utf-8")
    return json.loads(re.search(r"```json\n(.*?)\n```", text, re.S).group(1))


def reseal(data, header=None, body=None, **header_changes):
    """Rebuild a file with a valid checksum after changing header or body."""
    doc = json.loads(data)
    h = dict(doc["header"] if header is None else header)
    h.update(header_changes)
    b = doc["body"] if body is None else body
    return replay._seal(h, b)


class ReplayTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scn = golden_scenario()
        cls.cmds = replay.run_chooser(cls.scn, SEED, "scripted")
        cls.data = replay.record(cls.scn, cls.cmds, SEED)

    def test_round_trip_golden(self):
        header = replay.verify(self.data)
        self.assertEqual(header["final_hash"], GOLDEN_PINNED)
        self.assertEqual(header["seed"], SEED)
        self.assertEqual(header["battle_id"], "golden")
        self.assertEqual(header["kind"], "battle")
        self.assertEqual(header["format_version"], replay.FORMAT_VERSION)
        self.assertEqual(header["rules_hash"], replay.rules.RULES_HASH)
        self.assertEqual(header["policy_hash"], B.POLICY_HASH)
        h, scn, cmds, final = replay.load(self.data)
        self.assertEqual(scn, self.scn)
        self.assertEqual(cmds, self.cmds)
        self.assertEqual(B.state_hash(final), GOLDEN_PINNED)
        self.assertEqual(replay.info(self.data), header)

    def test_bytes_deterministic_and_canonical(self):
        again = replay.record(self.scn, self.cmds, SEED)
        self.assertEqual(self.data, again)
        # key order of the input scenario does not matter
        shuffled = json.loads(json.dumps(self.scn), object_pairs_hook=lambda p: dict(reversed(p)))
        self.assertEqual(replay.record(shuffled, self.cmds, SEED), self.data)
        text = self.data.decode("ascii")
        self.assertNotIn(" ", text.replace("pikeman", ""))  # no whitespace separators
        self.assertNotRegex(text, r"\d\.\d")
        self.assertEqual(self.data, replay._canon(json.loads(text)))

    def test_unsupported_version(self):
        for v in (0, 2, 99):
            with self.assertRaises(replay.UnsupportedVersion):
                replay.verify(reseal(self.data, format_version=v))

    def test_unsupported_kind(self):
        with self.assertRaises(replay.UnsupportedKind):
            replay.verify(reseal(self.data, kind="adventure"))
        with self.assertRaises(replay.UnsupportedKind):
            replay.record(self.scn, self.cmds, SEED, kind="adventure")

    def test_mismatched_packs(self):
        for key, exc in (("rules_hash", replay.MismatchedRulesPack),
                         ("policy_hash", replay.MismatchedPolicy),
                         ("creatures_hash", replay.MismatchedCreatures)):
            with self.assertRaises(exc):
                replay.verify(reseal(self.data, **{key: "0" * 64}))
            # info does not need the packs to match
            replay.info(reseal(self.data, **{key: "0" * 64}))

    def test_tampered(self):
        doc = json.loads(self.data)
        doc["header"]["seed"] += 1
        with self.assertRaises(replay.Tampered):
            replay.verify(replay._canon(doc))
        doc = json.loads(self.data)
        doc["body"]["commands"][3]["stack"] = 99
        with self.assertRaises(replay.Tampered):
            replay.verify(replay._canon(doc))
        doc = json.loads(self.data)
        doc["checksum"] = "0" * 64
        with self.assertRaises(replay.Tampered):
            replay.verify(replay._canon(doc))

    def test_resealed_changes_diverge(self):
        with self.assertRaises(replay.Diverged):
            replay.verify(reseal(self.data, final_hash="0" * 64))
        with self.assertRaises(replay.Diverged):
            replay.verify(reseal(self.data, seed=SEED + 1))
        doc = json.loads(self.data)
        body = doc["body"]
        body["commands"] = body["commands"][:5] + [{"type": "Move", "stack": 0, "dest": [0, 0]}]
        with self.assertRaises(replay.ReplayError):
            replay.verify(reseal(self.data, body=body, command_count=6))

    def test_malformed(self):
        for data in (b"[]", b"{}", b"null", b"\xff\xfe", b'{"a":1.5}',
                     self.data + b"x", self.data + b"\n"):
            with self.assertRaises(replay.ReplayError, msg=repr(data[:20])):
                replay.verify(data)
        doc = json.loads(self.data)
        doc["header"]["extra"] = 1
        with self.assertRaises(replay.ReplayError):
            replay.verify(reseal(self.data, header=doc["header"]))

    def test_truncation_at_every_cut_point(self):
        for cut in range(len(self.data)):
            with self.assertRaises(replay.Truncated, msg=f"cut {cut}"):
                replay.verify(self.data[:cut])

    def test_record_rejects_bad_input(self):
        with self.assertRaises(replay.ReplayError):
            replay.record(self.scn, self.cmds, 1.5)
        with self.assertRaises(replay.ReplayError):
            replay.record({"battle_id": "x"}, [], SEED)
        bad = dict(self.scn, extra=1.5)
        with self.assertRaises(replay.ReplayError):
            replay.record(bad, self.cmds, SEED)
        with self.assertRaises(replay.Diverged):
            replay.record(self.scn, [B.Wait(0)], SEED)


class ReplayCliTest(unittest.TestCase):
    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def test_record_verify_info(self):
        with tempfile.TemporaryDirectory() as d:
            scn = Path(d) / "s.json"
            scn.write_text(json.dumps(golden_scenario()), encoding="utf-8")
            f1, f2 = str(Path(d) / "a.h3r"), str(Path(d) / "b.h3r")
            for f in (f1, f2):
                code, _, err = self.run_cli("replay", "record", str(scn), "--seed", "12345",
                                            "--chooser", "scripted", "-o", f)
                self.assertEqual((code, err), (0, ""))
            self.assertEqual(Path(f1).read_bytes(), Path(f2).read_bytes())
            code, out, _ = self.run_cli("replay", "verify", f1)
            self.assertEqual(code, 0)
            self.assertIn(GOLDEN_PINNED, out)
            code, out, _ = self.run_cli("replay", "info", f1)
            self.assertEqual(code, 0)
            self.assertIn(f"final_hash: {GOLDEN_PINNED}", out)

            data = Path(f1).read_bytes()
            bad = Path(d) / "bad.h3r"
            bad.write_bytes(data[:len(data) // 2])
            code, out, err = self.run_cli("replay", "verify", str(bad))
            self.assertEqual(code, 1)
            self.assertEqual(err.count("\n"), 1)
            self.assertTrue(err.startswith("h3re: error: Truncated"))
            self.assertNotIn("Traceback", err)
            code, _, err = self.run_cli("replay", "verify", str(Path(d) / "missing.h3r"))
            self.assertEqual(code, 1)
            self.assertEqual(err.count("\n"), 1)


if __name__ == "__main__":
    unittest.main()
