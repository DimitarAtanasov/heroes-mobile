"""Tests for the battle text simulator (h3re/battle_cli.py, `battle-sim`).

Scenarios are synthetic or the golden scenario from docs/specs/battle-scenario.md.
No game files are used or required.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import re
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

PKG_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PKG_ROOT.parents[1]
sys.path.insert(0, str(PKG_ROOT))

from h3re import battle as B  # noqa: E402
from h3re import battle_cli  # noqa: E402
from h3re.__main__ import main  # noqa: E402

SCENARIO_DOC = REPO_ROOT / "docs" / "specs" / "battle-scenario.md"

# Same value as GoldenTest.PINNED in tests/test_battle.py.
# Re-pinned with it on 2026-11-01 (battle.md section 10).
GOLDEN_PINNED = "2191ae97fb22c8d15389d3e54c1a1eb6569a8d53630e0af647bd4ca97ca0d67d"


def golden_scenario() -> dict:
    """The first ```json block of the spec doc is the golden scenario."""
    text = SCENARIO_DOC.read_text(encoding="utf-8")
    match = re.search(r"```json\n(.*?)\n```", text, re.S)
    assert match, "no json block in battle-scenario.md"
    return json.loads(match.group(1))


def tiny_scenario() -> dict:
    """Two stacks, small enough that the scripted player finishes it."""
    return {
        "battle_id": "tiny",
        "creatures": {
            "swordsman": {"attack": 9, "defense": 6, "dmg_min": 4, "dmg_max": 6,
                          "hp": 20, "speed": 5},
            "imp": {"attack": 3, "defense": 2, "dmg_min": 1, "dmg_max": 2,
                    "hp": 4, "speed": 6},
        },
        "attackers": [{"creature": "swordsman", "count": 5}],
        "defenders": [{"creature": "imp", "count": 3}],
    }


class _Run:
    """Outcome of one battle_cli.run() call."""

    def __init__(self, rc, out, err):
        self.rc, self.out, self.err = rc, out, err


class CliTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)

    def write(self, data, name="scenario.json") -> Path:
        path = self.dir / name
        text = data if isinstance(data, str) else json.dumps(data)
        path.write_text(text, encoding="utf-8")
        return path

    def run_sim(self, scenario, seed=12345, chooser="first-legal", stdin_text=""):
        out, err = io.StringIO(), io.StringIO()
        rc = battle_cli.run(str(scenario), seed, chooser,
                            stdin=io.StringIO(stdin_text), stdout=out, stderr=err)
        return _Run(rc, out.getvalue(), err.getvalue())

    def assertFailsCleanly(self, result):
        """Exit 1, a final ``h3re: error:`` line, and no traceback."""
        self.assertEqual(result.rc, battle_cli.EXIT_FAILURE, result.err)
        self.assertEqual(result.err.count("h3re: error:"), 1, result.err)
        last = result.err.rstrip("\n").splitlines()[-1]
        self.assertTrue(last.startswith("h3re: error: "), result.err)
        self.assertNotIn("Traceback", result.err)


class GoldenScenarioTest(CliTestCase):
    def test_golden_json_matches_pinned_hash(self):
        path = self.write(golden_scenario(), "golden.json")
        result = self.run_sim(path, seed=12345, chooser="scripted")
        self.assertEqual(result.rc, 0, result.err)
        self.assertIn("winner: defender\n", result.out)
        self.assertTrue(result.out.endswith(f"state hash: {GOLDEN_PINNED}\n"), result.out[-200:])

    def test_golden_json_builds_same_state_as_golden_setup(self):
        # Same construction as golden_setup() in tests/test_battle.py.
        pike = B.Creature("pikeman", 4, 5, 1, 3, 10, 4)
        archer = B.Creature("archer", 6, 3, 2, 3, 10, 4, shots=12)
        wolf = B.Creature("wolf", 7, 5, 2, 5, 15, 8, strikes_twice=True)
        gnoll = B.Creature("gnoll", 6, 7, 2, 4, 13, 6, double_wide=True, hates=("pikeman",))
        ref = B.create_battle(
            "golden",
            [B.StackSetup(pike, 30, morale=1, luck=1), B.StackSetup(archer, 20, morale=2)],
            [B.StackSetup(wolf, 15, morale=-1, luck=2), B.StackSetup(gnoll, 25, morale=1)],
            obstacles=[(7, 3), (8, 5), (9, 7), (6, 8)],
            heroes=(B.Hero(attack=2, defense=1, offense=1, archery=2),
                    B.Hero(defense=2, armorer=1)),
        )
        battle_id, state = battle_cli.parse_scenario(golden_scenario())
        self.assertEqual(battle_id, "golden")
        self.assertEqual(B.canonical(state), B.canonical(ref))

    def test_scripted_run_is_deterministic(self):
        path = self.write(golden_scenario(), "golden.json")
        a = self.run_sim(path, 12345, "scripted")
        b = self.run_sim(path, 12345, "scripted")
        self.assertEqual(a.out, b.out)
        c = self.run_sim(path, 54321, "scripted")
        self.assertNotEqual(a.out, c.out)

    def test_event_log_shape(self):
        path = self.write(golden_scenario(), "golden.json")
        lines = self.run_sim(path, 12345, "scripted").out.splitlines()
        self.assertEqual(lines[0], "> Begin()")
        self.assertEqual(lines[1], "  BattleStarted(battle_id='golden')")
        self.assertTrue(lines[-3].startswith("winner: "))
        self.assertTrue(lines[-2].startswith("rounds: "))
        self.assertEqual(lines[-1], f"state hash: {GOLDEN_PINNED}")


class ChooserTest(CliTestCase):
    def test_first_legal_picks_first_entry(self):
        # First-legal waits, then defends forever: nobody attacks, so the
        # battle is cut off at the command cap. The summary is still printed.
        path = self.write(tiny_scenario())
        with mock.patch.object(battle_cli, "MAX_COMMANDS", 30):
            result = self.run_sim(path, 7, "first-legal")
        self.assertFailsCleanly(result)
        self.assertIn("> Wait(stack=0)\n", result.out)
        self.assertIn("winner: none (not finished)\n", result.out)
        self.assertRegex(result.out, r"state hash: [0-9a-f]{64}\n")
        self.assertIn("not finished after 30 commands", result.err)

    def test_first_legal_is_deterministic(self):
        path = self.write(tiny_scenario())
        with mock.patch.object(battle_cli, "MAX_COMMANDS", 30):
            a = self.run_sim(path, 7, "first-legal")
            b = self.run_sim(path, 7, "first-legal")
        self.assertEqual((a.rc, a.out, a.err), (b.rc, b.out, b.err))

    def test_interactive_with_index_zero_equals_first_legal(self):
        path = self.write(tiny_scenario())
        with mock.patch.object(battle_cli, "MAX_COMMANDS", 30):
            auto = self.run_sim(path, 7, "first-legal")
            inter = self.run_sim(path, 7, "interactive", stdin_text="0\n" * 100)
        self.assertEqual(inter.out, auto.out)
        self.assertEqual(inter.rc, auto.rc)

    def test_interactive_reprompts_on_bad_input(self):
        path = self.write(tiny_scenario())
        with mock.patch.object(battle_cli, "MAX_COMMANDS", 5):
            result = self.run_sim(path, 7, "interactive",
                                  stdin_text="banana\n-1\n999\n0\n" + "0\n" * 100)
        self.assertEqual(result.err.count("not a valid choice"), 3)
        self.assertIn("legal commands:", result.err)
        self.assertFailsCleanly(result)  # capped at 5 commands

    def test_interactive_prompts_go_to_stderr_not_log(self):
        path = self.write(tiny_scenario())
        with mock.patch.object(battle_cli, "MAX_COMMANDS", 5):
            result = self.run_sim(path, 7, "interactive", stdin_text="0\n" * 100)
        self.assertNotIn("choose", result.out)
        self.assertIn("choose 0-", result.err)

    def test_interactive_eof_is_one_line_error(self):
        path = self.write(tiny_scenario())
        result = self.run_sim(path, 7, "interactive", stdin_text="0\n")
        self.assertFailsCleanly(result)
        self.assertTrue(result.err.rstrip("\n").endswith(
            "h3re: error: input ended before the battle finished"), result.err)

    def test_interactive_quit(self):
        path = self.write(tiny_scenario())
        result = self.run_sim(path, 7, "interactive", stdin_text="q\n")
        self.assertFailsCleanly(result)
        self.assertTrue(result.err.rstrip("\n").endswith("h3re: error: aborted by user"),
                        result.err)

    def test_scripted_chooser_finishes_tiny_battle(self):
        path = self.write(tiny_scenario())
        result = self.run_sim(path, 7, "scripted")
        self.assertEqual(result.rc, 0, result.err)
        self.assertIn("winner: attacker\n", result.out)


class AiChooserTest(CliTestCase):
    def install_ai(self, value):
        """Put ``value`` at sys.modules['h3re.battle_ai'] for this test only.

        ``None`` makes the import fail with ImportError.
        """
        missing = object()
        saved = sys.modules.get("h3re.battle_ai", missing)

        def restore():
            if saved is missing:
                sys.modules.pop("h3re.battle_ai", None)
            else:
                sys.modules["h3re.battle_ai"] = saved
        self.addCleanup(restore)
        sys.modules["h3re.battle_ai"] = value

    @staticmethod
    def fake_ai(choose):
        module = types.ModuleType("h3re.battle_ai")
        module.choose = choose
        return module

    def test_ai_path_with_injected_module(self):
        calls = []

        def choose(state, side=None):
            calls.append(side)
            return battle_cli.scripted_choice(state)

        path = self.write(tiny_scenario())
        self.install_ai(self.fake_ai(choose))
        result = self.run_sim(path, 7, "ai")
        self.assertEqual(result.rc, 0, result.err)
        self.assertEqual(result.out, self.run_sim(path, 7, "scripted").out)
        self.assertTrue(calls)
        self.assertTrue(all(side is None for side in calls))

    def test_ai_missing_module_is_clear_error(self):
        path = self.write(tiny_scenario())
        self.install_ai(None)  # import raises ImportError
        result = self.run_sim(path, 7, "ai")
        self.assertFailsCleanly(result)
        self.assertIn("h3re.battle_ai", result.err)
        self.assertIn("cannot be imported", result.err)

    def test_ai_returning_illegal_command_is_error(self):
        path = self.write(tiny_scenario())
        self.install_ai(self.fake_ai(lambda state, side=None: B.Move(99, (1, 1))))
        result = self.run_sim(path, 7, "ai")
        self.assertFailsCleanly(result)
        self.assertIn("illegal command", result.err)

    def test_ai_returning_non_command_is_error(self):
        path = self.write(tiny_scenario())
        self.install_ai(self.fake_ai(lambda state, side=None: "wait"))
        result = self.run_sim(path, 7, "ai")
        self.assertFailsCleanly(result)
        self.assertIn("not a battle command", result.err)

    def test_ai_module_without_choose_is_error(self):
        path = self.write(tiny_scenario())
        self.install_ai(types.ModuleType("h3re.battle_ai"))
        result = self.run_sim(path, 7, "ai")
        self.assertFailsCleanly(result)
        self.assertIn("choose(state, side=None)", result.err)

    @unittest.skipUnless(importlib.util.find_spec("h3re.battle_ai") is not None,
                         "h3re/battle_ai.py is not present yet")
    def test_real_ai_module_runs(self):
        path = self.write(tiny_scenario())
        result = self.run_sim(path, 7, "ai")
        self.assertRegex(result.out, r"state hash: [0-9a-f]{64}\n")


class MalformedScenarioTest(CliTestCase):
    def base(self):
        return json.loads(json.dumps(tiny_scenario()))

    def assertParseError(self, result, expected):
        self.assertFailsCleanly(result)
        self.assertEqual(result.out, "")
        self.assertEqual(result.err.count("\n"), 1, result.err)
        self.assertIn(expected, result.err)

    def test_missing_file(self):
        self.assertParseError(self.run_sim(self.dir / "nope.json", 1), "cannot read scenario")

    def test_invalid_json(self):
        self.assertParseError(self.run_sim(self.write("{not json"), 1), "not valid JSON")

    def test_not_utf8(self):
        path = self.dir / "bad.json"
        path.write_bytes(b'{"battle_id": "\xff"}')
        self.assertParseError(self.run_sim(path, 1), "UTF-8")

    def test_top_level_not_object(self):
        self.assertParseError(self.run_sim(self.write([1, 2]), 1), "scenario must be an object")

    def cases(self):
        """(label, mutate(doc) -> doc, expected substring)."""
        def set_(path, value):
            def mutate(doc):
                node = doc
                for key in path[:-1]:
                    node = node[key]
                node[path[-1]] = value
                return doc
            return mutate

        def delete(path):
            def mutate(doc):
                node = doc
                for key in path[:-1]:
                    node = node[key]
                del node[path[-1]]
                return doc
            return mutate

        return [
            ("unknown top key", set_(["extra"], 1), "unknown key 'extra'"),
            ("missing battle_id", delete(["battle_id"]), "missing key 'battle_id'"),
            ("empty battle_id", set_(["battle_id"], ""), "battle_id"),
            ("missing creatures", delete(["creatures"]), "missing key 'creatures'"),
            ("creature not object", set_(["creatures", "imp"], 5), "must be an object"),
            ("creature missing hp", delete(["creatures", "imp", "hp"]), "missing key 'hp'"),
            ("creature string as int", set_(["creatures", "imp", "hp"], "4"),
             "must be an integer"),
            ("float as int", set_(["creatures", "imp", "hp"], 4.0), "must be an integer"),
            ("bool as int", set_(["creatures", "imp", "hp"], True), "must be an integer"),
            ("creature bad flag", set_(["creatures", "imp", "flyer"], "yes"),
             "must be true or false"),
            ("creature unknown key", set_(["creatures", "imp", "wings"], 2),
             "unknown key 'wings'"),
            ("hates not names", set_(["creatures", "imp", "hates"], [1]), "hates"),
            ("unknown creature in stack", set_(["attackers", 0, "creature"], "dragon"),
             "unknown creature 'dragon'"),
            ("stack missing count", delete(["attackers", 0, "count"]),
             "needs 'creature' and 'count'"),
            ("zero count", set_(["attackers", 0, "count"], 0), "invalid stack setup"),
            ("empty side", set_(["defenders"], []), "1 to 7 stacks"),
            ("eight stacks", set_(["defenders"], [{"creature": "imp", "count": 1}] * 8),
             "1 to 7 stacks"),
            ("bad pos", set_(["attackers", 0, "pos"], [1]), "[col, row] pair"),
            ("pos off grid", set_(["attackers", 0, "pos"], [40, 2]), "cannot be placed"),
            ("obstacle off grid", set_(["obstacles"], [[99, 0]]), "off grid"),
            ("obstacles not list", set_(["obstacles"], "x"), "obstacles must be a list"),
            ("heroes wrong length", set_(["heroes"], [None]), "list of two entries"),
            ("hero unknown key", set_(["heroes"], [{"luck": 1}, None]), "unknown key 'luck'"),
            ("policy unknown key", set_(["policy"], {"gravity": 1}), "unknown key 'gravity'"),
            ("policy bad enum", set_(["policy"], {"row_offset": "north"}), "row_offset"),
            ("policy bad type", set_(["policy"], {"range_penalty_beyond": "far"}),
             "must be an integer"),
            ("policy placement wrong shape", set_(["policy"], {"placement_rows": [[1]]}),
             "placement_rows"),
            ("policy negative range", set_(["policy"], {"range_penalty_beyond": -1}),
             "range_penalty_beyond"),
        ]

    def test_malformed_documents_exit_one_with_one_line(self):
        for label, mutate, expected in self.cases():
            with self.subTest(case=label):
                doc = mutate(self.base())
                self.assertParseError(self.run_sim(self.write(doc), 1), expected)


class PolicyAndHeroTest(CliTestCase):
    def test_policy_override_changes_state(self):
        doc = self.base_doc()
        doc["policy"] = {"row_offset": "odd"}
        _, odd = battle_cli.parse_scenario(doc)
        _, even = battle_cli.parse_scenario(self.base_doc())
        self.assertEqual(odd.policy.row_offset, "odd")
        self.assertEqual(even.policy.row_offset, "even")
        self.assertNotEqual(B.state_hash(even), B.state_hash(odd))

    def test_policy_new_fields_from_json(self):
        doc = self.base_doc()
        doc["policy"] = {"bad_morale_table": [2, 4, 6], "speed_tie": "alternate_last_mover",
                         "wait_order": "slow_first_alternate", "range_origin": "any_cell",
                         "bad_morale_on_wait_activation": True,
                         "good_morale_on_wait_activation": False}
        _, state = battle_cli.parse_scenario(doc)
        self.assertEqual(state.policy.bad_morale_table, (2, 4, 6))
        self.assertEqual(state.policy.speed_tie, "alternate_last_mover")
        doc["policy"] = {"bad_morale_table": [1, 2]}
        with self.assertRaises(battle_cli.CliError):
            battle_cli.parse_scenario(doc)
        doc["policy"] = {"morale_roll_on_wait_activation": True}  # deprecated, removed
        with self.assertRaises(battle_cli.CliError):
            battle_cli.parse_scenario(doc)

    def test_policy_empty_is_default(self):
        doc = self.base_doc()
        doc["policy"] = {}
        _, state = battle_cli.parse_scenario(doc)
        self.assertEqual(state.policy, B.DEFAULT_POLICY)

    def test_hero_null_differs_from_empty_hero(self):
        a = self.base_doc()
        b = self.base_doc()
        b["heroes"] = [{}, None]
        _, sa = battle_cli.parse_scenario(a)
        _, sb = battle_cli.parse_scenario(b)
        self.assertNotEqual(B.state_hash(sa), B.state_hash(sb))

    @staticmethod
    def base_doc():
        return json.loads(json.dumps(tiny_scenario()))


class MainIntegrationTest(CliTestCase):
    def run_main(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                rc = main(list(argv))
            except SystemExit as exc:
                rc = exc.code
        return rc, out.getvalue(), err.getvalue()

    def test_battle_sim_subcommand_golden(self):
        path = self.write(golden_scenario(), "golden.json")
        rc, out, err = self.run_main("battle-sim", str(path), "--seed", "12345",
                                     "--chooser", "scripted")
        self.assertEqual(rc, 0, err)
        self.assertIn(f"state hash: {GOLDEN_PINNED}", out)

    def test_battle_sim_default_chooser_is_first_legal(self):
        path = self.write(tiny_scenario())
        with mock.patch.object(battle_cli, "MAX_COMMANDS", 30):
            rc1, out1, _ = self.run_main("battle-sim", str(path), "--seed", "7")
            rc2, out2, _ = self.run_main("battle-sim", str(path), "--seed", "7",
                                         "--chooser", "first-legal")
        self.assertEqual((rc1, out1), (rc2, out2))
        self.assertEqual(rc1, battle_cli.EXIT_FAILURE)

    def test_battle_sim_malformed_is_exit_one_not_traceback(self):
        path = self.write("{")
        rc, out, err = self.run_main("battle-sim", str(path), "--seed", "1")
        self.assertEqual(rc, 1)
        self.assertTrue(err.startswith("h3re: error: "), err)
        self.assertNotIn("Traceback", err)

    def test_battle_sim_usage_errors_exit_two(self):
        path = self.write(tiny_scenario())
        with contextlib.redirect_stderr(io.StringIO()):
            rc, _, _ = self.run_main("battle-sim", str(path), "--seed", "1", "--chooser", "dice")
            self.assertEqual(rc, 2)
            rc, _, _ = self.run_main("battle-sim", str(path))
            self.assertEqual(rc, 2)
            rc, _, _ = self.run_main("battle-sim", str(path), "--seed", "x")
            self.assertEqual(rc, 2)


class _Tty(io.StringIO):
    """A stdout stand-in that reports itself as a terminal."""

    def isatty(self):
        return True


ATTACKER_MARKS = "ABCDEFG"
DEFENDER_MARKS = "HIJKLMN"
ANSI = re.compile(r"\x1b\[[0-9;]*m")


def _board_at(lines, label):
    """Index of the ``-- board, <label>`` line in the pretty output."""
    prefix = f"-- board, {label}, "
    return next(i for i, line in enumerate(lines) if line.startswith(prefix))


def _grid_rows(lines, label):
    """The 11 board rows that follow the two column-digit lines."""
    start = _board_at(lines, label)
    return lines[start + 3:start + 3 + B.HEIGHT]


def _cell_glyphs(grid):
    """Map each hex to the glyph drawn at its column. Even rows are shifted
    right by half a hex (2 columns), matching the default row_offset."""
    glyphs = {}
    for r, line in enumerate(grid):
        assert line[:4] == f"{r:>2}  ", repr(line)
        shift = 2 if r % 2 == 0 else 0
        for c in range(B.WIDTH):
            x = 4 + shift + 4 * c + 2
            glyphs[(c, r)] = line[x] if x < len(line) else " "
    return glyphs


class PrettyTest(CliTestCase):
    def pretty(self, scenario, seed=12345, chooser="scripted", **kw):
        out, err = kw.pop("stdout", None) or io.StringIO(), io.StringIO()
        rc = battle_cli.run(str(scenario), seed, chooser, stdin=io.StringIO(""),
                            stdout=out, stderr=err, pretty=kw.pop("pretty", True), **kw)
        return _Run(rc, out.getvalue(), err.getvalue())

    def golden_path(self):
        return self.write(golden_scenario(), "golden.json")

    def test_board_dimensions_and_positions(self):
        result = self.pretty(self.golden_path())
        self.assertEqual(result.rc, 0, result.err)
        lines = result.out.splitlines()
        grid = _grid_rows(lines, "start")
        self.assertEqual(len(grid), B.HEIGHT)
        self.assertTrue(all(len(line) <= 4 + 4 * B.WIDTH + 2 for line in grid))
        glyphs = _cell_glyphs(grid)
        self.assertEqual(len(glyphs), B.WIDTH * B.HEIGHT)

        _, state = battle_cli.parse_scenario(golden_scenario())
        expected = {(c, r): "." for c in range(B.WIDTH) for r in range(B.HEIGHT)}
        for ob in state.obstacles:
            expected[ob] = "#"
        for s in state.stacks:
            mark = (ATTACKER_MARKS if s.side == B.ATTACKER else DEFENDER_MARKS)[s.slot]
            for h in B.cells(s):
                expected[h] = mark
        self.assertEqual(glyphs, expected)

    def test_board_is_ascii_and_has_no_colour_codes_by_default(self):
        result = self.pretty(self.golden_path(), board_every=2)
        result.out.encode("ascii")
        self.assertNotIn("\x1b", result.out)

    def test_legend_lists_each_stack_with_side_count_and_hp(self):
        result = self.pretty(self.golden_path())
        lines = result.out.splitlines()
        start = _board_at(lines, "start")
        legend_at = next(i for i in range(start, len(lines)) if lines[i].startswith("legend:"))
        table = []
        for line in lines[legend_at + 1:]:
            if not line.strip():
                break
            table.append(line.split())
        self.assertEqual(table[0], ["mark", "side", "creature", "count", "HP", "pos", "state"])
        # HP is the total: (count - 1) * hp + the wounded top unit.
        self.assertEqual([row[:5] for row in table[1:]], [
            ["A", "attacker", "pikeman", "30", "300"],
            ["B", "attacker", "archer", "20", "200"],
            ["H", "defender", "wolf", "15", "225"],
            ["I", "defender", "gnoll", "25", "325"],
        ])
        self.assertTrue(all(row[-1] == "alive" for row in table[1:]))

    def test_round_headers_match_rounds(self):
        result = self.pretty(self.golden_path())
        headers = re.findall(r"^== round (\d+) =+$", result.out, re.M)
        rounds = int(re.search(r"^rounds: (\d+)$", result.out, re.M).group(1))
        self.assertEqual(headers, [str(n) for n in range(1, rounds + 1)])

    def test_event_columns_are_aligned(self):
        result = self.pretty(self.golden_path())
        event_lines = [line for line in result.out.splitlines()
                       if re.match(r"^      [A-Za-z]", line)]
        self.assertTrue(event_lines)
        for line in event_lines:
            self.assertEqual(line[22], " ", line)
            self.assertNotEqual(line[23:24], " ", line)

    def test_pretty_run_is_deterministic(self):
        path = self.golden_path()
        a = self.pretty(path, 12345, board_every=3)
        b = self.pretty(path, 12345, board_every=3)
        self.assertEqual(a.out, b.out)
        c = self.pretty(path, 54321, board_every=3)
        self.assertNotEqual(a.out, c.out)

    def test_hash_line_identical_with_and_without_pretty(self):
        path = self.golden_path()
        plain = self.run_sim(path, 12345, "scripted")
        pretty = self.pretty(path)
        self.assertEqual(plain.rc, pretty.rc)
        tail = plain.out.splitlines()[-3:]
        self.assertEqual(pretty.out.splitlines()[-3:], tail)
        self.assertEqual(tail[-1], f"state hash: {GOLDEN_PINNED}")

    def test_pretty_false_is_the_plain_output(self):
        path = self.golden_path()
        plain = self.run_sim(path, 12345, "scripted")
        explicit = self.pretty(path, pretty=False)
        self.assertEqual(plain.out, explicit.out)

    def test_board_every_adds_boards_at_multiples_of_n(self):
        result = self.pretty(self.golden_path(), board_every=3)
        steps = len(re.findall(r"^ {0,4}\d+  \S", result.out, re.M))
        after = re.findall(r"^-- board, after step (\d+), ", result.out, re.M)
        self.assertEqual(after, [str(n) for n in range(3, steps + 1, 3)])
        self.assertEqual(result.out.count("-- board, "), 2 + steps // 3)

    def test_no_board_every_means_only_start_and_end_boards(self):
        result = self.pretty(self.golden_path())
        self.assertEqual(result.out.count("-- board, "), 2)
        self.assertIn("-- board, start, round 0 --", result.out)
        self.assertIn("-- board, end, round 4 --", result.out)

    def test_board_every_needs_pretty(self):
        out, err = io.StringIO(), io.StringIO()
        rc = battle_cli.run(str(self.golden_path()), 12345, "scripted", stdin=io.StringIO(""),
                            stdout=out, stderr=err, board_every=2)
        self.assertEqual(rc, battle_cli.EXIT_FAILURE)
        self.assertEqual(out.getvalue(), "")
        self.assertIn("--board-every needs --pretty", err.getvalue())

    def test_board_every_rejects_negative(self):
        result = self.pretty(self.golden_path(), board_every=-1)
        self.assertEqual(result.rc, battle_cli.EXIT_FAILURE)
        self.assertIn("board_every must be an integer of 0 or more", result.err)

    def test_colour_only_with_tty(self):
        path = self.golden_path()
        plain = self.pretty(path)
        no_tty = self.pretty(path, color=True)
        self.assertNotIn("\x1b", no_tty.out)
        tty = self.pretty(path, color=True, stdout=_Tty())
        self.assertIn("\x1b[", tty.out)
        self.assertEqual(ANSI.sub("", tty.out), plain.out)
        self.assertEqual(ANSI.sub("", tty.out).splitlines()[-1], f"state hash: {GOLDEN_PINNED}")

    def test_summary_lists_survivors(self):
        path = self.write(tiny_scenario(), "tiny.json")
        result = self.pretty(path)
        self.assertEqual(result.rc, 0, result.err)
        lines = result.out.splitlines()
        end = _board_at(lines, "end")
        alive_in_legend = [line for line in lines[end:] if line.endswith(" alive")]
        summary = lines[lines.index("== summary ==") + 1:]
        rows = []
        for line in summary:
            if not line.strip():
                break
            rows.append(line)
        if not alive_in_legend:
            self.assertEqual(rows, ["  no surviving stacks"])
        else:
            self.assertEqual(len(rows), 1 + len(alive_in_legend))  # header + survivors

    def test_unfinished_battle_still_prints_summary(self):
        path = self.write(tiny_scenario(), "tiny.json")
        with mock.patch.object(battle_cli, "MAX_COMMANDS", 30):
            result = self.pretty(path, chooser="first-legal")
        self.assertEqual(result.rc, battle_cli.EXIT_FAILURE)
        self.assertIn("== summary ==", result.out)
        self.assertIn("winner: none (not finished)\n", result.out)
        self.assertEqual(result.err.count("h3re: error:"), 1, result.err)

    def test_unicode_battle_id_is_escaped_to_ascii(self):
        scenario = tiny_scenario()
        scenario["battle_id"] = "b\u00e4ttle"
        path = self.write(scenario, "uni.json")
        result = self.pretty(path, board_every=5)
        result.out.encode("ascii")
        self.assertIn("== battle b\\xe4ttle |", result.out)


if __name__ == "__main__":
    unittest.main()
