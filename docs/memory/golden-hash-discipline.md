---
name: golden-hash-discipline
type: pointer
updated: 2026-11-01
evidence: ADR-0001, ADR-0005, ADR-0006; checkpoints 28, 29, 36
---
A golden hash moves only through a recorded re-pin: one reviewed change, the reason in the owning spec, all pins updated together. A hash that moves without that is a bug to find.
Why: the hashes are the contract between Python and Kotlin (ADR-0007); drift would silently break every replay and save.
How to apply: when adding a state field, prefer omit-at-default so existing hashes stay put; prove a refactor is play-neutral by showing the old hash comes back when the new field is removed.
