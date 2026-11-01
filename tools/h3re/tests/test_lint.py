import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..", "lint")))

import banned_api_lint as L  # noqa: E402


def rules(src):
    return sorted({v.rule for v in L.lint_source(src)})


GOOD = '''
from fractions import Fraction
from math import floor
import hashlib


def f(d, s):
    total = 0
    for k in sorted(d.keys()):
        total += d[k] // 2
    x = Fraction(1, 3) * 7
    n = sum(v for v in d.values())
    t = tuple(sorted(s))
    ok = 3 in s
    return floor(x) + total + n + len(t) + (1 if ok else 0)
'''

# One bad fixture per rule: (rule, source)
BAD = [
    ("FLOAT_LITERAL", "x = 1.5\n"),
    ("TRUE_DIV", "def f(a, b):\n    return a / b\n"),
    ("TRUE_DIV", "def f(a, b):\n    a /= b\n    return a\n"),
    ("FLOAT_CALL", "def f(a):\n    return float(a)\n"),
    ("MATH_FLOAT", "import math\ndef f(a):\n    return math.sqrt(a)\n"),
    ("MATH_FLOAT", "from math import sin\n"),
    ("BANNED_IMPORT", "import time\n"),
    ("BANNED_IMPORT", "from datetime import datetime\n"),
    ("BANNED_IMPORT", "import random\n"),
    ("BANNED_IMPORT", "import os\n"),
    ("BANNED_CALL", "def f():\n    print('x')\n"),
    ("BANNED_CALL", "def f():\n    return open('a')\n"),
    ("BANNED_CALL", "def f():\n    return input()\n"),
    ("BANNED_CALL", "import time\ndef f():\n    return time.time()\n"),
    ("ITER_UNORDERED", "def f(s):\n    for x in set(s):\n        pass\n"),
    ("ITER_UNORDERED", "def f(d):\n    return [k for k in d.keys()]\n"),
    ("ITER_UNORDERED", "def f(d):\n    for k, v in d.items():\n        pass\n"),
    ("ITER_UNORDERED", "def f(a):\n    s = set(a)\n    return list(s)\n"),
    ("ITER_UNORDERED", "def f(a):\n    s = {1, 2}\n    for x in s:\n        pass\n"),
    ("ENV_READ", "import os\nX = os.environ.get('A')\n"),
    ("ENV_READ", "import os\ndef f():\n    return os.getenv('A')\n"),
    ("ENV_READ", "import os as o\nX = o.environ['A']\n"),
    ("ENV_READ", "from os import environ\n"),
]


class LintTest(unittest.TestCase):
    def test_good_fixture_clean(self):
        self.assertEqual(L.lint_source(GOOD), [])

    def test_bad_fixtures(self):
        for rule, src in BAD:
            self.assertIn(rule, rules(src), src)

    def test_every_rule_has_a_bad_fixture(self):
        self.assertEqual({r for r, _ in BAD}, set(L.RULES))

    def test_math_int_functions_allowed(self):
        self.assertEqual(rules("import math\nx = math.floor(3) + math.isqrt(9)\n"), [])

    def test_sorted_and_order_free_consumers(self):
        self.assertEqual(rules("def f(s):\n    return [x for x in sorted(s)]\n"), [])
        self.assertEqual(rules("def f(d):\n    return max(v for v in d.values())\n"), [])

    def test_inline_allow_needs_justification(self):
        ok = "x = 1.5  # det-lint-allow: FLOAT_LITERAL -- display only\n"
        bad = "x = 1.5  # det-lint-allow: FLOAT_LITERAL\n"
        self.assertEqual(rules(ok), [])
        self.assertEqual(rules(bad), ["FLOAT_LITERAL"])

    def test_allowlist(self):
        src = "def g(d):\n    for k in d.keys():\n        pass\n"
        v = L.lint_source(src, "m.py")
        self.assertEqual(len(v), 1)
        entry = {"file": "m.py", "rule": "ITER_UNORDERED", "function": "g",
                 "line": "for k in d.keys():", "justification": "order irrelevant"}
        self.assertEqual(L.apply_allowlist(v, [entry]), [])
        self.assertEqual(len(L.apply_allowlist(v, [dict(entry, function="h")])), 1)
        self.assertEqual(len(L.apply_allowlist(v, [dict(entry, line="for k in e.keys():")])), 1)
        self.assertEqual(len(L.apply_allowlist(v, [dict(entry, rule="TRUE_DIV")])), 1)

    def test_new_loop_in_allowlisted_function_is_flagged(self):
        entry = {"file": "m.py", "rule": "ITER_UNORDERED", "function": "g",
                 "line": "for k in d.keys():", "justification": "order irrelevant"}
        old = "def g(d):\n    for k in d.keys():\n        pass\n"
        self.assertEqual(L.apply_allowlist(L.lint_source(old, "m.py"), [entry]), [])
        # A different new unordered loop in the same function.
        new = old + "    for v in d.values():\n        pass\n"
        left = L.apply_allowlist(L.lint_source(new, "m.py"), [entry])
        self.assertEqual([(x.rule, x.text) for x in left],
                         [("ITER_UNORDERED", "for v in d.values():")])
        # A second copy of the very same statement is also flagged (count=1).
        dup = old + "    for k in d.keys():\n        pass\n"
        left = L.apply_allowlist(L.lint_source(dup, "m.py"), [entry])
        self.assertEqual(len(left), 1)
        self.assertEqual(left[0].line, 4)
        # ... unless the entry explicitly allows two.
        self.assertEqual(L.apply_allowlist(L.lint_source(dup, "m.py"),
                                           [dict(entry, count=2)]), [])

    def test_unused_entries_reported(self):
        entry = {"file": "m.py", "rule": "TRUE_DIV", "line": "x = a / b",
                 "justification": "n/a"}
        unused = []
        L.apply_allowlist([], [entry], unused)
        self.assertEqual(unused, [entry])

    def test_function_wide_entry_rejected(self):
        import json
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "a.json")
            with open(p, "w") as f:
                json.dump([{"file": "m.py", "rule": "ITER_UNORDERED", "function": "g",
                            "justification": "whole function"}], f)
            with self.assertRaises(ValueError):
                L.load_allowlist(p)

    def test_real_allowlist_is_line_scoped(self):
        entries = L.load_allowlist(L.DEFAULT_ALLOWLIST)
        self.assertTrue(entries)
        for e in entries:
            self.assertTrue(e["line"].strip(), e)

    def test_allowlist_requires_justification(self):
        import json
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "a.json")
            with open(p, "w") as f:
                json.dump([{"file": "m.py", "rule": "TRUE_DIV", "line": "x = a / b",
                            "justification": " "}], f)
            with self.assertRaises(ValueError):
                L.load_allowlist(p)

    def test_simulation_modules_pass(self):
        self.assertEqual(L.main([]), 0)

    def test_datapack_is_linted_by_default(self):
        self.assertIn("datapack.py", L.DEFAULT_MODULES)
        for m in L.SIM_MODULES:
            self.assertIn(m, L.DEFAULT_MODULES)

    def test_datapack_io_and_env_need_the_allowlist(self):
        path = os.path.join(L.DEFAULT_ROOT, "datapack.py")
        raw = L.lint_paths([path], [])
        rules_hit = {v.rule for v in raw}
        self.assertTrue({"BANNED_IMPORT", "BANNED_CALL", "ENV_READ"} <= rules_hit, rules_hit)
        self.assertEqual(L.lint_paths([path], L.load_allowlist(L.DEFAULT_ALLOWLIST)), [])

    def test_datapack_floats_and_unordered_iteration_still_banned(self):
        # The datapack allowlist is line-scoped, so new violations are caught.
        entries = L.load_allowlist(L.DEFAULT_ALLOWLIST)
        for src, rule in (("x = 0.5\n", "FLOAT_LITERAL"),
                          ("def f(a, b):\n    return a / b\n", "TRUE_DIV"),
                          ("def f(d):\n    for k in d.keys():\n        pass\n",
                           "ITER_UNORDERED")):
            left = L.apply_allowlist(L.lint_source(src, "datapack.py"), entries)
            self.assertEqual([v.rule for v in left], [rule])


if __name__ == "__main__":
    unittest.main()
