---
name: owner-preferences
type: preference
updated: 2026-11-02
evidence: conversation; ADR-0004 (Kotlin), ADR-0010 (GPL-2.0-or-later)
---
The owner wants Android with a Kotlin engine (Python is the oracle) and a GPL-2.0-or-later project. Commit each piece only when verified, push to the PR branch, and never merge or touch `main` without being asked.
Why: owner decisions, recorded in ADR-0004 and ADR-0010.
How to apply: ask for the plan-usage figure before launching rounds; wrap up at 95%, write the handoff and push at 98%. Be honest about what is unverified (nothing has run on real game files). Refer to agents by role names in docs, not model names. Ask the owner about license, store, edition support and real game data instead of deciding.
2026-11-02 decisions: push only branches that are mergeable as they are (no throwaway CI branches); the UI should follow Heroes 3 as the reference and use sprites from the player's own game files at runtime, with a drawn fallback, never original assets in the repo; saves are autosave plus manual saves plus choosing an exact save, no import or export; app name unchanged for now; the owner asks for a PR explicitly (then subscribe to it).
2026-11-02 (later): game data comes into the app by sideload only for now (adb, debug builds); no folder picker or drop folder without a new explicit yes. Order of work stated by the owner: real game data first, then the import flow, then the device test. Real game files are never in the container; the owner runs checks locally and sends back sanitized reports.
