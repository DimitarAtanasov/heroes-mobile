import hashlib
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import vector_cache  # noqa: E402

from h3re import adventure as A  # noqa: E402
from h3re import vectors as V  # noqa: E402
from h3re import vectors_adventure as VA  # noqa: E402

GOLDEN_PIN = "179c570020d05be9a53c265a76517a4bb9f398c92f37d19485d30f804f703420"


class TestAdventureVectors(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = vector_cache.module_doc(VA)[VA.FILE]
        cls.cases = {c["name"]: c for c in cls.doc["cases"]}

    def test_generation_is_deterministic(self):
        # Until the lead wires the module into vectors.EXTRA_VECTOR_MODULES, compare against an
        # independent second generation directly.
        if "vectors_adventure" in V.EXTRA_VECTOR_MODULES:
            vector_cache.assert_module_deterministic(self, VA)
        else:
            self.assertEqual(V._dump(VA.generate()[VA.FILE]), V._dump(self.doc))

    def test_non_trivial_and_covering(self):
        steps = [s for c in self.doc["cases"] for s in c["steps"]]
        self.assertGreaterEqual(len(self.doc["cases"]), 20)
        self.assertGreaterEqual(len(steps), 1000)
        self.assertEqual({s["command"]["type"] for s in steps}, {c.__name__ for c in VA.COMMANDS})
        self.assertEqual({e["type"] for s in steps for e in s["events"]},
                         {e.__name__ for e in VA.EVENTS})
        pols = {c["policy"] for c in self.doc["cases"]}
        self.assertEqual(pols, {n for n, _ in VA._policies()})
        self.assertGreaterEqual(len(self.doc["illegal_cases"]), 500)

    def test_golden_reproduces_the_pin(self):
        last = self.cases["golden"]["steps"][-1]
        self.assertEqual(last["sha256"], GOLDEN_PIN)
        self.assertEqual(json.loads(last["canonical"])["day"], 15)

    def test_steps_match_the_reference(self):
        for c in self.doc["cases"]:
            texts = [c["initial"]["canonical"]] + [s["canonical"] for s in c["steps"]]
            for t, s in zip(texts[1:], c["steps"]):
                self.assertEqual(hashlib.sha256(t.encode("ascii")).hexdigest(), s["sha256"])
            self.assertGreater(len(set(texts)), 3, c["name"])

    def test_illegal_cases_are_rejected_by_python(self):
        msgs = {ic["message"] for ic in self.doc["illegal_cases"]}
        for want in ("game already started", "game not started", "no such hero",
                     "hero does not belong to the current player",
                     "destination not reachable today", "not player True's turn",
                     "not a tile: 'ab'"):
            self.assertIn(want, msgs)

    def test_nonbmp_guard_ids_are_in_code_point_order(self):
        # Python sorts str by code point; UTF-16 order puts U+1F600 (D83D DE00) before U+FB01.
        case = self.cases["golden-guards-nonbmp"]
        ids = [g["id"] for g in json.loads(case["initial"]["canonical"])["guards"]]
        self.assertIn("\ufb01", ids)
        self.assertIn("\U0001f600", ids)
        self.assertEqual(ids, sorted(ids))
        self.assertNotEqual(ids, sorted(ids, key=lambda s: s.encode("utf-16-be")))
        for st in case["steps"]:
            self.assertEqual(
                [g["id"] for g in json.loads(st["canonical"])["guards"]], ids)

    def test_repr_probes_follow_python_repr(self):
        msgs = {ic["message"] for ic in self.doc["illegal_cases"]}
        for want in (
                r"""not player "it's"'s turn""",
                r"""not player 'tab\there''s turn""",
                r"""not player '\x00\x1f\x7f''s turn""",
                r"""not player '\x80\x9f\xa0\xad''s turn""",
                r"""not player '\u2028\u2029''s turn""",
                r"""not player '\U0010ffff''s turn""",
                r"""not player '\ud800''s turn""",
                r"""not player {'a': 1, 'b': [1, {'c': None}], "c'd": True}'s turn""",
                r"""not a tile: ({'a': 1}, 2)"""):
            self.assertIn(want, msgs)

    def test_policy_cases_cover_bounds_and_types(self):
        pc = {c["name"]: c for c in self.doc["policy_cases"]}
        self.assertIsNone(pc["bound-ok"]["error"])
        for name in ("diagonal_num-bool", "diagonal_num-1e8", "move_cost_floor-2e9",
                     "pathfinding_flat-bool", "road_cost-huge", "diagonal_num-2pow70"):
            self.assertIsInstance(pc[name]["error"], str, name)
        for c in self.doc["policy_cases"]:
            try:
                A.AdventurePolicy(**{k: (tuple(v) if isinstance(v, list) else v)
                                     for k, v in c["policy"].items()})
                got = None
            except ValueError as e:
                got = str(e)
            self.assertEqual(got, c["error"], c["name"])

    def test_policy_cases_cover_flags(self):
        pc = {c["name"]: c for c in self.doc["policy_cases"]}
        for f in VA.A._POLICY_FLAGS:
            for kind in ("int1", "int0", "null", "str"):
                self.assertEqual(pc["%s-%s" % (f, kind)]["error"], "%s must be a bool" % f)
        # Order: flags first, in field order, before the other checks.
        self.assertEqual(pc["order-flag-before-cost_from"]["error"],
                         "road_needs_both must be a bool")
        self.assertEqual(pc["order-flags-in-field-order"]["error"],
                         "diagonal_moves must be a bool")
        self.assertEqual(pc["order-flag-before-int"]["error"],
                         "income_on_first_day must be a bool")

    def test_edge_day_cases_pass_int_and_reach_long_max(self):
        edge = {n: c for n, c in self.cases.items() if c["kind"] == "edge"}
        self.assertEqual(set(edge), {"edge-day-int-max", "edge-day-int-max-week",
                                     "edge-day-2pow62-week", "edge-day-long-max"})
        days = lambda c: [json.loads(st["canonical"])["day"] for st in c["steps"]]  # noqa: E731
        self.assertEqual(json.loads(edge["edge-day-int-max"]["initial"]["canonical"])["day"],
                         2 ** 31 - 1)
        self.assertIn(2 ** 31, days(edge["edge-day-int-max"]))
        self.assertEqual(days(edge["edge-day-long-max"])[-1], 2 ** 63 - 1)
        for c in edge.values():
            kinds = {e["type"] for st in c["steps"] for e in st["events"]}
            self.assertLessEqual({"DayStarted", "TurnStarted"}, kinds, c["name"])
        for n in ("edge-day-int-max-week", "edge-day-2pow62-week"):
            kinds = {e["type"] for st in edge[n]["steps"] for e in st["events"]}
            self.assertIn("WeekStarted", kinds, n)
        big = [e for st in edge["edge-day-2pow62-week"]["steps"] for e in st["events"]
               if e["type"] == "WeekStarted"]
        self.assertGreater(big[0]["week"], 2 ** 31 - 1)

    def test_constants_mirror_the_module(self):
        k = self.doc["constants"]
        self.assertEqual(k["terrain_cost"], A.TERRAIN_COST)
        self.assertEqual(k["speed_mp"], list(A._SPEED_MP))
        self.assertEqual(k["logistics_pct"], list(A.LOGISTICS_PCT))


if __name__ == "__main__":
    unittest.main()
