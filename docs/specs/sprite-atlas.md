# Sprite atlas builder

Status: groundwork for MVP 0.2 (real sprites). Implements `docs/specs/android-app.md` 4.3 (atlas)
and 4.5 (memory/draw budget). Code: `android/presenter/.../SpriteAtlas.kt`. Pure JVM, integer-only,
no Android APIs. Tests use synthetic frames and the DEF conformance vectors only.

## Input and output

- `AtlasFrame(key, width, height, rgba, offsetX, offsetY, fullWidth, fullHeight, overlay?)`: straight
  RGBA, 4 bytes per pixel, row-major. Offsets and full canvas size are carried to `Atlas.meta`
  and do not affect packing. `overlay` is width*height bytes, nonzero = player-colour pixel.
- `Atlas(pages, rects, meta)`: `Page(width, height, argb: IntArray)`, `Rect(page, x, y, w, h)`.
  A frame with zero area gets `Rect(-1, 0, 0, w, h)` and uses no space.
- `AtlasBuilder(maxPage = 2048, padding = 1, budgetBytes = 96 MiB).build()` returns
  `BuildResult.Ok(atlas)` or `BuildResult.Failed(reason, message)`; it never throws for data
  problems. Reasons: `DUPLICATE_KEY`, `FRAME_TOO_LARGE`, `OVER_BUDGET`.

## Packing

1. Sort by (height descending, width descending, key ascending by UTF-16 code units). Input order
   never matters. Keys must be unique.
2. Each frame needs a cell of (w + padding) x (h + padding). A cell wider or taller than `maxPage`
   is `FRAME_TOO_LARGE` (a 2048 page holds at most 2047 px).
3. Shelf packer, first fit: pages in creation order, shelves in creation order; a frame goes into
   the first shelf with `cell.h <= shelf.h` and room to the right. Otherwise a new shelf opens on
   the first page with room below, otherwise a new page. A shelf's height is its first (tallest)
   cell.
4. The rect sits at the cell origin, so neighbours are separated by at least `padding` transparent
   pixels to the right and below. There is no padding at the page's left and top edge.
5. Page size is the used extent (max cell right edge, last shelf bottom), not `maxPage`; this
   keeps the memory estimate tight. Padding pixels are zero (transparent).

## Pixel conversion

Premultiplied ARGB `Int` = `a<<24 | r'<<16 | g'<<8 | b'` with `c' = (c*a + 127) / 255` (integer
division). This is exact round-to-nearest: `c*a/255` has a fractional part `k/255`, never `1/2`, so
there are no ties. Reference rows: a=0 -> 0; a=1: c=127 -> 0, c=128 -> 1; a=127: c=128 -> 64,
c=255 -> 127; a=128: c=255 -> 128; a=254: c=128 -> 127, c=255 -> 254; a=255 -> identity.

## Mask pages

`MaskPages.build(atlas, frames)` returns one `MaskPage(width, height, alpha8)` per atlas page, same
size, 255 inside a frame's rect where `overlay` is set and 0 elsewhere (the UI tints it, 4.3).
`DefFrames.from(prefix, def)` builds frames from a parsed DEF: colour from `DefFile.toRgba`, with
palette index 5 pixels (`Def.OVERLAY_INDEX`) cleared to transparent in the colour image (4.3 says
the selection index is left transparent there; `Def.toRgba` itself keeps it opaque) and set in the
overlay. Keys are `prefix/BBB/IIII` (zero padded) so key order is block, then frame index.

## Memory (4.5)

`Atlas.bytes()` = sum of `width*height*4` over pages (masks add 1 byte per pixel,
`MaskPage.bytes()`). `Atlas.checkBudget(limit)` returns `Within` or `Exceeded` with both numbers;
`build()` applies `budgetBytes` (default 96 MiB, the 4.3 decoded-bitmap cap) and returns
`OVER_BUDGET`. Per-creature budgeting and LRU eviction are the caller's job.

## Open points

- 4.3 sorts by (height, group, frame index); here the tie-break is width then key, and the
  caller encodes group/frame in the key. Decide whether width should be in the key.
- Fractional budget accounting for mask pages is not folded into `bytes()`.
- No edge extrusion: bilinear sampling at rect borders relies on the 1 px transparent gap.
