# ADR-0004: Android app with a Kotlin engine; Python is the reference oracle

Status: accepted (2026-11-01). Resolves the open question in `engine-design.md` section 4.

## Context
The product target is an Android app that loads the user's own legally owned game data at
runtime. The simulation exists today as Python (`tools/h3re`), integer/`Fraction` only, with
canonical-JSON SHA-256 state hashes (ADR-0001), PCG32 streams (`rng.py`) and pinned golden
hashes. Options considered: (a) Python on device via Chaquopy, (b) port to Kotlin with the
Python code kept as a reference, (c) port to Rust and call it through JNI.

## Decision
Build the app in Kotlin (native Android). Port the simulation to Kotlin as a separate
module, and keep the Python implementation as the executable specification and conformance
oracle. A Kotlin build is correct only when it reproduces the Python golden hashes.

## Why
- The sim is deterministic, integer-only and hash-pinned (ADR-0001, ADR-0002), so a port is
  mechanically checkable, step by step, rather than judged by eye.
- No embedded interpreter: smaller APK, faster start, control over timing and memory.
- Rust would add a second toolchain and more work with no MVP benefit; revisit if iOS or
  desktop becomes a goal.
- Chaquopy is the fastest prototype but loses on APK size, sim speed and startup; it stays an
  option only for throw-away demos.

## Consequences
- **Conformance vectors.** The replay format (`replay.py`, `docs/specs/replay.md`) is the
  cross-language test suite. Every golden scenario is exported as a replay file plus per-step
  state hashes. Kotlin tests replay them and compare hashes and events.
- **Byte-exact canonical form.** Kotlin must produce the same canonical JSON bytes (sorted
  keys, compact separators, ints and strings only, tuples as lists) and SHA-256. The
  canonical form is specified in ADR-0001 and is now an interface, not an implementation
  detail.
- **RNG.** PCG32 and the stream derivation (`derive_stream`, SHA-256 of seed, domain, id with
  length-prefixed fields) are ported with unsigned 64-bit arithmetic (`ULong`) and tested
  against the published vectors in `rng.md`.
- **Exact rationals.** Python's `Fraction` has no Kotlin equivalent. Amended 2026-11-01:
  the Kotlin engine adds a small `Rational` type with one named rounding step (ADR-0009). The
  integer-rewrite preference in the earlier text is withdrawn.
- **Data stays outside the APK.** No game assets in the app or repo. The user imports their
  own install through the Storage Access Framework; LOD/DEF/PCX/TXT/H3M readers are ported
  after the sim and are conformance-tested with synthetic files plus the gated real-file tests.
- **Python stays authoritative.** A rule change lands in Python first (spec, tests, golden
  re-pin per ADR-0001), then in Kotlin; the conformance vectors are regenerated in the same
  change.
- **Project layout.** `android/` (Gradle, Kotlin, Compose UI) with a `sim` module that has no
  Android dependencies (so it runs as plain JVM tests), `data` (readers) and `app`.

## Amendments (2026-11-01)
- Conformance vectors and the replay format are the cross-language contract: ADR-0007.
- Pack integers are Kotlin `Int`, capped at 2**31-1 on both sides; hashes and XP accumulation use `Long`: ADR-0008.
- Exact rationals use a `Rational` type with one named rounding step: ADR-0009.
- The state-form rules (omit at default, stored content in place of a pack hash) are ADR-0005 and ADR-0006.

## Risks
- Two implementations can drift; mitigated by CI that regenerates vectors from Python and
  runs the Kotlin sim tests against them.
- Performance: soak and AI loops are heavier in Kotlin tests; keep vector sizes bounded.
- Anything the rules specs mark [uncertain] is a policy in both implementations, never a
  hard-coded choice, so experiment results change data, not code.
