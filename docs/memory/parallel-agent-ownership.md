---
name: parallel-agent-ownership
type: lesson
updated: 2026-11-01
evidence: checkpoints 50 and 51 (vector wiring done by the lead); docs/loops/agent-round.md
---
Run agents in parallel only on disjoint files, each building in a private copy, and let the lead be the single writer of shared files.
Why: one half-written Kotlin file breaks every Gradle build in a shared tree, and two agents appending to `vectors.py`, `conformance.md` or the handoff file collide.
How to apply: give each agent its own vector module (`vectors_<topic>.py` exposing `generate()`), its own spec note (`conformance-<topic>.md`), and a deadline. The lead adds the module to `EXTRA_VECTOR_MODULES` in `vectors.py` and commits each owner's files as a separate commit.
