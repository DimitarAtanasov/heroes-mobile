# Conformance vectors (Python -> Kotlin)

Python (`tools/h3re`) is authoritative (ADR-0004). The Kotlin engine (`android/sim`,
package `h3.sim`) is correct only when it reproduces every vector below byte for byte.
A rule or format change lands in Python first, then the vectors are regenerated in the same
change, then Kotlin follows. Vectors never contain timestamps and are never hand-edited.

## Generating and checking

- Generate: `cd tools/h3re && python3 -m h3re.vectors [--out DIR]`
  (default `android/sim/src/test/resources/vectors/`).
- Check without writing: `python3 -m h3re.vectors --check` (exit 1 if stale).
- `tools/h3re/tests/test_vectors.py` asserts the generator is deterministic and that the
  committed files equal a fresh generation, so Python drift fails the Python suite until the
  vectors are regenerated and reviewed.
- Kotlin: `cd android && gradle :sim:test` (the `:app` module is only included with
  `-PwithApp=true`, because the Android Gradle plugin needs the Google Maven repository).

## File format

Each file is `json.dumps(obj, sort_keys=True, separators=(",", ":"))` plus one LF, pure
ASCII (non-ASCII escaped), top-level `"format": 1`. Integers may exceed 2^53 and 2^64; readers
must parse them exactly (the Kotlin test reader uses `BigInteger`). Booleans are JSON booleans.

### `rng.json`
- `published`: `{seed, seq, u32[6]}`, the published PCG32 check vector (seed 42, seq 54).
- `pcg32_u32`: cases `{seed, seq, state, inc, u32[1000]}`; `state`/`inc` are the generator
  after seeding, before the first draw.
- `pcg32_ops`: cases `{seed, seq, ops, out}`. `ops` entries are `["u32"]`,
  `["range", lo, hi]` (half-open), `["randint", lo, hi]` (inclusive), `["chance", num, den]`;
  `out` holds the results in order (ints, or booleans for `chance`). 1000 ops per case, including
  spans of 1 and 2^32, negative bounds, and `chance` with num <= 0 and num >= den (no draw).
- `derived`: cases `{master, domain, id, state, inc, ops, out}` for `derive_stream(master,
  domain, id)`: negative and > 64-bit master seeds (byte length `max(8, (bit_length(|x|)+8)//8)`,
  little-endian two's complement), empty domain/id, non-ASCII and astral text, NUL, long
  strings, and field-boundary cases (`"a","bc"` vs `"ab","c"`).

### `canonical_json.json`
Cases `{name, value, hex, sha256}`: `hex` is the canonical encoding of `value` (ADR-0001), and
`sha256` its digest. Rules the Kotlin encoder must match:
- keys sorted by Unicode **code point** (not UTF-16 unit: U+1F600 sorts after U+FFFF);
- compact separators, no whitespace;
- `ensure_ascii=True`: everything outside 0x20..0x7E is escaped, including DEL (`\u007f`);
  escapes are `\" \\ \n \r \t \b \f`, other controls and non-ASCII as lowercase `\uXXXX`
  (astral characters as UTF-16 surrogate pairs);
- ints (arbitrary size), strings, lists, string-keyed maps, booleans, null. No floats; other
  types are rejected.

### `state_hash.json`
Cases `{name, canonical, sha256}` built through the public battle API (golden scenario of
`tests/test_battle.py`, state before and after `Begin` with `battle_rng(12345, "golden")`).
`canonical` is the `battle.canonical` text. Kotlin currently parses it and checks that
re-encoding is identical and the SHA-256 matches; once `h3.sim` has a battle state, tests will
build the state natively, compare, and add per-step hashes from replays (follow-up).
`golden_setup()` in `vectors.py` mirrors the test's by hand; these vectors move with the
battle rules (including re-pins per ADR-0001) and must be regenerated with them.

## Python/Kotlin differences resolved
- Unsigned 64-bit arithmetic uses `ULong`; outputs and bounds are `Long` (u32 fits).
- Python `str` ordering is by code point; Kotlin `String` by UTF-16 unit. The encoder sorts by
  code point explicitly.
- Java `BigInteger.bitLength()` differs from Python for negatives; the seed byte length uses
  `abs().bitLength()`, matching Python's `bit_length()`.
- Lone surrogates cannot be UTF-8 encoded in Python and are excluded from vectors.
