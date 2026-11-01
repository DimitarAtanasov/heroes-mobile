# ADR-0007: Replay files and exported conformance vectors are the cross-language contract for the Kotlin port

Status: accepted

Context: ADR-0004 names the replay format as the cross-language test suite and makes the Python implementation the oracle. `tools/h3re/h3re/replay.py` and `docs/specs/replay.md` define the file, and `tools/h3re/h3re/vectors.py` exports the vectors to `android/sim/src/test/resources/vectors` (its `DEFAULT_OUT`), which the Kotlin tests load (`android/sim/src/test/kotlin/h3/sim/ConformanceTest.kt`).

Decision:
- The Python replay files and the vectors written by `python3 -m h3re.vectors` are the contract between the two implementations. A Kotlin change is accepted only when it reproduces every state hash, event and final hash in them, byte for byte.
- Vectors are generated only from Python, by `cd tools/h3re && python3 -m h3re.vectors`. They are never edited by hand, and the Kotlin side never generates its own oracle.
- A vector change is a change of the Python rules or of the file format. It goes with the Python change, its spec record and, for a golden value, an ADR-0001 re-pin, in the same reviewed change.
- `python3 -m h3re.vectors --check` fails when the committed files differ from a fresh generation.

Consequences:
- `sim-engineer` (Kotlin): tests run against the committed vectors; a Kotlin-only test may add coverage but never replaces a vector.
- `test-verifier`: runs `--check` and the Kotlin conformance tests and quotes both results.
- `determinism-auditor`: treats an unexpected vector diff as a hash divergence (it runs before merge).

Verification:
- `cd tools/h3re && python3 -m h3re.vectors --check` exits 0 with "vectors up to date".
- The Kotlin `:sim` conformance tests (`ConformanceTest.kt`) pass, run with the Gradle wrapper in `android/` (`./gradlew :sim:test`; the task name is to be confirmed by the Android owner).
- `git diff --stat -- android/sim/src/test/resources/vectors` shows changes only together with a Python rule or format change in the same commit.
