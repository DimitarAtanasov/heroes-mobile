# HoMM3 PCX bitmap variant (clean-room notes)

Implemented in `tools/h3re/h3re/pcx.py`. All integers little-endian.
Only the variant used by HoMM3 is handled; this is not a general PCX reader
(no RLE, no header magic, no other bit depths).

## Header (12 bytes)
| Offset | Size | Field |
|---|---|---|
| 0 | u32 | data size |
| 4 | u32 | width |
| 8 | u32 | height |

Width and height must be 1..8192 (`MAX_DIM`). Zero or larger values raise `PcxError`.

## Mode selection
The data size field decides the mode. Let n = width * height.

- `size == n`: **indexed**. Body is n bytes of palette indices (row-major),
  followed by a 768-byte palette of 256 RGB triples. Total length must be at
  least `12 + n + 768`; extra trailing bytes are ignored.
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
- **Unverified: 24-bit channel order.** The spec task describes the 24-bit
  body as BGR. `to_rgb()` swaps the first and third byte of every triple on
  that basis. This has not been checked against real HoMM3 assets. If the
  data is actually RGB, only `PcxImage.to_rgb()` for bgr24 needs to change.
- The 8-bit palette is assumed to be the last 768 bytes of the file, with no
  marker or count field. This holds for the synthetic fixtures only.
- Palette entries are not validated for range (every byte is valid).

## Errors
`PcxError` (subclass of `ValueError`) is raised for: non-bytes input, truncated
header or body, size matching neither mode, dimensions of 0 or above the cap.
