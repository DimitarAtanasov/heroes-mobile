# Conformance: LOD archive and PCX bitmap readers

Status: Kotlin port of the readers in `docs/specs/lod.md` and `docs/specs/pcx.md`, with
synthetic cross-language vectors. Python (`tools/h3re/h3re/lod.py`, `pcx.py`) is the reference
oracle (ADR-0004, ADR-0007). This document covers only these two readers.

## Scope

| Piece | Python | Kotlin (`android/sim`) |
|---|---|---|
| LOD archive, read-only, in memory | `h3re/lod.py` `LodArchive` | `h3/sim/Lod.kt` `LodArchive.open(bytes, strict)` |
| LOD member name check (pre-extraction) | `_check_member_name` | `LodArchive.checkMemberName(name)` |
| PCX (indexed and 24-bit BGR), to RGB | `h3re/pcx.py` `parse_pcx`, `to_rgb` | `h3/sim/Pcx.kt` `parsePcx`, `PcxImage.toRgb()` |
| Vectors | `h3re/vectors_lodpcx.py` | `src/test/resources/vectors/lod.json`, `pcx.json` |

Not ported, deliberately:

- `LodArchive.extract_all` writes files, so it stays app-side (the app writes through the Storage
  Access Framework). The sim keeps only the pure name check it needs.
- `PcxImage.to_png` belongs to the presentation layer.
- The engine's transparency colour key (palette entry 0 equal to (255,0,255)) stays unmodelled,
  as in `pcx.md`.

`:sim` uses no Android or file APIs and no `Double` or `Float`. The uint32 header fields are `Long`.
Zlib uses `java.util.zip.Inflater` (zlib wrapper, RFC 1950), the same format as Python's `zlib`.

## Port fidelity

LOD (`Lod.kt` against `lod.py`):

- Header of 92 bytes, magic `LOD\0`, entry count u32 at offset 8, cap `1 << 20` entries, 32-byte
  entries (16-byte name, then offset, size, type, packed size as u32 LE).
- Names are Latin-1 up to the first NUL. An empty name is refused. A payload range that extends past
  the file end is refused. The range is computed in `Long`, so it cannot overflow.
- Duplicates (same upper-cased key): `strict` refuses, the default is last-wins. The listing keeps
  the first-appearance position, and each name is the name of the last duplicate.
- Inflate output stops at `size + 1` bytes. The output is produced in chunks of at most 64 KiB, so a
  declared size never drives an allocation. Exceeding the size, a truncated stream, a size mismatch,
  corrupt zlib data and a preset-dictionary request are all `LodFormatError`. Trailing bytes after
  the zlib end are ignored, as in Python.
- A missing name is `LodKeyError` (Python `KeyError`).

PCX (`Pcx.kt` against `pcx.py`):

- Dimensions must be 1..8192. Size `n = w*h` selects indexed mode, which needs `12 + n + 768`
  bytes. The palette is always the **last 768 bytes of the file**. Size `3n` selects 24-bit BGR mode,
  which needs `12 + 3n` bytes. Any other size is refused.
- `toRgb()` swaps the first and third byte of every BGR triple.

## Error categories

Vectors and tests name categories, not messages.

| Category | Kotlin | Raised for |
|---|---|---|
| `LodFormatError` | `LodFormatError` (a `LodError`) | every malformed, truncated or out-of-bounds archive or member |
| `KeyError` | `LodKeyError` (a `LodError`) | `entry` or `read` with an unknown name |
| `PcxError` | `PcxError` | every malformed bitmap |

## Vectors

Generated from Python by `h3re.vectors_lodpcx.generate()`. The orchestrator wires it into
`vectors.generate()`. Regenerate with `cd tools/h3re && python3 -m h3re.vectors` and review the diff.
Vectors are never edited by hand. Every archive and bitmap is synthetic and built in memory. No
game data is read or written.

`lod.json` (213 cases, about 70 KB) covers:

- valid archives: raw, compressed, empty, opaque type field, NUL-truncated name, 16-byte name,
  Latin-1 name, empty compressed member, trailing bytes;
- duplicates: last-wins, strict refusal, first-position listing;
- header: bad magic, empty file, 91-byte header, count at u32 max, count over cap, count at cap
  with a missing directory, count bombs, count larger or smaller than the members;
- bounds: offset past end, offset and size u32 overflow, packed size past end, empty name, NUL-first
  name;
- corrupt payloads: not zlib, declared size too small (expansion capped at size + 1), declared size
  too large, truncated stream, bad Adler-32, preset dictionary, zero size with data, empty stream;
- every proper prefix (`truncated_base_at_NNN`) of a valid archive, all refused at open.

Each member records its directory fields, its `lookup` name in lower case (which must read the same
bytes), and its data hex or a `LodFormatError` category. Each case also names a missing member, which
must raise `KeyError`.

`pcx.json` (49 cases, about 47 KB) covers: indexed 2x2 and 1x1, 24-bit 2x2 and 3x1, a gap before the
palette (tolerated), trailing bytes that shift the palette window, the 8192x1 width cap, truncation
at every cut point of a 24-bit 2x2 and at header, pixel and palette boundaries of a 1x1 indexed, and
size, dimension, header and empty-input errors.

## Results

- Python: `python3 -I -m unittest discover -s tests` in `tools/h3re` ran 579 tests, all OK (4 skipped,
  as before). New module tests: `tests/test_vectors_lodpcx.py` (9 tests).
- Kotlin: `gradle --offline :sim:test` is green. New tests: `LodTest` (6 methods) and `PcxTest`
  (4 methods), which replay both vector files with exact comparison of member lists, bytes and
  error categories.
- Mutation check: reading the PCX palette from right after the pixels (`12 + n`) instead of the last
  768 bytes, and reading the LOD count at offset 12 instead of 8, made
  6 test methods fail (4 in `LodTest`, 2 in `PcxTest`). The sources were then restored and the
  suite re-run green.

## Discrepancies flagged (CLAUDE.md law 10)

1. **Name upper-casing.** `lod.md` ("Name rules") says lookup is "ASCII-style `upper()`". The code
   (`lod.py` `_key`) calls `str.upper()`, which is full Unicode. On Latin-1 names that matters for
   U+00DF: `"straße.txt".upper()` is `"STRASSE.TXT"`, so the two names collide as duplicates. Kotlin
   matches the code (`uppercase(Locale.ROOT)`), and the vector `duplicate_sharp_s_upper_collides` pins
   it. The spec and the code disagree, so this is an open decision for an ADR. Neither the code nor the
   spec has been changed. The engine's actual rule is not verified here, since no reference archive is
   available.
2. **Member-name check whitespace.** `_check_member_name` uses Python `str.strip()`, which also strips
   U+0085 and U+00A0 in Latin-1 names. Kotlin checks exactly those characters (`PY_SPACE`). This matches
   the code. `lod.md` lists only the control-character and separator rules, so the spec is silent on it.

## Open items

- The vector files are built with Python's `zlib`, so the compressed hex depends on the zlib build.
  Kotlin only inflates them, so the Kotlin tests do not depend on that output. The freshness check
  (`test_committed_files_match_fresh_generation`) does compare bytes, so a different zlib build can
  make it fail: regenerate if so.
- The orchestrator still has to wire `vectors_lodpcx.generate()` into `vectors.generate()`. The
  existing `test_vectors.test_committed_files_match_fresh_generation` does not cover these two files
  until then.
