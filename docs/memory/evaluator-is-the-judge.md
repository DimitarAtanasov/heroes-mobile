---
name: evaluator-is-the-judge
type: lesson
updated: 2026-11-01
evidence: tools/skills/loop_eval.py; its first run flagged an unlabeled branch in docs/loops/agent-round.md (S1)
---
Acceptance of a loop, and of a loop run, comes from `python3 tools/skills/loop_eval.py`, never from an agent's own report; rules are fixed S1-S4 for graphs and R1-R8 for runs.
Why: a deterministic check cannot be talked into passing. On its first run it found a real flaw in our own example loop (a branching node with an unlabeled edge), which a read-through had missed.
How to apply: when a loop fails the evaluator, change the loop or the run, never the evaluator. Use a cheap runner model because the evaluator catches protocol errors; use the strongest model for the advisor and producer.
