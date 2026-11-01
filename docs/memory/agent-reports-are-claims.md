---
name: agent-reports-are-claims
type: lesson
updated: 2026-11-01
evidence: checkpoints 49, 52, 65 (mutation checks; at 65 a lead mutation of the confirm guard survived and exposed a missing stale-preview test); Kotlin audit of 2026-11-01 (edge overflow and parser strictness found after green tests)
---
A subagent's "done, all green" is an observation. Accept only what you reproduced, and break the new code once on purpose to see a test fail.
Why: green vectors only prove the inputs the corpus reaches. The Kotlin audit found overflow and policy-strictness gaps that 731 matching steps never touched. A surviving mutant needs a proof that it is equivalent (for example a zero-probability chance draws nothing) or a new test.
How to apply: mutate one behaviour per new module, expect failures, restore, re-run. Run a determinism audit on each new port before calling it done.
