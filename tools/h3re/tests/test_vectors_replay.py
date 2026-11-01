import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from h3re import battle as B  # noqa: E402
from h3re import battle_cli  # noqa: E402
from h3re import replay  # noqa: E402
from h3re import soak  # noqa: E402
from h3re import vectors as V  # noqa: E402
from h3re import vectors_replay as VR  # noqa: E402

PKG_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_DOC = None


def doc():
    global _DOC
    if _DOC is None:
        _DOC = VR.generate()[VR.FILE]
    return _DOC


def _floats(x):
    if isinstance(x, float):
        return True
    if isinstance(x, dict):
        return any(_floats(v) for v in x.values())
    if isinstance(x, list):
        return any(_floats(v) for v in x)
    return False


class VectorsReplayTest(unittest.TestCase):
    def test_shape_and_no_floats(self):
        d = doc()
        self.assertEqual(d["format"], 1)
        self.assertFalse(_floats(d))
        self.assertEqual(set(d), {"format", "packs", "scenarios", "scenario_errors",
                                  "replay_errors", "truncation"})
        self.assertGreaterEqual(len(d["scenarios"]), 10)
        self.assertGreaterEqual(len(d["scenario_errors"]), 60)
        self.assertGreaterEqual(len(d["replay_errors"]), 50)

    def test_deterministic(self):
        self.assertEqual(V._dump(VR.generate()[VR.FILE]), V._dump(doc()))

    def test_error_names_all_covered(self):
        names = {c["error"] for c in doc()["replay_errors"]}
        self.assertEqual(names, {"Malformed", "Truncated", "Tampered", "UnsupportedVersion",
                                 "UnsupportedKind", "MismatchedRulesPack", "MismatchedPolicy",
                                 "MismatchedCreatures", "Diverged"})

    def test_scenarios_replay_and_rebuild(self):
        policies = set()
        for s in doc()["scenarios"]:
            scn = json.loads(s["scenario"])
            policies.add(json.dumps(scn.get("policy", {}), sort_keys=True))
            _, state = battle_cli.parse_scenario(scn)
            self.assertEqual(B.canonical(state).decode("ascii"), s["initial_canonical"])
            self.assertEqual(B.state_hash(state), s["initial_hash"])
            cmds = [soak.decode_command("battle", c) for c in s["commands"]]
            data = replay.record(scn, cmds, s["seed"])
            self.assertEqual(data.decode("ascii"), s["replay"])
            self.assertEqual(replay.verify(data), s["header"])
        self.assertGreaterEqual(len(policies), 5)

    def test_error_cases_reproduce(self):
        for c in doc()["scenario_errors"]:
            with self.assertRaises(battle_cli.CliError, msg=c["name"]) as cm:
                battle_cli.parse_scenario(json.loads(c["scenario"]))
            self.assertEqual(" ".join(str(cm.exception).split()), c["error"], c["name"])
        for c in doc()["replay_errors"]:
            blob = bytes.fromhex(c["replay_hex"]) if "replay_hex" in c else c["replay"].encode("ascii")
            with self.assertRaises(replay.ReplayError, msg=c["name"]) as cm:
                replay.verify(blob)
            self.assertEqual(type(cm.exception).__name__, c["error"], c["name"])

    def test_truncation_vector(self):
        t = doc()["truncation"]
        data = t["replay"].encode("ascii")
        self.assertEqual(len(data), t["length"])
        for cut in range(len(data)):
            with self.assertRaises(replay.Truncated):
                replay.verify(data[:cut])

    def test_cli_verifies_vector_replays(self):
        with tempfile.TemporaryDirectory() as tmp:
            for s in doc()["scenarios"][:3]:
                path = os.path.join(tmp, s["name"] + ".h3r")
                with open(path, "wb") as f:
                    f.write(s["replay"].encode("ascii"))
                r = subprocess.run([sys.executable, "-m", "h3re", "replay", "verify", path],
                                   cwd=PKG_ROOT, capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, r.stderr)

    def test_committed_file_matches(self):
        path = os.path.join(V.DEFAULT_OUT, VR.FILE)
        if not os.path.exists(path):
            self.skipTest("replay.json not generated yet")
        with open(path, "rb") as f:
            self.assertEqual(f.read(), V._dump(doc()))


if __name__ == "__main__":
    unittest.main()
