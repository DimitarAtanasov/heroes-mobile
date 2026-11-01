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

Palette indices 0-9 are special (0 transparent, 1/4 shadow-like, others
selection/outline effects). The renderer treats 0 as transparent and 1/4 as
approximate semi-transparent black; other effect colors are left as palette RGB.

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
- Frame `size` is recorded but not used for validation. Palette-cycling and
  the special-color semantics are not modeled.
- Output: `Frame.pixels` (indices), `frame_to_canvas`, `to_rgb`/`to_rgba`,
  `write_ppm`, `write_png` (8-bit RGB/RGBA, zlib, no third-party libs).
- Malformed input raises `DefError` (truncation, bad format, overrunning runs,
  implausible counts/dimensions).
