# HoMM3 .H3M map header (clean-room notes)

Implemented in `tools/h3re/h3re/h3m.py`. Files are gzip streams; little-endian.
Strings are u32 length + bytes (cp1252). Decompression is capped at 64 MiB.
Truncated gzip streams, trailing bytes after the stream, and multi-member
gzip files are rejected with `H3mError` (real maps are one gzip member).

## Header
| Field | Type |
|---|---|
| format | u32: 0x0E RoE, 0x15 AB, 0x1C SoD, 0x1D Chronicles (SoD layout), 0x33 WoG (SoD layout) |
| has hero | u8 |
| map size | u32 (square side); see note below |
| two levels | u8 |
| name, description | strings |
| difficulty | u8 (0-4) |
| max hero level | u8, only if not RoE |

HotA (0x20) is explicitly unsupported: it has a version number and an extended
header (4 more zero bytes after the 31 reserved bytes, plus version-gated
fields), so the parser raises `H3mError("unsupported map format 0x20 (HotA)...")`.

Map size note: real sizes are 36/72/108/144 (S/M/L/XL), and newer editions
(e.g. HotA) allow others. The parser only checks the permissive range
1..1024 as a sanity bound and does not enforce the standard sizes.

## Players (8 slots)
u8 can_human, u8 can_computer. If neither, skip 6 (RoE) / 12 (AB) / 13 (SoD+)
bytes. Otherwise: u8 AI behavior; SoD+: u8 customized-towns flag; allowed
factions bitmask (u8 RoE, u16 else); u8 random faction; u8 has main town
(then, non-RoE: u8 generate-hero-at-town, u8 generate-hero; then 3-byte x,y,z);
u8 has random hero; u8 main hero id (0xFF none, else u8 portrait + string
name); non-RoE: u8 placeholder, u32 count, then (u8 id, string name) pairs.

## Conditions and teams
Victory: u8 type (0xFF none) else u8 allow-normal-victory, u8 applies-to-AI,
then by type: 0 artifact (u8 RoE / u16 else), 1 creatures (u8/u16 id + u32
count), 2 resources (u8 type + u32 amount), 3 build city (pos, u8 hall,
u8 castle), 4-7 pos, 8-9 none, 10 transport artifact (u8 id, then 3-byte pos).
Loss: u8 type (0xFF none); 0/1 pos; 2 u16 days.
Teams: u8 count; if nonzero, 8 u8 team ids.

## After teams (parsed; then terrain tiles; stops before objects)
In order. "Mask" = little-endian bit order (bit i = byte i//8, bit i%8).
1. Allowed heroes mask: 16 bytes (RoE), 20 bytes (AB+). Set bit = allowed.
   Exposed as `allowed_heroes_mask` / `allowed_heroes` (ids < 128 RoE, < 156).
2. AB+: u32 placeholder count (cap 256), then u8 hero ids -> `placeholder_heroes`.
3. SoD+: u8 disposed count; each u8 id, u8 portrait, string name, u8 player
   bitmask -> `disposed_heroes` (dicts).
4. 31 reserved bytes (all versions).
5. AB+: allowed artifacts mask, 17 bytes (AB) / 18 (SoD). Set bit = BANNED
   (inverted vs heroes) -> `allowed_artifacts_mask`, `banned_artifacts`
   (ids < 129 AB, < 144 SoD/Chronicles; WoG's count is 171 but the mask is still
   18 bytes, so ids 144+ cannot be represented).
6. SoD+: spells mask 9 bytes (70 spells), skills mask 4 bytes (28 skills);
   set bit = banned -> `*_mask`, `banned_spells`, `banned_skills`.
7. Rumors: u32 count (cap 4096), each (string name, string text) -> `rumors`.
8. SoD+: 156 predefined hero records -> `predefined_heroes` {id: dict} (only
   customised heroes present). Record: u8 flag (0 = none); u8 has-exp (u32);
   u8 has-skills (u32 count <= 28, then u8 skill, u8 level); u8 has-artifacts
   (19 x u16 slots: 16 worn, catapult, spellbook, misc5; 0xFFFF empty; then
   u16 backpack count + u16 ids); u8 has-bio (string); u8 gender (0xFF
   default); u8 has-spells (9-byte mask); u8 has-primary (4 x u8 A/D/P/K).
9. Terrain tiles (all versions): size x size x (1 + two_levels) tiles, 7 bytes
   each, level 0 first, then rows, then columns: u8 terrain, u8 view, u8 river
   type, u8 river direction, u8 road type, u8 road direction, u8 flags.
   Exposed as `levels`, `tiles_raw` (bytes), `tile(x, y, level)` and a lazy
   `tiles` iterator of `Tile` tuples. Truncated tile data raises `H3mError`
   (the length is checked before any copy; size is capped at 1024, so at most
   14 MiB). Parsing stops here: bytes after the tiles (objects) are ignored.
New `H3mHeader` fields default to empty/None, so older construction still works.

## Verification status
Confirmed against VCMI source (functional facts only; no code copied): mask
polarity (heroes set = allowed; artifacts/spells/skills set = banned), mask
byte lengths and id limits, the 31 reserved bytes in every version, tile layout
and field order (level, row, column; 7 bytes), the SoD predefined hero record
(including 19 u16 artifact slots), and WoG/Chronicles using the SoD header.
Notes: VCMI expects at most 8 secondary skills per predefined hero (we allow
28), masks road/river type bytes with 0x07 (we keep raw bytes), and the tile
flags byte is kept raw (low bits are terrain/river/road mirroring).
Still unverified against real files: RoE/AB hero-count details.

## Not implemented
Objects (object templates, object instances), events. Errors raise `H3mError`.
