"""Tests for tools/skills/loop_eval.py (the deterministic loop evaluator). One failing fixture per rule."""
import copy
import json
import os
import subprocess
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools", "skills"))
import loop_eval as E  # noqa: E402

with open(os.path.join(ROOT, "docs", "loops", "agent-round.md"), encoding="utf-8") as f:
    LOOP = f.read()
TRACE = E._load_run(os.path.join(ROOT, "docs", "loops", "runs", "agent-round.example.jsonl"))


def rules(errs):
    return sorted({e.split()[0] for e in errs})


class GraphCriteria(unittest.TestCase):
    def test_repo_loop_passes(self):
        self.assertEqual(E.eval_graph(LOOP, "loop"), [])

    def test_s1_unlabeled_branch(self):
        bad = LOOP.replace("dispatch -->|agents reported| verify", "dispatch --> verify")
        self.assertIn("S1", rules(E.eval_graph(bad)))

    def test_s2_zero_budget_and_unlabeled_retry(self):
        self.assertIn("S2", rules(E.eval_graph(LOOP.replace("rework_per_piece: 2", "rework_per_piece: 0"))))
        self.assertIn("S2", rules(E.eval_graph(LOOP.replace("rework -->|budget left| dispatch", "rework --> dispatch"))))

    def test_s3_done_without_a_verify_gate(self):
        bad = LOOP.replace("dispatch -->|agents reported| verify[Verify in clean copy plus mutation]",
                           "dispatch -->|agents reported| commit")
        self.assertIn("S3", rules(E.eval_graph(bad)))

    def test_s4_needs_a_non_success_exit(self):
        bad = (LOOP.replace("    dispatch -->|needs owner decision| escalated\n", "")
               .replace("    verify -->|unsafe or data loss| failed\n", "")
               .replace("    rework -->|budget spent| escalated\n", ""))
        self.assertIn("S4", rules(E.eval_graph(bad)))

    def test_g0_structural_problem_is_reported(self):
        self.assertIn("G0", rules(E.eval_graph(LOOP.replace("## Verification", "## Checking"))))


class RunCriteria(unittest.TestCase):
    def errs(self, recs):
        return E.eval_run(LOOP, recs, "t")

    def mut(self, fn):
        r = copy.deepcopy(TRACE)
        fn(r)
        return r

    def test_example_trace_passes(self):
        self.assertEqual(self.errs(TRACE), [])

    def test_r1_chain_integrity(self):
        self.assertIn("R1", rules(self.errs(self.mut(lambda r: r[2].update(step=7)))))
        self.assertIn("R1", rules(self.errs(self.mut(lambda r: r[3].update(node="commit")))))
        self.assertIn("R1", rules(self.errs(self.mut(lambda r: r.pop()))))
        self.assertIn("R1", rules(self.errs([])))
        self.assertIn("R1", rules(self.errs(self.mut(lambda r: r[-1].update(node="verify")))))

    def test_r2_edges_and_labels(self):
        self.assertIn("R2", rules(self.errs(self.mut(lambda r: r[1].update(to="commit")))))
        self.assertIn("R2", rules(self.errs(self.mut(lambda r: r[1].update(label="whenever")))))

    def test_r3_budgets(self):
        self.assertIn("R3", rules(self.errs(self.mut(lambda r: r[3].update(spent={"rework_per_piece": 3})))))
        self.assertIn("R3", rules(self.errs(self.mut(lambda r: r[4].update(spent={"rework_per_piece": 0})))))
        self.assertIn("R3", rules(self.errs(self.mut(lambda r: r[3].update(spent={"mystery": 1})))))
        self.assertIn("R3", rules(self.errs(self.mut(lambda r: r[3].pop("spent")))))  # retry without spending

    def test_r4_acceptance_needs_independent_command_evidence(self):
        def no_pass(r):
            r[5]["evidence"] = [{"kind": "command", "ref": "gradle :sim:test", "exit_code": 1}]
        self.assertIn("R4", rules(self.errs(self.mut(no_pass))))

        def claim_only(r):
            r[5]["evidence"] = [{"kind": "report", "ref": "the agent says it passed"}]
        self.assertIn("R4", rules(self.errs(self.mut(claim_only))))

        def maker_accepts(r):
            for x in r:
                if x["role"] == "verifier":
                    x["actor"] = "haiku-runner"
        self.assertIn("R4", rules(self.errs(self.mut(maker_accepts))))

    def test_r5_evidence_shape(self):
        self.assertIn("R5", rules(self.errs(self.mut(lambda r: r[0].update(evidence=[{"kind": "vibes", "ref": "x"}])))))
        self.assertIn("R5", rules(self.errs(self.mut(lambda r: r[2].update(evidence=[{"kind": "command", "ref": "x"}])))))
        self.assertIn("R5", rules(self.errs(self.mut(lambda r: r[0].update(evidence="oops")))))

    def test_r6_schema(self):
        self.assertIn("R6", rules(self.errs(self.mut(lambda r: r[0].update(extra=1)))))
        self.assertIn("R6", rules(self.errs(self.mut(lambda r: r[0].update(role="manager")))))
        self.assertIn("R6", rules(self.errs(self.mut(lambda r: r[0].update(actor="")))))

    def test_r7_escalation_needs_a_decision(self):
        esc = [
            {"step": 1, "node": "advise", "to": "dispatch", "label": "", "actor": "a", "role": "advisor", "evidence": []},
            {"step": 2, "node": "dispatch", "to": "escalated", "label": "needs owner decision", "actor": "l",
             "role": "lead", "evidence": []},
            {"step": 3, "node": "escalated", "to": None, "label": "", "actor": "l", "role": "lead", "evidence": []},
        ]
        self.assertIn("R7", rules(self.errs(esc)))
        ok = copy.deepcopy(esc)
        ok[1]["evidence"] = [{"kind": "decision", "ref": "Is a GPL app acceptable?"}]
        self.assertEqual(self.errs(ok), [])

    def test_r8_failure_needs_evidence(self):
        failed = [
            {"step": 1, "node": "advise", "to": "dispatch", "label": "", "actor": "a", "role": "advisor", "evidence": []},
            {"step": 2, "node": "dispatch", "to": "verify", "label": "agents reported", "actor": "r", "role": "runner",
             "evidence": []},
            {"step": 3, "node": "verify", "to": "failed", "label": "unsafe or data loss", "actor": "l", "role": "verifier",
             "evidence": []},
            {"step": 4, "node": "failed", "to": None, "label": "", "actor": "l", "role": "lead", "evidence": []},
        ]
        self.assertIn("R8", rules(self.errs(failed)))
        failed[3]["evidence"] = [{"kind": "report", "ref": "tree corrupted by a bad merge"}]
        self.assertEqual(self.errs(failed), [])

    def test_failing_graph_blocks_any_run(self):
        bad = LOOP.replace("dispatch -->|agents reported| verify", "dispatch --> verify")
        self.assertIn("R0", rules(E.eval_run(bad, TRACE, "t")))

    def test_it_is_deterministic(self):
        self.assertEqual(self.errs(TRACE), self.errs(TRACE))
        bad = self.mut(lambda r: r[1].update(to="commit"))
        self.assertEqual(self.errs(bad), self.errs(bad))


class Cli(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, os.path.join(ROOT, "tools", "skills", "loop_eval.py"), *args],
                              capture_output=True, text=True)

    def test_exit_codes(self):
        loop = os.path.join(ROOT, "docs", "loops", "agent-round.md")
        trace = os.path.join(ROOT, "docs", "loops", "runs", "agent-round.example.jsonl")
        self.assertEqual(self.run_cli("graph", loop).returncode, 0)
        self.assertEqual(self.run_cli("run", loop, trace).returncode, 0)
        self.assertEqual(self.run_cli().returncode, 2)

    def test_bad_json_line_fails_cleanly(self):
        import tempfile
        d = tempfile.mkdtemp()
        p = os.path.join(d, "t.jsonl")
        with open(p, "w") as f:
            f.write("{not json}\n")
        r = self.run_cli("run", os.path.join(ROOT, "docs", "loops", "agent-round.md"), p)
        self.assertEqual(r.returncode, 1)
        self.assertIn("invalid JSON", r.stdout)
        self.assertNotIn("Traceback", r.stderr)


class RepoWiring(unittest.TestCase):
    def test_repo_validator_runs_the_strict_checks(self):
        import validate as V
        self.assertEqual(V.validate_repo(ROOT), [])

    def test_a_run_without_a_loop_doc_is_reported(self):
        import tempfile
        import validate as V
        d = tempfile.mkdtemp()
        os.makedirs(os.path.join(d, "docs", "loops", "runs"))
        with open(os.path.join(d, "docs", "loops", "runs", "ghost.x.jsonl"), "w") as f:
            f.write(json.dumps({"step": 1}) + "\n")
        self.assertTrue(any("no matching loop doc" in e for e in V.validate_repo(d)))


if __name__ == "__main__":
    unittest.main()
