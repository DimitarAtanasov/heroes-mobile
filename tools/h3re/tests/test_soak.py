import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from h3re import adventure as A  # noqa: E402
from h3re import battle as B  # noqa: E402
from h3re import soak  # noqa: E402


class SoakTest(unittest.TestCase):
    def test_battles_and_adventures_pass(self):
        self.assertEqual(soak.soak(3, max_steps=120), [])

    def test_logs_are_reproducible(self):
        for kind in soak.KINDS:
            a = soak.generate_log(kind, 3)
            b = soak.generate_log(kind, 3)
            self.assertEqual(a[1], b[1])
            self.assertGreater(len(a[0]), 1)

    def test_command_roundtrip(self):
        for kind in soak.KINDS:
            cmds, tr = soak.generate_log(kind, 2, 60)
            back = [soak.decode_command(kind, soak.encode_command(c)) for c in cmds]
            self.assertEqual(back, cmds)
            self.assertEqual(soak.trace(kind, 2, back), tr)

    def test_different_seeds_differ(self):
        self.assertNotEqual(soak.generate_log("battle", 1)[1],
                            soak.generate_log("battle", 2)[1])

    def test_detects_injected_nondeterminism(self):
        # A hidden counter makes the second live run differ from the first.
        orig = A.apply
        calls = {"n": 0}

        def flaky(state, cmd, rng=None):
            s, e = orig(state, cmd, rng)
            calls["n"] += 1
            if calls["n"] > 30 and isinstance(cmd, A.EndTurn):
                e = e + ("noise%d" % calls["n"],)
            return s, e

        A.apply = flaky
        try:
            with self.assertRaises(soak.Divergence):
                soak.check_seed("adventure", 0, 100)
        finally:
            A.apply = orig

    def test_trace_digest_is_stable_and_discriminating(self):
        tr = soak.generate_log("battle", 3, 60)[1]
        self.assertEqual(soak.trace_digest(tr), soak.trace_digest(list(tr)))
        self.assertRegex(soak.trace_digest(tr), r"^[0-9a-f]{64}$")
        self.assertNotEqual(soak.trace_digest(tr), soak.trace_digest(tr[:-1]))
        other = soak.generate_log("battle", 4, 60)[1]
        self.assertNotEqual(soak.trace_digest(tr), soak.trace_digest(other))
        self.assertNotEqual(soak.trace_digest([("ab", "c")]), soak.trace_digest([("a", "bc")]))

    def test_run_seed_digest_matches_trace(self):
        for kind in soak.KINDS:
            n, dg = soak.run_seed(kind, 2, 60)
            cmds, tr = soak.generate_log(kind, 2, 60)
            self.assertEqual(n, len(cmds))
            self.assertEqual(dg, soak.trace_digest(tr))

    def test_policy_matrix_is_non_default_and_valid(self):
        combos = soak.policy_matrix()
        self.assertGreaterEqual(len(combos), 3)
        for name, bp, ap in combos:
            if name == "default":
                self.assertEqual(bp, B.DEFAULT_POLICY)
                self.assertEqual(ap, A.DEFAULT_POLICY)
            else:
                self.assertNotEqual(bp, B.DEFAULT_POLICY, name)
                self.assertNotEqual(ap, A.DEFAULT_POLICY, name)

    def test_policy_reaches_the_scenario(self):
        for name, bp, ap in soak.policy_matrix():
            self.assertEqual(soak.build_scenario("battle", 1, bp)[0].policy, bp)
            self.assertEqual(soak.build_scenario("adventure", 1, ap)[0].policy, ap)

    def test_policy_matrix_changes_traces(self):
        combos = soak.policy_matrix()
        for kind, idx in (("battle", 1), ("adventure", 2)):
            digests = set()
            for combo in combos:
                digests.add(soak.run_seed(kind, 5, 120, combo[idx])[1])
            self.assertGreater(len(digests), 1, kind)

    def test_policy_matrix_soak_passes_with_digests(self):
        digests = []
        self.assertEqual(soak.soak(2, max_steps=80, matrix=True, digests=digests), [])
        self.assertEqual(len(digests), 2 * 2 * len(soak.POLICY_MATRIX))
        again = []
        soak.soak(2, max_steps=80, matrix=True, digests=again)
        self.assertEqual(soak.soak_digest(digests), soak.soak_digest(again))

    def test_digest_cli_flags(self):
        with tempfile.TemporaryDirectory() as d:
            f = os.path.join(d, "dg.txt")
            argv = ["--games", "1", "--max-steps", "40", "--policy-matrix", "-q"]
            self.assertEqual(soak.main(argv + ["--digest-out", f]), 0)
            self.assertEqual(soak.main(argv + ["--expect-digest-file", f]), 0)
            with open(f, "w") as fh:
                fh.write("0" * 64 + "\n")
            self.assertEqual(soak.main(argv + ["--expect-digest-file", f]), 1)

    def test_digest_independent_of_pythonhashseed(self):
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        outs = []
        for hs in ("0", "4242"):
            env = dict(os.environ, PYTHONHASHSEED=hs)
            r = subprocess.run(
                [sys.executable, "-m", "h3re.soak", "--games", "2", "--max-steps", "60",
                 "--policy-matrix", "-q"], cwd=root, env=env, capture_output=True,
                text=True, timeout=300)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            line = [x for x in r.stdout.splitlines() if x.startswith("DIGEST ")]
            self.assertEqual(len(line), 1)
            outs.append(line[0])
        self.assertEqual(outs[0], outs[1])

    def test_cli(self):
        self.assertEqual(soak.main(["--games", "2", "-q"]), 0)


if __name__ == "__main__":
    unittest.main()
