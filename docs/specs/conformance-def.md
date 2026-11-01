# DEF sprite decoder conformance (Kotlin contract)

Companion to `docs/specs/def.md` and (for the vector mechanics) `docs/specs/conformance.md`.
The Python reference is `tools/h3re/h3re/defimg.py`; the Kotlin port is
`android/sim/src/main/kotlin/h3/sim/Def.kt` (`Def.parse`, `Def.toRgba`, `Def.frameToCanvas`,
`DefFile.toRgba`, `DefFile.toRgbaCanvas`). Vectors: `android/sim/src/test/resources/vectors/def.json`,
produced by `tools/h3re/h3re/vectors_def.py` (`generate() -> {"def.json": doc}`), never edited by hand.
Wiring into `vectors.generate()` is the orchestrator's job (`out[name] = _dump(obj)` loop, as for battle).
Standalone: `python3 -m h3re.vectors_def [--out DIR]`.

## Files
All DEF inputs are synthetic (seeded `random.Random(0xDEF5)`); no game data. File size ~1.7 MB.
- `constants`: `max_blocks`, `max_entries`, `max_dim`, `max_total_pixels`, `color_tolerance`,
  `overlay_index`, `special_colors`, `special_alpha` (-1 = keep opaque colour).
- `cases[]`: `{name, note, hex, [max_pixels]}` plus either `error` ("DefError") or `ok`:
  `{type, width, height, blocks:[{id, frames:[...]}]}`. Palette is the 768 bytes at file offset 16.
  Per frame: `name_hex` (latin-1 bytes), `offset`, `size`, `fmt`, `full_width/height`, `width/height`,
  `x`, `y` (signed), `pixels_sha256`, `canvas_sha256`, and the RGBA hashes `rgba_sha256`,
  `rgba_noshadow_sha256`, `canvas_rgba_sha256`, `canvas_rgba_noshadow_sha256` (shadow = shadow_alpha
  true). Frames of at most 64 pixels (canvas: 64) also carry `pixels_hex`, `rgba_hex`, `canvas_hex`,
  `canvas_rgba_hex`. `max_pixels` present means `parse(data, max_pixels)`.
- `truncation_base_hex` and `truncations[]`: for every prefix length `cut` of the base file,
  `[cut, "error"]` or `[cut, "ok", frame_count]`.

## Coverage (279 cases: 202 ok, 77 error, plus 1397 truncation cut points)
Formats 0, 1, 2, 3 (small and large; format-1 runs of 256; format-3 widths 32, 40 (floor stride),
64, 96, 100; width 10 with stride 0 where every row decodes from the same u16); format-2
first-u16-only; legacy format 1 (three sizes, margins ignored, data at offset+16) and the non-legacy
case w > fw only; special palette indices 0-7 across four palette variants and a tolerance sweep
(index 2 and 3, each channel, delta 0..10, both signs); margins (inside, negative, clipped,
fully outside, int32 extremes, image larger than canvas in one direction, zero dimensions);
shared-offset frames across blocks, empty blocks, latin-1 / unterminated / NUL-embedded names;
malformed: block count 257/256/huge, entries 4097/4096, frame offset past end/huge/into header,
unknown format, dimension 8193, size field lies (too big, huge, too small, raw mismatch, legacy),
overrunning runs, bad line offsets (u16/u32), truncated tables and raw runs, pixel budget
(exact, one short, zero, shared-charged-once, legacy full size, RLE 8192x8192 bombs, two bombs
exceeding the default 64M budget), 120 random byte corruptions of a mixed-format base file.

## Contract
- Kotlin must succeed exactly where Python succeeds and throw `DefException` where Python raises
  `DefError`; messages are not compared. Successes must match byte for byte (indices, canvas, RGBA).
- Offsets, sizes and counts are u32 and handled as `Long`; x and y are int32. Integer-only.
- Python quirks pinned deliberately (see def.md): format 2 reads one u16 only; format 3 stride is
  `2*floor(w/32)`; only 0-7 are special; index 5 stays opaque; indices 2 and 3 need the colour match
  (per channel difference <= 8, inclusive); legacy frames are charged `fullW*fullH` pixels.

## Ambiguities / notes
- The default 64M budget is not exercised by a success case (a legitimate 64M-pixel frame would
  need a huge decode); budget behaviour is pinned through explicit `max_pixels`, plus one
  default-budget failure with two 8192x8192 frames.
- Python decodes a frame fully before the budget of a later frame is tested, so errors in an early
  frame mask later budget errors; Kotlin mirrors the same order.
