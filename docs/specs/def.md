# HoMM3 .DEF sprite container (clean-room notes)

Implemented in `tools/h3re/h3re/defimg.py`. All integers little-endian.

## Header
| Offset | Size | Field |
|---|---|---|
| 0 | u32 | type (sprite category) |
| 4 | u32 | width |
| 8 | u32 | height |
| 12 | u32 | block count |
| 16 | 768 | palette, 256 x RGB |

Special palette indices (UNCERTAIN): the low palette entries are reserved for
effects, but sources disagree on the range. This spec previously said 0-9;
`engine-design.md` says 0-7. Only index 0 (transparent) is certain; 1 and 4 are
believed shadow-like. Treat 0-9 as the conservative reserved range (a superset
of 0-7) until verified against real assets; indices 8 and 9 in particular are
unconfirmed. The renderer treats 0 as transparent and 1/4 as approximate
semi-transparent black (alpha 64/128, guessed); all others keep palette RGB.

## Blocks
Blocks follow the palette back to back. Each block:
- u32 block id, u32 entry count n, 2 unknown u32
- n frame names, 13 bytes each (NUL padded)
- n u32 absolute file offsets of frames

## Frame
32-byte header: u32 data size, u32 format, u32 full width, u32 full height,
u32 width, u32 height, i32 x, i32 y. The (width x height) image is placed at
(x, y) within the full-size canvas. Pixel data follows (offsets below are
relative to the end of the 32-byte header).

- Format 0: raw, width*height palette indices.
- Format 1: height u32 line offsets; each line is a sequence of (code, len-1)
  pairs: code 0xFF followed by len raw bytes, otherwise len copies of code.
- Format 2: height u16 line offsets; each line is bytes b with code=b>>5,
  len=(b&31)+1: code 7 means len raw bytes follow, else len copies of index code.
- Format 3: like 2, but height*ceil(width/32) u16 offsets, one per 32-pixel
  segment of each line.

## Implementation status / caveats
- Formats 2 and 3 offsets/layout are written from memory of community
  documentation and verified only against synthetic fixtures.
- Palette-cycling and the special-color semantics are not modeled.
- Frame `size` is the length of pixel data after the 32-byte header. It must fit
  in the file, must equal width*height for format 0, and all line/segment
  offsets and run data are confined to that window (else `DefError`).
- Hardening: frames sharing an offset are decoded once (cached; entries share
  the pixel buffer). `parse_def(data, max_pixels=MAX_TOTAL_PIXELS)` bounds the
  total pixels decoded over distinct frames (default 64M) and raises `DefError`.
- Empty frames (zero width/height): `write_png` raises `EmptyImageError`
  (a `ValueError`); use `frame_is_empty(frame)` or `frame_to_png(frame, palette)`
  (returns `None` for empty frames) to skip them.
- Output: `Frame.pixels` (indices), `frame_to_canvas`, `to_rgb`/`to_rgba`,
  `write_ppm`, `write_png` (8-bit RGB/RGBA, zlib, no third-party libs).
- Malformed input raises `DefError` (truncation, bad format, overrunning runs,
  implausible counts/dimensions).
