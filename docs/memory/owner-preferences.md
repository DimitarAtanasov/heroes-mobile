---
name: owner-preferences
type: preference
updated: 2026-11-01
evidence: conversation; ADR-0004 (Kotlin), ADR-0010 (GPL-2.0-or-later)
---
The owner wants Android with a Kotlin engine (Python is the oracle) and a GPL-2.0-or-later project. Commit each piece only when verified, push to the PR branch, and never merge or touch `main` without being asked.
Why: owner decisions, recorded in ADR-0004 and ADR-0010.
How to apply: ask for the plan-usage figure before launching rounds; wrap up at 95%, write the handoff and push at 98%. Be honest about what is unverified (nothing has run on real game files). Refer to agents by role names in docs, not model names. Ask the owner about license, store, edition support and real game data instead of deciding.
