# ADR-0003: VCMI as a fact source only (clean-room, GPL)

Status: accepted. Amended by ADR-0010: the project is GPL-2.0-or-later, so reusing VCMI code is now permitted with provenance headers. The facts-only practice remains the default for specs and cross-check reports. Amended by ADR-0014: a creature-to-DEF fact table may be ported from VCMI's creature configuration, with per-entry source citations; no VCMI file is committed.

Context: The rules and file formats in `docs/specs/` have `[uncertain]` items that no public
document settles. VCMI, a GPL-2.0-or-later reimplementation, is the best available evidence.
Its licence is copyleft, and this project must stay clean-room. The cross-check reports
(`docs/specs/vcmi-crosscheck-rules.md`, `docs/specs/vcmi-crosscheck-formats.md`) already follow
this rule. Their status notes say VCMI is evidence, not proof.

Decision:
- VCMI may be read for functional facts only: constants, offsets, sizes, field order, the semantics of a flag, the order of operations, and the existence of a behaviour.
- Each fact is written in our own words and carries a citation: repo-relative path plus the function or section name, and a one-line description. Example: `lib/filesystem/CArchiveLoader.cpp` (`initLODArchive`): seek to 0x5C before the directory loop.
- Forbidden in any repo file: VCMI code, comments, identifiers used as-is, code snippets, and line-by-line paraphrase of VCMI code. Forbidden: committing VCMI files or a vendored copy.
- Implementers (`sim-engineer`) work from `docs/specs/` only. The cross-check reports are the only channel from VCMI into our code. An implementer does not open VCMI source.
- VCMI is evidence, not proof. A VCMI result changes a default only when it is "clear" in the cross-check report. Ambiguous items wait for the `rules.md` section 9 experiments on real data.
- VCMI behaviour that VCMI itself documents as a departure from the original game is not copied.

Consequences:
- The cross-check reports contain no code blocks. Any new cross-check entry follows the same format.
- `spec-agent` checks the clean-room boundary in every spec it writes. `adr-scribe` rejects any ADR or note that quotes or paraphrases VCMI code.
- Facts about the original game are not copied from VCMI as data tables. Numeric values come from the user's own legally owned game data, read at runtime, and tuning values go to `data/*.json` under the project's own licence.

Verification:
- Review of each cross-check entry: it has a path citation, no code block, and no comments copied.
- `grep -n '```' docs/specs/vcmi-crosscheck-*.md` returns nothing (currently true).
- Spot check by `determinism-auditor` or `adr-scribe` when a new VCMI fact enters a spec.
