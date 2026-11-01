# HoMM3 PCX bitmap variant (clean-room notes)

Implemented in `tools/h3re/h3re/pcx.py`. All integers little-endian.
Only the variant used by HoMM3 is handled; this is not a general PCX reader
(no RLE, no header magic, no other bit depths).
Layout cross-checked against VCMI; see `docs/specs/vcmi-crosscheck-formats.md`.

## Header (12 bytes)
| Offset | Size | Field |
|---|---|---|
| 0 | u32 | data size |
| 4 | u32 | width |
| 8 | u32 | height |

Width and height must be 1..8192 (`MAX_DIM`). Zero or larger values raise `PcxError`.

## Mode selection
The data size field decides the mode. Let n = width * height.

- `size == n`: **indexed**. Body is n bytes of palette indices (row-major)
  starting at offset 12. The 256 x RGB palette (768 bytes) is the **last 768
  bytes of the file**, not the bytes right after the pixels. Total length must
  be at least `12 + n + 768`. Bytes between the pixels and the palette are
  not used and are tolerated. Bytes after the palette are not stripped, so
  they shift the window the palette is read from.
- `size == 3 * n`: **24-bit**. Body is `size` bytes of pixels, three bytes per
  pixel, row-major, no palette. Total length must be at least `12 + size`.
- Any other size raises `PcxError`.

When n is 0 both rules would match, but zero dimensions are rejected first.

## Output model
`parse_pcx(bytes) -> PcxImage(width, height, mode, pixels, palette)`

- `mode`: `"indexed"` or `"bgr24"`.
- `pixels`: raw body bytes. Indices for indexed, stored triples for bgr24.
- `palette`: list of 256 `(r, g, b)` tuples for indexed, `None` for bgr24.
- `to_rgb()`: packed 8-bit RGB, width*height*3 bytes, row-major.
- `to_png()`: 8-bit RGB PNG via `defimg.write_png`.

## Open items
- The 24-bit body is stored BGR (first byte blue, third byte red). `to_rgb()`
  swaps the first and third byte of every triple. Confirmed against the VCMI
  engine's PCX loader (`clientsdl2/render/CBitmapHandler.cpp`, 24-bit branch,
  where the surface masks put blue in the lowest byte). Functional fact only.
- The 8-bit palette is the last 768 bytes of the file, RGB order, with no
  marker or count field. Confirmed against the VCMI engine's loader (same file,
  8-bit branch).
- VCMI has no dimension cap. We keep 1..8192 as a deliberate safety limit,
  stricter than the engine. The size rule (n or 3n, else error) matches.
- Palette entries are not validated for range (every byte is valid).
- Not modeled: the engine's transparency rule (palette entry 0 equal to
  (255,0,255) becomes transparent; an exact (0,255,255) entry is a color key).
  The parser returns opaque RGB only.

## Errors
`PcxError` (subclass of `ValueError`) is raised for: non-bytes input, truncated
header or body, size matching neither mode, dimensions of 0 or above the cap.
