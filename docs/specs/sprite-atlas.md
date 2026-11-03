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

## Upscaling (0.2)

`SpriteScale.scale(frame, k)` enlarges a frame by an integer `k` in 1..4 (`k = 1` returns the frame).
The destination pixel centre maps to source position `(2*d + 1 - k) / (2k)`, and both axes use integer
weights over `2k`. Colour and alpha are bilinear, with colour averaged premultiplied, so a transparent
neighbour does not darken an edge. The overlay is sampled nearest, so the player-colour edge stays
crisp. Offsets and full canvas size scale by `k`. `SpriteLoadPlan.load(..., scale)` applies it to every
frame before packing (default 1, so the output is unchanged unless asked). The app requests
`SpriteLoader.SPRITE_SCALE = 2`. Scaling multiplies the atlas by `k*k`, so the 96 MiB budget still
applies and an over-budget atlas is reported as `OVER_BUDGET`, not partially loaded.

## Creature sprite table (0.2)

The loader side of android-app.md section 14 Q2 option (a): a creature-to-DEF table the owner writes,
keyed by the creature's row in `CRTRAITS.TXT` (ADR-0014), each entry citing its source (ADR-0003). The
table ships as `data/sprite_map.json` (ADR-0014: a cited port of facts, row and DEF member name
only). Parser:
`SpriteTable.parse(text)` in `:presenter` (`.../ui/SpriteTable.kt`); it is pure (the caller reads the
file). The app bundles the table (`copyH3Data`) and `SpriteLoader` reads and parses it on the
sprite worker through `SpriteRows.prepare`; a refused table means tokens, and every parse error is
logged with `describe()`.

```json
{
  "schema_version": 2,
  "entries": [
    { "row": 12, "def": "<MEMBER>.DEF", "source": "<citation>" }
  ]
}
```

- `row` is the ZERO-BASED position of the creature among the accepted creature records of
  `CRTRAITS.TXT`: the header is excluded, and blank rows and rows with an empty first cell do not
  count. The first creature record is row 0. This matches the VCMI creature index, so VCMI index
  values are used directly, with no +1. It is not the id used in this repo's `creatures.json`.
- Keys are exactly `schema_version` and `entries` at the top, and `row`, `def`, `source` per entry;
  anything missing, unknown or of the wrong type (for `def`, `source`) is `BAD_SHAPE`.
- `schema_version` is the integer 2; any other value, including 1, is `BAD_SCHEMA_VERSION`.
- `row` must be a JSON integer, non-negative and at most `Int.MAX_VALUE`; a negative, out-of-range or
  non-integer value (string, boolean, null, array, object) is `BAD_ROW`. A float is `INVALID_JSON`
  (see below). A second entry for the same row is `DUPLICATE_ROW`.
- `def` is a bare archive member name that ends in `.DEF` (exact case) with a stem. A `/` or `\` is
  `DEF_HAS_PATH`; anything else wrong is `BAD_DEF_NAME`. Whether the member exists is not checked
  here: `SpriteLoadPlan` reports `MISSING_DEF` at load time.
- `source` is required and must not be empty or only whitespace (`MISSING_SOURCE`). It states where
  the owner learned the fact, in the owner's words (ADR-0003). It is validated, not kept in the table.
- Text is read with the strict data-pack reader (`PackJson`, made public in `:sim` for this): integers
  only, duplicate object keys rejected. Invalid JSON, floats and duplicate keys are `INVALID_JSON`.
- The result is all or nothing. `SpriteTableResult.Ok(table)` holds `Map<Int, String>` (row to DEF
  member name) in file order. `Failed(errors)` lists every entry error in file order; structural
  errors (JSON, top-level shape, version) stop before any entry is read. It never throws.
- Error codes: `INVALID_JSON`, `BAD_SCHEMA_VERSION`, `BAD_SHAPE`, `BAD_ROW`, `MISSING_SOURCE`,
  `DUPLICATE_ROW`, `BAD_DEF_NAME`, `DEF_HAS_PATH`.
- Consumer: `SpriteLoadPlan.loadByRow(creatures, lods, table)` (with `resolveByRow` and
  `defForRow`) takes the parsed row-keyed table and `(row, creature name)` pairs, the row being the
  creature's CRTRAITS data-row index (`ContentResult.creatureRows`). The DEF is looked up by row
  only; the name is the atlas key and the name in errors. A row the table lacks is `NO_MAPPING` and
  the board draws the token. Repeated names are dropped (first wins); two rows may share a DEF,
  which is decoded once. Everything after the lookup is the same as `load`. The app uses this
  row path (slice 5 wiring): `SpriteRows.pairs` turns the roster entries into the pairs. The
  name-keyed `load`, `resolve`, `defFor` and `DEFAULT_TABLE` stay in `:presenter` (its tests use
  them); the app no longer calls them.
- Row mismatch: on load, `SpriteRows.mismatch` counts the distinct table rows that are not a battle
  roster row and the roster rows with no table entry, and the app logs one line
  `SPRITE_ROWS table_only=N roster_only=M` when either count is non-zero (counts only, no names).
  The battle roster leaves out the no-fixed-damage creatures, so their table rows count as
  `table_only`.

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
