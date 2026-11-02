# H3M header conformance (vectors `h3m.json`)

Contract for the Kotlin port `h3.sim.H3m` of the header half of `tools/h3re/h3re/h3m.py`
(ADR-0004, ADR-0007). Layout facts live in `docs/specs/h3m.md`; this file defines the
vectors only. Vectors are synthetic (built in `tools/h3re/h3re/vectors_h3m.py`); no game
data. The lead wires `vectors_h3m` into `vectors.EXTRA_VECTOR_MODULES`.

## File

`{"format": 1, "cases": [...]}`. A case is `{"name", "hex" | ("of", "cut"), "expect"}`.
`of` names an earlier case; the bytes are that case's bytes cut to the first `cut` bytes
(used for the every-cut-point cases). The bytes go to `parse_h3m` / `H3m.parse` (gzip
detected by the `1f 8b` magic, otherwise plain).

`expect`: `{"ok": false, "error": "H3mError"}` (`"hota": true` when the error is the HotA
one, Kotlin `H3mHotaError`), or `{"ok": true, "header": DUMP}`.

Error messages are compared by class only (current behaviour): the Kotlin test checks that
`H3mError` (or `H3mHotaError` when `hota` is set) is thrown, never the message text. The
vectors carry no message, so Python and Kotlin wording may differ.

## Canonical dump

Sorted keys, compact, ASCII (`ensure_ascii`, so non-ASCII strings are `\uXXXX`). Masks are
lower-case hex, positions and tuples are lists, `predefined_heroes` is keyed by decimal
string, victory/loss are dicts holding only the fields of their type, and tiles are
`{"count", "sha256"}` plus `"raw"` (hex) when the map has at most 16 tiles. The Kotlin test
builds the same tree from the typed header and compares the canonical text.

## Behaviour pinned

- Versions RoE 0x0E, AB 0x15, SoD 0x1C, Chronicles 0x1D, WoG 0x33 accepted; HotA 0x20 and
  every other format refused. Size 1..1024, difficulty 0..4. Strings are Windows-1252 with
  undefined bytes as U+FFFD; a string over 1 MiB is refused.
- Victory types 0..10 (type 10: artifact byte then 3 position bytes), loss types 0..2,
  `0xFF` none; unknown types refused. Teams: a non-zero count byte means 8 team bytes.
- Masks: heroes 16 bytes (RoE, 128 ids) or 20 (156 ids); artifacts 17 (AB, 129) or 18
  (SoD+, 144); spells 9 (70), skills 4 (28); set bits are listed.
- Counts: player heroes and placeholders at most 256, rumors 4096, predefined secondary
  skills 28; each count is also checked against the bytes that remain before any loop.
- Gzip: single member only. Header flags with reserved bits, a method other than 8, a bad
  header CRC, a bad data CRC or length, a truncated stream and any byte after the member
  (trailing junk or a second member) are refused. Output of exactly 64 MiB (67108864 bytes) is
  accepted; the cap refuses only a stream that still has output past 64 MiB (vectors
  `gz_valid_exactly_64mib`, accepted, and `gz_valid_64mib_plus_1`, refused). Python sets the
  cap as `max_length` and rejects when input is left unconsumed; Kotlin probes for one more
  byte once 64 MiB is filled.
- Bytes after the tiles of a plain map are ignored (objects are not parsed).

## Not ported

Objects (templates, instances, events): `H3m.parse(bytes, objects = true)` throws
`H3mError`. Gzip is decoded with `java.util.zip.Inflater` over a hand-read gzip header
rather than `GZIPInputStream`, because `GZIPInputStream` silently accepts trailing bytes
and further members and cannot report where a member ended.
