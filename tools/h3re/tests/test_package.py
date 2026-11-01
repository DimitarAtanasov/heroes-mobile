"""Tests for the h3re package's public surface (__all__ and import behaviour)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

PKG_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PKG_ROOT)

import h3re  # noqa: E402


def _run_isolated(code: str, env: dict | None = None,
                  cwd: str = PKG_ROOT) -> subprocess.CompletedProcess:
    """Run ``code`` in a fresh interpreter (package root as cwd by default).

    ``env`` entries are added to a copy of the environment; ``PYTHONPATH`` is
    set so a different ``cwd`` still finds the package."""
    full = dict(os.environ)
    full["PYTHONPATH"] = PKG_ROOT
    full.update(env or {})
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=cwd,
        env=full,
        capture_output=True,
        text=True,
        timeout=60,
    )


class TestAll(unittest.TestCase):
    def test_every_name_in_all_resolves(self):
        self.assertTrue(h3re.__all__)
        for name in h3re.__all__:
            with self.subTest(name=name):
                self.assertTrue(hasattr(h3re, name))
                self.assertIsNotNone(getattr(h3re, name))

    def test_all_has_no_duplicates(self):
        self.assertEqual(len(h3re.__all__), len(set(h3re.__all__)))

    def test_star_import_matches_all(self):
        ns: dict = {}
        exec("from h3re import *", ns)
        exported = {k for k in ns if not k.startswith("__")}
        self.assertEqual(exported, set(h3re.__all__))


class TestBattleExports(unittest.TestCase):
    def test_battle_exposed_as_submodule_only(self):
        from h3re import battle

        self.assertIn("battle", h3re.__all__)
        self.assertIs(h3re.battle, battle)
        # generic names must not leak into the package namespace
        for name in ("apply", "Stack", "Hero", "cells"):
            with self.subTest(name=name):
                self.assertNotIn(name, h3re.__all__)

    def test_sibling_modules_not_imported(self):
        proc = _run_isolated(
            "import sys, h3re\n"
            "bad = [m for m in ('h3re.battle_ai', 'h3re.battle_cli', 'h3re.adventure')"
            " if m in sys.modules]\n"
            "assert not bad, bad\n"
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)


class TestImportSideEffects(unittest.TestCase):
    def test_fresh_import_prints_nothing(self):
        proc = _run_isolated("import h3re")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout, "")
        self.assertEqual(proc.stderr, "")

    def test_fresh_import_opens_only_the_pack_files(self):
        code = (
            "import builtins, io\n"
            "opened = []\n"
            "_real_open = builtins.open\n"
            "def _spy(*a, **k):\n"
            "    opened.append(a[0] if a else k.get('file'))\n"
            "    return _real_open(*a, **k)\n"
            "builtins.open = _spy\n"
            "io.open = _spy\n"
            "import h3re\n"
            "import os\n"
            "names = [os.path.basename(str(p)) for p in opened]\n"
            "assert names == ['rules.json', 'battle_policy.json'], opened\n"
        )
        proc = _run_isolated(code)
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_each_submodule_imports_standalone(self):
        # Importing any submodule first in a fresh process must succeed,
        # which guards against circular-import regressions.
        for mod in ("battle", "defimg", "h3m", "lod", "pcx", "rng", "rules", "txt"):
            with self.subTest(module=mod):
                proc = _run_isolated(f"import h3re.{mod}")
                self.assertEqual(proc.returncode, 0, proc.stderr)


_PROBE = (
    "import json\n"
    "from h3re import battle as B, rules as R\n"
    "cr = B.Creature(name='a', attack=4, defense=4, dmg_min=1, dmg_max=3, hp=10, speed=4)\n"
    "s = B.create_battle('p', [B.StackSetup(cr, 5)], [B.StackSetup(cr, 5)])\n"
    "print(json.dumps({'dir': R.RULES_DIR, 'rules_hash': R.RULES_HASH,\n"
    "  'state_rules_hash': s.rules_hash, 'hash': B.state_hash(s),\n"
    "  'die': R.MORALE_DIE,\n"
    "  'luck': [R.luck_chance(1).denominator],\n"
    "  'good': [R.good_morale_chance(1).denominator],\n"
    "  'bad': [R.bad_morale_chance(-1).denominator]}))\n"
)


def _probe(env=None, cwd=PKG_ROOT):
    proc = _run_isolated(_PROBE, env, cwd)
    return proc


def _repo_data_dir():
    return os.path.abspath(os.path.join(PKG_ROOT, "..", "..", "data"))


class TestRulesPackIdentity(unittest.TestCase):
    """The loaded rules pack is part of the battle state hash."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def _pack(self, name, **changes):
        d = os.path.join(self.tmp.name, name)
        shutil.copytree(_repo_data_dir(), d)
        if changes:
            path = os.path.join(d, "rules.json")
            with open(path, encoding="utf-8") as f:
                rules = json.load(f)
            rules.update(changes)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(rules, f)
        return d

    def test_different_packs_give_different_initial_hashes(self):
        base = _probe()
        self.assertEqual(base.returncode, 0, base.stderr)
        base = json.loads(base.stdout)
        same = json.loads(_probe({"H3_DATA_PACK_DIR": self._pack("same")}).stdout)
        other = _probe({"H3_DATA_PACK_DIR": self._pack("other", hate_bonus=[3, 4])})
        self.assertEqual(other.returncode, 0, other.stderr)
        other = json.loads(other.stdout)
        # an identical copy of the pack in another directory is the same pack
        self.assertEqual(same["hash"], base["hash"])
        self.assertEqual(same["rules_hash"], base["rules_hash"])
        # a different pack: different rules hash, carried into the state, and
        # so a different state hash at step 0
        self.assertNotEqual(other["rules_hash"], base["rules_hash"])
        self.assertEqual(other["state_rules_hash"], other["rules_hash"])
        self.assertNotEqual(other["hash"], base["hash"])

    def test_one_die_drives_luck_and_both_morales(self):
        base = json.loads(_probe().stdout)
        self.assertEqual(base["die"], 24)
        self.assertEqual((base["luck"], base["good"], base["bad"]), ([24], [24], [24]))
        wide = self._pack("die30", morale_die=30)
        out = _probe({"H3_DATA_PACK_DIR": wide})
        self.assertEqual(out.returncode, 0, out.stderr)
        out = json.loads(out.stdout)
        self.assertEqual(out["die"], 30)
        self.assertEqual((out["luck"], out["good"], out["bad"]), ([30], [30], [30]))

    def test_relative_pack_dir_is_made_absolute_once(self):
        pack = self._pack("rel")
        rel = os.path.relpath(pack, self.tmp.name)
        proc = _probe({"H3_DATA_PACK_DIR": rel}, cwd=self.tmp.name)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = json.loads(proc.stdout)
        self.assertTrue(os.path.isabs(out["dir"]))
        self.assertEqual(os.path.realpath(out["dir"]), os.path.realpath(pack))
        # a chdir after import does not change the recorded directory
        code = (
            "import os, tempfile\n"
            "from h3re import datapack as D, rules as R\n"
            "before = (D.DEFAULT_DIR, D.LOADED_DIR, R.RULES_DIR)\n"
            "os.chdir(tempfile.gettempdir())\n"
            "assert before == (D.DEFAULT_DIR, D.LOADED_DIR, R.RULES_DIR), before\n"
            "assert all(os.path.isabs(p) for p in before), before\n"
            "D.load_dir()\n"
        )
        proc = _run_isolated(code, {"H3_DATA_PACK_DIR": rel}, cwd=self.tmp.name)
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_unusable_pack_dir_is_a_clear_error(self):
        missing = os.path.join(self.tmp.name, "does-not-exist")
        proc = _probe({"H3_DATA_PACK_DIR": missing})
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("DataPackError", proc.stderr)
        self.assertIn("not a directory", proc.stderr)
        self.assertIn("H3_DATA_PACK_DIR", proc.stderr)
        # a file instead of a directory is just as unusable
        afile = os.path.join(self.tmp.name, "afile")
        with open(afile, "w") as f:
            f.write("x")
        proc = _probe({"H3_DATA_PACK_DIR": afile})
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("not a directory", proc.stderr)

    def test_policy_defaults_follow_the_pack_dir(self):
        d = self._pack("pol")
        path = os.path.join(d, "battle_policy.json")
        with open(path, encoding="utf-8") as f:
            pol = json.load(f)
        pol["range_penalty_beyond"] = 7
        with open(path, "w", encoding="utf-8") as f:
            json.dump(pol, f)
        code = (
            "import json\n"
            "from h3re import battle as B\n"
            "cr = B.Creature(name='a', attack=4, defense=4, dmg_min=1, dmg_max=3, hp=10, speed=4)\n"
            "s = B.create_battle('p', [B.StackSetup(cr, 5)], [B.StackSetup(cr, 5)])\n"
            "print(json.dumps([B.BattlePolicy().range_penalty_beyond, B.state_hash(s),"
            " B.POLICY_HASH]))\n"
        )
        base = json.loads(_run_isolated(code).stdout)
        proc = _run_isolated(code, {"H3_DATA_PACK_DIR": d})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        other = json.loads(proc.stdout)
        self.assertEqual((base[0], other[0]), (10, 7))
        self.assertNotEqual(other[1], base[1])
        self.assertNotEqual(other[2], base[2])

    def test_adventure_reads_no_pack_value(self):
        # adventure.py is independent of rules.json, which is why GameState
        # carries no rules hash (battle.md section 10). If this fails, add it.
        proc = _run_isolated(
            "import sys\n"
            "import h3re.adventure as A\n"
            "assert not hasattr(A, 'rules') and not hasattr(A, 'datapack')\n"
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)


if __name__ == "__main__":
    unittest.main()
