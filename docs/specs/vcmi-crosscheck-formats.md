# VCMI cross-check: file-format specs

Scope: LOD, DEF, PCX, TXT, H3M. Compared our clean-room specs
(`docs/specs/{lod,def,pcx,txt,h3m}.md`) and code (`tools/h3re/h3re/{lod,defimg,pcx,txt,h3m}.py`)
against the GPL-2.0 VCMI engine (`/home/user/vcmi/vcmi`, repo vcmi/vcmi).

License note: this file records only functional facts (offsets, sizes, constants, semantics),
stated in our own words, each with a path citation. No VCMI code or comments were copied. Paths
are relative to the VCMI repo root. "Ours" means our spec/code. No other file was edited.

Sections of VCMI that matter most: `lib/filesystem/CArchiveLoader.cpp` (LOD),
`client/render/CDefFile.cpp` and `clientsdl2/render/ScalableImage.cpp` (DEF),
`clientsdl2/render/CBitmapHandler.cpp` (PCX), `lib/texts/CLegacyConfigParser.cpp` (TXT),
`lib/mapping/MapFormatH3M.cpp`, `MapReaderH3M.cpp`, `MapFeaturesH3M.cpp`, `MapFormat.h` (H3M).

## Mismatches, ranked by severity

| # | Sev | Format | Mismatch | Fix |
|---|-----|--------|----------|-----|
| 1 | HIGH | H3M | Victory condition type 10 (transport artifact) has a 3-byte position after the artifact byte. Ours reads only the artifact byte, so everything after it (loss condition, teams, masks, rumors, tiles) is misaligned or fails. | `h3m.py` `_read_victory` t==10: read `u8 artifact` then `pos3`. Fix `h3m.md` Conditions line. |
| 2 | HIGH | TXT | VCMI treats double quotes as field quoting (quote pairs inside a quoted field mean one literal quote) and only CR LF ends a record (a bare LF is data). Ours says "no quoting" and accepts bare LF as a terminator. Quoted legacy files get stray quote characters and wrong row splits. | `txt.py` / `txt.md`: add an opt-in "legacy" mode, or at least document the quoting. Decide the policy for bare LF. |
| 3 | MED | DEF | Reserved palette range is 0-7, not 0-9. Indices 8 and 9 are ordinary colors. Semantics per index are known (table below). Ours treats 0-9 as reserved and leaves 2, 3, 5, 6, 7 as plain palette RGB. | `def.md` special-index paragraph; `defimg.py` `to_rgba`: handle 2/3 conditionally, document 5/6/7. |
| 4 | MED | DEF | Legacy format-1 quirk: when a format-1 frame has width > full width AND height > full height, the engine ignores margins, takes width/height = full size, and starts pixel data 16 bytes earlier (only a 16-byte frame header). This applies to a known pair of old files. Ours has no handling and would misdecode or raise `DefError`. | `defimg.py` `_decode_frame`: add the special case. Add it to `def.md`. |
| 5 | MED | DEF | Formats 2 and 3: VCMI does not use the per-line / per-segment offset tables for every row. It reads only the first u16 (format 2) or the first u16 of each row (format 3, row stride `2*(width/32)` bytes using floor division), then decodes runs sequentially until the row is full. Ours uses `ceil(width/32)` per row and a per-segment offset. Equivalent only when width is a multiple of 32 and rows are packed contiguously. | `def.md`: record the floor-vs-ceil discrepancy. `defimg.py` fmt 3: tolerate `width % 32 != 0`, preferably by decoding rows sequentially. |
| 6 | MED | PCX | VCMI reads the 8-bit palette from the last 768 bytes of the file, not from right after the pixel data. Ours takes `12+n .. 12+n+768`. These differ if there are trailing bytes after the palette. Ours explicitly ignores trailing bytes, which is exactly where it would go wrong. | `pcx.py` `parse_pcx`: take the palette from `data[-768:]`. Update `pcx.md` and remove the "assumed" wording. |
| 7 | LOW | H3M | Artifact mask id limit for SoD is 144 (18 bytes x 8, all bits meaningful), not 141. Ours drops banned ids 141-143 from `banned_artifacts`. WoG count is 171 but the mask is still 18 bytes. | `h3m.py` `ARTIFACT_COUNT` default 141 -> 144. Fix `h3m.md` step 5. |
| 8 | LOW | H3M | Format ids 0x1D (Chronicles) and 0x20 (HotA, with a version number and an extended header) are supported by VCMI. Ours rejects them (clean error). WoG (0x33) and Chronicles share the SoD header layout. | Optional: add 0x1D as SoD-layout in `h3m.py`. Note HotA as unsupported in `h3m.md`. |
| 9 | LOW | TXT | Encoding is per game language (not always cp1252): cp1250, cp1251, cp1253, cp1254, cp1257, GBK, Big5, cp932, cp949, UTF-8 for a few. Ours hardcodes cp1252 and rejects bytes undefined in cp1252. VCMI does not strip a UTF-8 BOM. | `txt.py`: accept an `encoding=` argument. Document in `txt.md`. |
| 10 | LOW | LOD | Duplicate names: VCMI keeps the last entry (map assignment); ours rejects the archive. VCMI also never checks magic or version and silently ignores files shorter than 10 bytes; ours is stricter (acceptable). VCMI would run past a 16-byte name with no NUL; ours handles it. | Consider downgrading duplicates to "last wins" in `lod.py` for real archives. Keep the strict magic check as a deliberate choice. |
| 11 | INFO | H3M | Hero secondary-skill count in predefined hero records: VCMI expects <= 8 (it only warns above that); ours allows <= 28. Harmless. Road and river type bytes are masked with 0x07 by VCMI (high bits ignored); ours keeps raw bytes. | Optional note in `h3m.md`. |
| 12 | INFO | LOD family | VCMI also loads `.VID` and `.SND` archives, which have a different layout (below). Ours has no support. | Out of scope unless needed. |

Confirmed unverified assumptions (now backed by VCMI): LOD header/stride, tile layout and field
order, mask polarity, mask lengths, 31 reserved bytes in every version, PCX BGR order, DEF
palette position and block header layout, DEF compression formats 0 and 1, predefined hero record
order and the 19-slot SoD artifact set, WoG parsed as SoD.

## LOD (`docs/specs/lod.md`, `tools/h3re/h3re/lod.py`)

| Our assumption | VCMI fact | Match? | Action |
|---|---|---|---|
| Header 92 bytes; magic "LOD\0" | Directory starts at byte offset 0x5C (92). Magic is not read or checked. `lib/filesystem/CArchiveLoader.cpp` (`initLODArchive`: seek to 0x5C before the directory loop). | Yes (VCMI is looser) | None. Optional: keep strict magic as policy. |
| entry_count u32 at offset 8 | Count read as u32 at offset 8. Same file, same function. | Yes | None |
| version u32 at offset 4, opaque | Bytes 4-7 never read. Same file. | Yes | None |
| Entry stride 32: name[16], offset, uncompressed size, type, compressed size (all u32 LE) | Per entry: 16-byte name, u32 offset, u32 full size, u32 skipped as "unused/unknown", u32 compressed size. Total 32 bytes. Same file, loop body. | Yes | Remove the "unverified" caveats in `lod.md` open items. |
| `compressed_size == 0` means stored raw; otherwise zlib | Compressed size nonzero: stream of `compressedSize` bytes at offset, inflated to `fullSize`; zero: raw `fullSize` bytes at offset. `CArchiveLoader.cpp` `load()`. | Yes | None |
| zlib with header (RFC 1950) | Inflate initialised with 15 window bits (zlib wrapper, not gzip, not raw) for archive members. `lib/filesystem/CCompressedStream.cpp` constructor, gzip flag false from `CArchiveLoader::load`. | Yes | None |
| `type` field opaque | Skipped, never interpreted. `CArchiveLoader.cpp`. | Yes | None |
| Duplicate names invalid | Entries stored in a map keyed by mount point + name; a later duplicate overwrites an earlier one. `CArchiveLoader.cpp`. | No (stricter) | `lod.py`: consider last-wins for real files. |
| Archives shorter than header raise | Files under 10 bytes are silently treated as empty. `CArchiveLoader.cpp` constructor. | No (stricter) | Keep strict; document the difference. |
| Lookup case-insensitive | Resource names are case-normalised (ResourcePath uppercases). `lib/filesystem/ResourcePath.h`. | Yes | None |
| (not covered) other archives | `.PAC` uses the LOD path. `.VID`: u32 count, entries of 40-byte name + i32 offset (44-byte stride), size derived from the next higher offset. `.SND`: u32 count, entries of 40-byte name + i32 offset + i32 size (48-byte stride), VCMI appends ".wav" to the name. `CArchiveLoader.cpp` `initVIDArchive`, `initSNDArchive`. | n/a | Optional: add to `lod.md` as "related containers". |

## DEF (`docs/specs/def.md`, `tools/h3re/h3re/defimg.py`)

| Our assumption | VCMI fact | Match? | Action |
|---|---|---|---|
| Header: type, width, height, block count (4 x u32), palette 768 bytes at offset 16 (RGB) | Offset 0 type (skipped), 4 and 8 width/height (skipped), 12 block count, then 256 x RGB triples at offset 16. `client/render/CDefFile.cpp` constructor. | Yes | None |
| Type is an opaque category | Known values: 0x40 spell, 0x41 sprite, 0x42 creature, 0x43 map object, 0x44 map hero, 0x45 terrain, 0x46 cursor, 0x47 interface, 0x48 sprite frame, 0x49 battle hero. `client/render/CDefFile.cpp` (enum at top; values not used for decoding). | Partly (we expose the integer only) | Optionally add the names to `def.md`. |
| Block: id u32, count u32, 2 unknown u32 | Block id, entry count, then 8 bytes skipped. Same constructor. | Yes | None |
| Names 13 bytes NUL padded, then n u32 absolute offsets | 13-byte names, NUL-trimmed; then n u32 absolute offsets. Same. | Yes | None |
| Frame header 32 bytes: size, format, full w/h, w/h, x, y (i32 margins) | Fields in order: size, format, fullWidth, fullHeight, width, height, leftMargin (signed), topMargin (signed). `client/render/CDefFile.h` struct. The `size` field is not used by the decoder. | Yes | None |
| Format 0 raw rows of `width` bytes | Row-by-row copy of `width` bytes. `CDefFile.cpp` `loadFrame` case 0. | Yes | None |
| Format 1: height u32 row offsets (relative to end of 32-byte header); pair (code, len-1); 0xFF = raw | Same. Row offsets relative to the pixel-data start; segment byte then length-1; code 0xFF raw, else repeat of that index. Rows are decoded until `width` pixels. `CDefFile.cpp` case 1. | Yes | None |
| Format 2: height u16 row offsets; byte: code=b>>5, len=(b&31)+1; code 7 raw | Code is top 3 bits, length is low 5 bits + 1; code 7 raw, else repeat of palette index = code. Start position taken from the first u16 at the data start; subsequent rows continue sequentially. `CDefFile.cpp` case 2. | Layout yes; row addressing differs | `def.md`: note that engines read sequentially. Ours is fine for well-formed data. |
| Format 3: `height*ceil(width/32)` u16 offsets, one per 32-px segment | Offset table row stride is `2*(width/32)` bytes (floor division); only the first u16 of each row is used, then the row is decoded sequentially until `width`. Same run encoding as format 2. `CDefFile.cpp` case 3. | Partly | See mismatch #5. |
| (not modeled) legacy format-1 case | For format 1 when width > fullWidth and height > fullHeight: margins forced to 0, size forced to full size, and pixel data begins 16 bytes before the usual position. Comment names two old map-terrain defs. `CDefFile.cpp` `loadFrame` start. | No | See mismatch #4. |
| Special palette: 0 transparent; "1 and 4 shadow-like"; reserved range uncertain (0-9) | Reserved range is the first 8 entries only. Reference colors: 0=(0,255,255), 1=(255,150,255), 2=(255,100,255), 3=(255,50,255), 4=(255,0,255), 5=(255,255,0), 6=(180,0,255), 7=(0,255,0). A palette entry counts as "special" when within 8 per channel of the reference. `clientsdl2/render/ScalableImage.cpp` (`sourcePalette`, `colorsSimilar`). | No (range) | See mismatch #3. |
| Alpha: 1 -> 64, 4 -> 128 (guessed) | Targets: 0 alpha 0; 1 alpha 64 (shadow border); 2 alpha 64 (fog-of-war border); 3 alpha 128 (fog-of-war body); 4 alpha 128 (shadow body); 5 selection/owner-flag overlay (transparent when hidden); 6 alpha 128 and 7 alpha 64 (shadow below selection, battle defs). Indices 0, 1, 4 are always applied; 2 and 3 only when the actual palette color matches the reference. `ScalableImage.cpp` (`targetPalette`, `setShadowTransparency`). | Yes for 1 and 4; others not modeled | `defimg.py` `to_rgba`: confirm 64/128, add 2/3 conditional, treat 5 as overlay/flag, 6/7 as shadow when selection is hidden. Update `def.md`; the "guessed" label can go for 1 and 4. |
| Index 0 transparent | Index 0 is the color key for sprites. `clientsdl2/render/SDLImageLoader.cpp` (color key set to 0 after load). | Yes | None |
| Indices 8, 9 reserved | No special handling anywhere for 8 and above. `ScalableImage.cpp` (only first 8 compared). | No | Remove from reserved range in `def.md` and in `engine-design.md`. |

## PCX (`docs/specs/pcx.md`, `tools/h3re/h3re/pcx.py`)

| Our assumption | VCMI fact | Match? | Action |
|---|---|---|---|
| Header 12 bytes: size, width, height (u32 LE) | Same three u32 values at offsets 0, 4, 8; pixel data starts at offset 12 (0xC). `clientsdl2/render/CBitmapHandler.cpp` `loadH3PCX`. | Yes | None |
| size == w*h indexed; size == 3*w*h 24-bit; else error | The file is recognised as this variant only when size equals w*h or 3*w*h (`isPCX`); any other value returns failure. `CBitmapHandler.cpp`. | Yes | None |
| Indexed: n index bytes row-major, then 256 x RGB palette right after pixels | Rows copied top to bottom, no padding or flip. Palette is taken from the last 768 bytes of the whole file, RGB order. `CBitmapHandler.cpp` (`loadH3PCX`, 8-bit branch). | Partly (position) | See mismatch #6. |
| 24-bit stored BGR (unverified) | Pixels copied straight into a surface whose masks put blue in the lowest byte, red in the highest (little-endian), i.e. bytes are B, G, R. Rows are tightly packed (`width*3`), no padding. `CBitmapHandler.cpp` 24-bit branch. | Yes (confirmed) | Remove "unverified" from `pcx.md` open items and `pcx.py` comment. |
| Max dimension 8192 | No dimension cap in VCMI. | n/a (ours stricter) | Keep as safety limit. |
| Trailing bytes ignored (indexed) | Not ignored in effect: they shift the palette location (palette read from end). | No | See mismatch #6. |
| (not modeled) transparency rule | If palette entry 0 equals (255,0,255): entry 0 becomes fully transparent, entry 1 gets alpha 32, entry 4 gets alpha 128, and 0 is the color key. Otherwise, if the palette contains exactly (0,255,255), that color is the color key. 24-bit images get a default key color. `CBitmapHandler.cpp` `loadBitmapFromDir`; key color constant in `client/render/Colors.cpp`. | n/a | Optional: document in `pcx.md` if alpha output is ever needed. |

## TXT (`docs/specs/txt.md`, `tools/h3re/h3re/txt.py`)

| Our assumption | VCMI fact | Match? | Action |
|---|---|---|---|
| Decoded as cp1252 | Encoding depends on the language of the data: cp1252 for English and most Western languages, cp1250 (Czech, Hungarian, Italian, Polish), cp1251 (Russian, Ukrainian, Belarusian, Bulgarian), cp1253, cp1254, cp1257, GBK, Big5, cp932, cp949, UTF-8 for Norwegian and Vietnamese. Pure-ASCII strings skip conversion. `lib/texts/Languages.h` (encoding column), `lib/texts/CLegacyConfigParser.cpp` `readString`. | Partly | See mismatch #9. |
| Field separator TAB | TAB. `CLegacyConfigParser.cpp` (field scanning stops at TAB or CR). | Yes | None |
| Records end with CRLF or LF | A record ends only at LF that follows a CR. A bare LF is treated as data inside an unquoted multi-line field. `CLegacyConfigParser.cpp` `isEndOfLine`. | No | See mismatch #2. |
| No quoting; quote chars are data | A field that starts with a double quote is quoted: text runs to the closing quote; a doubled quote inside means a literal quote; after the closing quote, unquoted text may continue. A quoted field with no closing quote ends at TAB or CR. `CLegacyConfigParser.cpp` `extractQuotedPart`, `extractQuotedString`. | No | See mismatch #2. |
| Blank line = one empty field | A line start at end-of-line yields an empty string. Same file `readRawString`. | Yes | None |
| Rows may differ in field count | Yes; the caller consumes fields and `endLine` skips the rest of a row. | Yes | None |
| Numeric columns not interpreted | Numbers are parsed by the caller; a comma is accepted as decimal separator; parse failure yields 0. `CLegacyConfigParser.cpp` `readNumber`. | n/a | Optional note for any future typed accessor. |
| UTF-8 BOM skipped | No BOM handling found. | n/a (ours is a superset) | Keep. |

## H3M (`docs/specs/h3m.md`, `tools/h3re/h3re/h3m.py`)

Reserved bytes per version: VCMI skips exactly 31 zero bytes after the disposed-heroes block for
every format (RoE, AB, SoD, CHR, WoG, HotA). Source: `lib/mapping/MapFormatH3M.cpp`
`readMapOptions`. HotA adds more fields after those 31 bytes (4 more zero bytes, then
version-gated fields), which is why HotA cannot be read with our layout.

| Our assumption | VCMI fact | Match? | Action |
|---|---|---|---|
| Gzip wrapper; content starts with u32 format | Compressed if the first three bytes are 1F 8B 08; an uncompressed stream is accepted when the first u32 is a known format id. Zip magic means a VCMI JSON map. `lib/mapping/CMapService.cpp` `getMapLoader`. | Yes | None |
| Format ids 0x0E RoE, 0x15 AB, 0x1C SoD, 0x33 WoG | Same, plus 0x1D Chronicles, 0x20 HotA, 0x64 VCMI. `lib/mapping/MapFormat.h`. | Yes (subset) | See mismatch #8. |
| After format: u8 has-hero, u32 size, u8 two-levels, name, desc, u8 difficulty, AB+: u8 max hero level | Order: "any players" flag (u8), size (i32, used for both width and height), levels flag (u8), name string, description string, difficulty (u8, range 0-4 checked), level limit (u8, AB and later only). `MapFormatH3M.cpp` `readHeader`. | Yes | None |
| Strings: u32 length + bytes, cp1252 | u32 length (rejects > 500000) then raw bytes, converted from the file's language encoding. `lib/filesystem/CBinaryReader.cpp` `readBaseString`; `MapFormatH3M.cpp` `readBasicString`. | Yes (encoding differs, see TXT #9) | `h3m.py`: optionally make the encoding a parameter. Lower the string cap to 500000 if matching engine behavior matters. |
| Players: 8 slots; inactive skip 6 / 12 / 13 bytes | VCMI never skips: it reads the full block for all 8 slots. Fields in order: can-human (u8), can-AI (u8), AI tactic (i8, -1..3), SoD+: 1 unused byte, faction mask (1 byte RoE, 2 bytes AB+; set bit = allowed), random-faction flag, has-main-town, [AB+: generate-hero-at-town u8, 1 unused byte], [town position 3 bytes], has-random-hero, main hero id (u8, 0xFF none), [portrait u8 + name string], AB+: 1 unused byte, u32 hero-name count, then (hero id u8, name string) pairs. `MapFormatH3M.cpp` `readPlayerInfo`. Summing an empty block gives 6 (RoE), 12 (AB), 13 (SoD). | Yes (the skip sizes are consistent with the full layout) | None |
| Factions: u8 RoE / u16 AB+ | `factionsBytes` 1 for RoE, 2 for AB+; HotA more. `MapFeaturesH3M.cpp`. | Yes | None |
| Victory type 0xFF none; else u8 allow-normal, u8 applies-to-AI, then by type | Type read as signed -1..12; -1 is standard win; two flag bytes follow otherwise. `MapFormatH3M.cpp` `readVictoryLossConditions`, `MapFormatH3M.h` enum. | Yes | None |
| Type 0 artifact (u8 RoE / u16 AB+) | Artifact id is u8 in RoE, u16 in AB and later; invalid = 0xFF / 0xFFFF. `MapReaderH3M.cpp` `readArtifact`. | Yes | None |
| Type 1 creature (u8/u16) + u32 count | Creature id u8 RoE / u16 AB+, then i32 count. `MapReaderH3M.cpp` `readCreature`; `MapFormatH3M.cpp`. | Yes | None |
| Type 2 resource u8 + u32 amount | Resource id (u8) + i32 amount. | Yes | None |
| Type 3 build city: pos, hall u8, castle u8 | Position (3 bytes), hall level 0-3, fort level 0-2, both u8. | Yes | None |
| Types 4-7: pos | 4 grail, 5 beat hero, 6 capture town, 7 beat monster: each a 3-byte position (grail z > 2 means "anywhere"). | Yes | None |
| Types 8-9: none | 8 take all dwellings, 9 take all mines: no extra data. | Yes | None |
| Type 10: transport artifact (u8) | Artifact id (u8, 0xFF none) followed by a 3-byte position. `MapFormatH3M.cpp` case TRANSPORTITEM; `MapReaderH3M.cpp` `readArtifact8`. | NO | Mismatch #1. |
| Types 11, 12 rejected | HotA only: 11 eliminate all monsters (no extra data), 12 survive N days (u32). | n/a | Only if HotA support is added. |
| Loss: 0xFF none; 0/1 pos; 2 u16 days | Range -1..2; 0 lose town (pos3), 1 lose hero (pos3), 2 time limit (u16 days). | Yes | None |
| Teams: u8 count, then 8 u8 if nonzero | Same; if count is 0, teams are derived from active players. `MapFormatH3M.cpp` `readTeamInfo`. | Yes | None |
| Allowed heroes: 16 bytes RoE, 20 AB+; set = allowed; ids < 128 / 156 | Same counts and bytes (`heroesBytes` 16 / 20, `heroesCount` 128 / 156); bit i of byte i/8 is hero i; set bit means allowed (no inversion). `MapFeaturesH3M.cpp`; `MapReaderH3M.cpp` `readBitmask`, `readBitmaskHeroes`. | Yes | None |
| AB+: u32 placeholder count then u8 ids | Same (hero id u8, count u32). `MapFormatH3M.cpp` `readAllowedHeroes`. | Yes | None |
| SoD+: u8 disposed count; each id, portrait, name string, u8 player mask | Same order; player mask is 1 byte, 8 bits, set = player. `MapFormatH3M.cpp` `readDisposedHeroes`. | Yes | None |
| 31 reserved bytes, all versions, after disposed heroes | Exactly 31 expected-zero bytes, all versions, in this position (after disposed heroes, before artifacts). `MapFormatH3M.cpp` `readMapOptions` / call order in `init`. | Yes (confirmed) | Remove from "unverified" list in `h3m.md`. |
| Artifact mask: AB 17 bytes, SoD 18; set = BANNED; ids < 129 / < 141 | Present for AB and later only (not RoE). Bytes 17 (AB), 18 (SoD, WoG, CHR). Set bit means banned (reader inverts). Counts: AB 129, SoD 144, WoG 171 (bytes unchanged). RoE feature table lists 16 bytes but they are never read. `MapFeaturesH3M.cpp`; `MapFormatH3M.cpp` `readAllowedArtifacts`. | Yes except SoD count | Mismatch #7. |
| Spells mask 9 bytes (70 spells), skills 4 bytes (28); SoD+; set = banned | Same sizes and counts; read only for SoD and later; inverted, so set = banned. `MapFormatH3M.cpp` `readAllowedSpellsAbilities`. | Yes | None |
| Rumors: u32 count, (string name, string text) | Same. Engine only warns above 1000 rumors; ours caps at 4096. `MapFormatH3M.cpp` `readRumors`. | Yes | None |
| Predefined heroes: SoD+, 156 records | SoD+ only; one record per hero id up to 156 (count prefix only in HotA). `MapFormatH3M.cpp` `readPredefinedHeroes`. | Yes | None |
| Record: flag; has-exp + u32; has-skills + u32 count + (skill u8, level u8); has-artifacts; has-bio + string; gender u8 (0xFF default); has-spells + 9-byte mask; has-primary + 4 x u8 | Same order and widths. Skill level checked 1-3; gender -1..1; spell mask set = has spell; primary skills attack, defense, power, knowledge as 4 bytes. Same function. | Yes | None |
| Artifacts: 19 x u16 slots (SoD), then u16 backpack count and u16 ids; 0xFFFF empty | Slots per version: 18 (RoE/AB), 19 (SoD and later); each id u16 (AB+), 0xFFFF = none; then u16 backpack count, each u16 id. In HotA >= 5 each artifact id is followed by an extra u16 spell id. `MapFormatH3M.cpp` `loadArtifactsOfHero`, `MapFeaturesH3M.cpp`. | Yes | None |
| Tiles: 7 bytes, level-major, then rows, then columns | Order is level, then y, then x; per tile: terrain u8, view u8, river type u8, river direction u8, road type u8, road direction u8, flags u8. Same order as ours. `MapFormatH3M.cpp` `readTerrain`. | Yes (confirmed) | Remove "UNVERIFIED" for tiles in `h3m.md`. |
| Tile flags byte "not interpreted" | Bits 0-1 terrain mirroring, bits 2-3 river mirroring, bits 4-5 road mirroring (per the draw/edit operations); bit 7 is set at runtime for favorable-winds objects. A road/river type byte is only meaningful in its low 3 bits. `lib/mapping/CMapOperation.cpp`, `CDrawRoadsOperation.cpp`, `TerrainTile.h`, `MapReaderH3M.cpp` `readRoad`, `readRiver`. | Partly (we keep raw) | Optional: document bit meanings in `h3m.md`; mask road/river with 0x07 when exposing types. |
| WoG parsed with SoD layout; extras unknown | The header region is identical to SoD for WoG (and CHR); the format level only changes counts and engine settings. `MapFeaturesH3M.cpp`. | Yes | Remove from "unverified" list. |
| Size 1..1024 sanity bound | No bound in the header reader (size is a plain i32). Standard sizes 36/72/108/144. | n/a | None |
