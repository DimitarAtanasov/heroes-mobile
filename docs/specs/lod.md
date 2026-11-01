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
| 8      | 4    | entry_count  | number of directory entries (`n`)  |
| 12     | 80   | (reserved)   | ignored on read                    |

The magic must match exactly. Any other value is rejected.

### Directory entry (32-byte stride)

Entry `i` starts at `92 + 32 * i`.

| Relative offset | Size | Field             | Notes                                              |
|-----------------|------|-------------------|----------------------------------------------------|
| 0               | 16   | name              | ASCII/Latin-1, NUL-padded. Text after the first NUL is ignored. |
| 16              | 4    | offset            | absolute file offset of the payload                |
| 20              | 4    | uncompressed_size | size of the member's decoded contents              |
| 24              | 4    | type              | opaque 32-bit value, exposed but not interpreted   |
| 28              | 4    | compressed_size   | `0` = payload is stored raw; non-zero = zlib       |

Entry size is 32 bytes. (The original brief said 80; that is the header padding.) Layout is from community documentation and unverified against a real archive.

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
- Two entries whose names compare equal under the lookup rule make the archive invalid.
- Directory order is preserved and reported by `LodArchive.list()`.

## Validation performed by the reader

Parsing fails with `LodFormatError` if any of these hold:

1. The file is shorter than 8 bytes, or the magic is wrong.
2. `entry_count` is greater than 1 048 576 (sanity cap).
3. The directory (`92 + 32 * entry_count` bytes) extends past end of file.
4. Any payload range `[offset, offset + stored_size)` extends past end of file, where
   `stored_size` is `compressed_size` if non-zero, else `uncompressed_size`. The sum is
   computed without overflow (Python integers).
5. A name is empty, or duplicates another name case-insensitively.

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

- The header field positions (count at offset 8 after magic+version, directory at offset 92) and the 32-byte
  stride follow the project brief. They have not been verified against a reference file.
- The meaning of the `type` field is unknown and is exposed as an integer only.
- The 48 trailing bytes in each directory entry are unidentified.
