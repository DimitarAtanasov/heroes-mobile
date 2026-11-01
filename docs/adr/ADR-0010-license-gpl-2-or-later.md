# ADR-0010: The project is licensed GPL-2.0-or-later

Status: accepted (2026-11-01, decided by the project owner). Amends ADR-0003.

## Context
ADR-0003 kept VCMI (GPL-2.0-or-later) as a source of facts only, so that the project could
choose any license. The owner has now accepted a GPL license. That removes the licensing reason
for the facts-only rule and opens the option of reusing VCMI code, including its rendering and
Android build, where that is practical.

## Decision
- All code and docs of this repository are released under **GPL-2.0-or-later**
  (`LICENSE` is the GPL v2 text; each new source file may carry
  `SPDX-License-Identifier: GPL-2.0-or-later`). "Or later" matches VCMI's own headers, keeps
  compatibility with GPL-3 and so with Apache-2.0 dependencies such as AndroidX and Compose, and
  lets the project move to GPL-3 later.
- Reusing VCMI code is now **permitted** under that license, with these conditions:
  1. Provenance: any file or function derived from VCMI says so in a header comment, naming the
     VCMI path and the commit (`git -C <clone> rev-parse HEAD`) it came from.
  2. Kotlin and Python remain the languages of this repository. VCMI's C++ is ported, not
     vendored; no VCMI source tree is copied wholesale into the repo.
  3. Anything ported keeps the project's laws: determinism, integer-only simulation, data in
     `data/*.json`, tests, and the Python oracle plus conformance vectors (ADR-0004, ADR-0007).
     VCMI behaviour that differs from the original game stays a policy option (rules.md section 9).
- Unchanged: **no original game data** (maps, archives, sprites, sounds, text tables, binaries)
  ever enters the repo, and the app reads the player's own legally owned install at runtime.
  The GPL covers code, not the game's art or data.
- Existing code stays valid: it was written without copying VCMI and is simply licensed GPL now.

## Consequences
- Distribution of the app (APK or any build) must offer the complete corresponding source under
  the GPL, including the Kotlin engine and app. Store terms (for example Google Play) have
  conflicted with the GPL in some cases; check them before publishing.
- Contributors agree to license their work GPL-2.0-or-later.
- Third-party dependencies must be GPL-compatible. Apache-2.0 libraries are compatible with
  GPL-3 but not GPL-2-only, which is why "or later" is required.
- VCMI's client/rendering design can be studied and ported (sprite compositing, animation timing,
  UI layout logic) instead of reinvented. It is C++/SDL, so it informs the Kotlin renderer rather
  than dropping into it.
- The cross-check reports keep their no-code-blocks format, because they are specs, not
  derived code. New derived code is the exception path described above.
