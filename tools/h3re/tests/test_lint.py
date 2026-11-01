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
                 "justification": "order irrelevant"}
        self.assertEqual(L.apply_allowlist(v, [entry]), [])
        other = dict(entry, function="h")
        self.assertEqual(len(L.apply_allowlist(v, [other])), 1)

    def test_allowlist_requires_justification(self):
        import json
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "a.json")
            with open(p, "w") as f:
                json.dump([{"file": "m.py", "rule": "TRUE_DIV", "justification": " "}], f)
            with self.assertRaises(ValueError):
                L.load_allowlist(p)

    def test_simulation_modules_pass(self):
        self.assertEqual(L.main([]), 0)


if __name__ == "__main__":
    unittest.main()
