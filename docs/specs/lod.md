# LOD archive format

Container format used by Heroes of Might and Magic 3 to store game assets.
This document describes the layout that `tools/h3re/h3re/lod.py` implements.
It was written clean-room from the layout summary in the project brief. It has
not been checked against a reference archive, and the parser never needs real
game files to run its tests.

All integers are unsigned and little-endian.

## File layout

```
offset 0                 header            92 bytes
offset 92                directory         entry_count * 32 bytes
offset 92 + 32 * n       payloads          referenced by directory entries
```

### Header (92 bytes)

| Offset | Size | Field        | Value                              |
|--------|------|--------------|------------------------------------|
| 0      | 4    | magic        | `4C 4F 44 00` (`"LOD\0"`)          |
| 4      | 4    | version      | opaque, not interpreted            |
| 8      | 4    | entry_count  | number of directory entries (`n`); read at offset 8 (confirmed by VCMI) |
| 12     | 80   | (reserved)   | ignored on read                    |

The magic must match exactly. Any other value is rejected. (The engine never
checks the magic or the version field; this reader does, as a deliberate
policy.)

### Directory entry (32-byte stride)

Entry `i` starts at `92 + 32 * i`.

| Relative offset | Size | Field             | Notes                                              |
|-----------------|------|-------------------|----------------------------------------------------|
| 0               | 16   | name              | ASCII/Latin-1, NUL-padded. Text after the first NUL is ignored. |
| 16              | 4    | offset            | absolute file offset of the payload                |
| 20              | 4    | uncompressed_size | size of the member's decoded contents              |
| 24              | 4    | type              | opaque 32-bit value, exposed but not interpreted   |
| 28              | 4    | compressed_size   | `0` = payload is stored raw; non-zero = zlib       |

Entry size is 32 bytes (confirmed by VCMI: 16-byte name, then four u32 fields, no
trailing bytes). The header is 92 bytes and the directory starts at offset 0x5C
(92), which the engine also uses.

### Payloads

- If `compressed_size == 0`, the payload is `uncompressed_size` raw bytes at `offset`.
- If `compressed_size != 0`, the payload is `compressed_size` bytes at `offset`. It is a
  zlib stream (RFC 1950, with header) that must decode to exactly `uncompressed_size`
  bytes.

A member with `uncompressed_size == 0` and `compressed_size == 0` is an empty file. Its
`offset` is still bounds-checked.

## Name rules

- Lookup is case-insensitive (ASCII-style `upper()` on the Latin-1 string).
- Names must be non-empty.
- Two entries whose names compare equal under the lookup rule are duplicates.
  Default (`strict=False`): the later entry wins, as the engine does (it stores
  entries in a map keyed by name). The name is kept in its first-appearance
  position in `list()`, and the entry data comes from the last duplicate.
  `strict=True` (`LodArchive(..., strict=True)` or `LodArchive.open(path, strict=True)`)
  rejects the archive with `LodFormatError` instead.
- Directory order (first appearance) is reported by `LodArchive.list()`.

## Validation performed by the reader

Parsing fails with `LodFormatError` if any of these hold:

1. The file is shorter than the 92-byte header, or the magic is wrong.
2. `entry_count` is greater than 1 048 576 (sanity cap). This is a limit of this
   reader, not an engine rule.
3. The directory (`92 + 32 * entry_count` bytes) extends past end of file.
4. Any payload range `[offset, offset + stored_size)` extends past end of file, where
   `stored_size` is `compressed_size` if non-zero, else `uncompressed_size`. The sum is
   computed without overflow (Python integers).
5. A name is empty. Duplicate names are handled per the `strict` option below.

Reading a member fails with `LodFormatError` if:

- the zlib data is corrupt or truncated;
- the stream decodes to more than `uncompressed_size` bytes (output is capped during
  decompression, so a decompression bomb cannot exhaust memory);
- the stream decodes to fewer bytes than `uncompressed_size`.

Looking up a name that does not exist raises `KeyError`.

## Extraction safety

`LodArchive.extract_all(dest)` writes each member as a plain file directly inside `dest`:

1. Every member name is validated before anything is created or written. A name is
   rejected if it is `.` or `..`, contains `/`, `\`, or `:`, contains a control character
   (below 0x20), or has leading or trailing whitespace.
2. The destination directory is created if missing.
3. For each member, a target path that is already a symlink is refused rather than
   followed. The resolved target must lie inside the resolved destination.

Extraction does not create subdirectories.

## Errors

| Exception          | Raised for                                             |
|--------------------|--------------------------------------------------------|
| `LodFormatError`   | any malformed, truncated, or out-of-bounds structure   |
| `KeyError`         | `read()` or `entry()` called with an unknown name      |

`LodFormatError` subclasses both `LodError` and `ValueError`.

## Open items

- Confirmed by VCMI (functional facts only; see `docs/specs/vcmi-crosscheck-formats.md`):
  header 92 bytes, entry count u32 at offset 8, 32-byte directory stride, zlib
  wrapper (RFC 1950, with header) for compressed members, and `compressed_size == 0`
  meaning raw storage.
- The meaning of the `type` field is unknown. The engine skips it, and we expose it as an integer only.
- Known difference: the engine accepts files shorter than the header (under 10 bytes
  are treated as empty) and does not check magic or version. This reader rejects both
  as a deliberate policy.
