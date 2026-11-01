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

Special palette indices (cross-checked against VCMI): only indices 0-7 are
reserved; 8 and above are ordinary colours (earlier "0-9" wording was wrong).
Reference colours: 0=(0,255,255), 1=(255,150,255), 2=(255,100,255),
3=(255,50,255), 4=(255,0,255), 5=(255,255,0), 6=(180,0,255), 7=(0,255,0).
Target alpha: 0 -> 0 (transparent), 1 -> 64 (shadow border), 2 -> 64
(fog-of-war border), 3 -> 128 (fog-of-war body), 4 -> 128 (shadow body),
5 = selection / owner-flag overlay (transparent only when hidden by the
renderer), 6 -> 128 and 7 -> 64 (shadow below selection, battle defs).
Indices 0, 1, 4 are always applied; 2 and 3 only when the actual palette colour
is within 8 per channel of its reference colour. `to_rgba` renders shadow
alphas as black with that alpha, keeps index 5 as its opaque palette colour
(exposed as `OVERLAY_INDEX`), and leaves 6/7 applied unconditionally.

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
- Legacy format 1: if width > full width AND height > full height, margins are
  forced to 0, width/height become the full size, and the pixel data starts 16
  bytes earlier than normal (at frame offset + 16; row offsets are relative to
  that start). Seen in two old terrain defs.
- Format 1: height u32 line offsets; each line is a sequence of (code, len-1)
  pairs: code 0xFF followed by len raw bytes, otherwise len copies of code.
- Format 2: only the first u16 of the frame is read (start of run data);
  lines are then decoded one after another until each holds `width` pixels.
  Each line is bytes b with code=b>>5,
  len=(b&31)+1: code 7 means len raw bytes follow, else len copies of index code.
- Format 3: same run encoding. Offset table row stride is 2*floor(width/32)
  bytes (floor, not ceil); only the first u16 of each row is read, and the row
  is decoded sequentially until `width` pixels. Equivalent to a per-segment
  table only for well-formed data with width a multiple of 32.

## Implementation status / caveats
- Formats 2 and 3 follow the VCMI cross-check; tested on synthetic fixtures.
- Palette-cycling is not modeled.
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
