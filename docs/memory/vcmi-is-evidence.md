---
name: vcmi-is-evidence
type: pointer
updated: 2026-11-01
evidence: ADR-0003, ADR-0010, docs/specs/vcmi-crosscheck-rules.md, docs/specs/vcmi-crosscheck-formats.md
---
VCMI tells us what the original probably does; it is not proof, and it sometimes differs on purpose. Clear findings may become defaults; ambiguous ones become switchable policies plus an experiment in `rules.md` section 9.
Why: the project can use VCMI facts and, under the GPL, ported code with a provenance header (path and commit); the original game's data is never copied.
How to apply: cite the VCMI path and commit; keep rule choices as policy options so experiment results change data, not code.
