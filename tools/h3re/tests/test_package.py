"""Tests for the h3re package's public surface (__all__ and import behaviour)."""

from __future__ import annotations

import os
import subprocess
import sys
import unittest

PKG_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PKG_ROOT)

import h3re  # noqa: E402


def _run_isolated(code: str) -> subprocess.CompletedProcess:
    """Run ``code`` in a fresh interpreter with the package root as cwd."""
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=PKG_ROOT,
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

    def test_fresh_import_opens_no_files(self):
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
            "assert opened == [], opened\n"
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


if __name__ == "__main__":
    unittest.main()
