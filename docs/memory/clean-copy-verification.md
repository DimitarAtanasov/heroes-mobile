---
name: clean-copy-verification
type: lesson
updated: 2026-11-01
evidence: DEF verification false failure before checkpoint 54; docs/loops/agent-round.md
---
Verify an agent's work in a copy built from `git archive HEAD` plus only that agent's owned files, never from a tar of the working tree.
Why: a "clean copy" taken from the working `android/` directory also carried another agent's unfinished `Legal.kt` and a regenerated `battle_states.json`, which produced failures that were not the agent's fault.
How to apply: `rm -rf /tmp/verify && mkdir /tmp/verify && git archive HEAD | tar -x -C /tmp/verify`, then copy the owner's files over it; run the full Python suite, the lint, `python3 -m h3re.vectors --check` and `gradle :sim:test` there.
