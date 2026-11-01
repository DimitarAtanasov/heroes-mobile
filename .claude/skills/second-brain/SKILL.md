---
name: second-brain
description: Keep a durable, version-controlled memory for this project in docs/memory - capture lessons, environment facts and owner preferences as small linked notes, recall them before work, and prune them. Use at the start of a session, after a surprise or mistake, and before a handoff.
---

# Second brain (project memory)

Memory lives in git as plain markdown, so it survives sessions, can be reviewed and reverted, and is
readable by every agent. Entry point: `docs/memory/MEMORY.md` (an index, one line per note).

## Principles
- **Store only what code and git history cannot tell you**: why something was decided or went wrong,
  environment facts, owner preferences, and pointers. Do not copy code, ADRs or the commit log.
- **Simplicity first.** A note is short, has one idea, and earns its place. The index stays under
  150 lines; when it grows, merge or delete.
- **Goal-driven.** A note exists to change a future action. If you cannot say what it changes, do not
  write it.
- **Surgical.** Update the existing note instead of adding a near-duplicate.
- **Memory is a hint, not truth.** A note may be stale. Before acting on one that names a file,
  command, flag or number, check it against the repo or by running it, and fix the note if it is wrong.

## Note format
File `docs/memory/<topic>.md`, kebab-case name:
```
---
name: <topic>
type: lesson | fact | preference | pointer
updated: YYYY-MM-DD
evidence: <commit, ADR, command or file that supports it>
---
<the rule or fact in one or two sentences>
Why: <the incident or reason>
How to apply: <when it matters and what to do>
```
Index line in `MEMORY.md`: `- [topic](topic.md) - one-line hook`.

## Operations
1. **Recall (session start, and before a risky step)**: read `MEMORY.md`, open the notes whose hook
   matches the task, then read `docs/checkpoints/HANDOFF.md`. State in one line which notes you are
   applying.
2. **Capture (after a surprise, a correction by the owner, or a failure)**: write or update the note
   in the same change that fixes the problem. Include the evidence. Capture owner decisions as a
   pointer to the ADR (`docs/adr/`) rather than a copy.
3. **Consolidate (before a handoff or every few rounds)**: merge duplicates, delete notes the code now
   makes obsolete, re-check dated facts, keep the index current. Record what you removed in the commit.
4. **Lint**: `python3 tools/skills/validate.py` checks skills and loops; keep `MEMORY.md` links valid
   (the test in `tools/h3re/tests/test_loops.py` fails on a dead link or a missing frontmatter field).

## What never goes in
Secrets or tokens, personal data beyond what the owner put in the repo, original game files or
excerpts of them, large logs, anything already in an ADR or the code.

## Relationship to other records
- ADRs record decisions; memory records lessons and facts that shaped them.
- `HANDOFF.md` is the resume point of the current work; memory is what persists across all work.
- Loop contracts in `docs/loops/` say how work proceeds; memory says what we learned doing it.
