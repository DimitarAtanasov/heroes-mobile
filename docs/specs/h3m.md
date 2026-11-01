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

## After teams (parsed; then terrain tiles)
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
   14 MiB). By default parsing stops here and later bytes are ignored; with
   `parse_h3m(data, objects=True)` (or `parse_h3m_bytes(raw, objects=True)`)
   the sections below are parsed too.
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

## Objects, object instances and events (`objects=True`)
Opt-in keyword (default `False`), so the existing API, the header-only
behaviour and the CLI `h3m-info` are unchanged. Results go on the same
`H3mHeader`: `objects_parsed` (bool), `templates` (list of `ObjectTemplate`),
`objects` (list of `MapObject`), `events` (list of dicts), `trailing_bytes`.
All reads are bounds-checked; every count is capped and also checked against
the bytes that remain (count x minimum record size) before any loop, so a
lying count raises `H3mError` instead of allocating.

Order after the tiles: template table, object instances, global events, then
end of data. Source for every layout fact below (functional facts only, no
code copied): VCMI `lib/mapping/MapFormatH3M.cpp` (`init` call order,
`readObjectTemplates`, `readObjects`, `readObject` dispatch, the per-class
readers named below, `readEvents`, `readEventCommon`, `readMessageAndGuards`,
`readCreatureSet`), `lib/mapping/MapReaderH3M.cpp` (id widths, sentinels,
bitmask byte counts, `readInt3`, `readBool`), `lib/mapping/MapFeaturesH3M.cpp`
(per-version sizes), `lib/mapObjects/ObjectTemplate.cpp` (`readMap`), and
`lib/constants/EntityIdentifiers.h` (object class ids).

### Template table
u32 count (cap 65536), then per template (46 bytes + name):
string def name; 6-byte passable mask; 6-byte active mask; u16 terrain mask
(read but not used by VCMI; kept as `terrain_mask_first`); u16 allowed-terrains
mask (bit i = terrain id i, `allowed_terrains`); u32 class id; u32 subid; u8
type (object group: 2 creature, 3 hero, 4 artifact, 5 resource); u8 draw-order
flag (VCMI uses it as a print priority); 16 reserved bytes (kept raw).
Mask semantics (kept raw, not decoded): byte i is a row, bit j a column; rows
and columns are counted from the bottom-right corner of the 8x6 footprint
(row 5-i, column 7-j). Passable mask: bit clear = blocked tile. Active mask:
bit set = visitable tile. Templates with unknown class ids are accepted; the
check happens when an instance uses them.

### Object instances
u32 count (cap 262144). Per object (`MapObject`): 3 bytes x, y, level; u32
template index (must be < template count, else `H3mError`); 5 reserved
bytes; then a class-specific body chosen by the template's class id (and
subid for mines and border gates). `MapObject` carries `index`, `offset`
(byte offset of the record in the decompressed data), `x`, `y`, `level`,
`template_index`, `class_id`, `subid`, `kind` and `body` (dict). Positions are
not range-checked (VCMI allows anchors up to 8 tiles past the edge).
Errors inside a body are re-raised as `H3mError("object N at offset O (class
C): ...")`.

Common pieces. Ids: artifact and creature ids are u8 in RoE and u16 in AB+
(sentinel 0xFF / 0xFFFF -> `None`); hero, portrait, skill and spell ids are
u8. Army: 7 slots of (creature id, u16 count), list of tuples. Resources: 7 x
i32 (all versions). Flags: a byte whose low bit is set counts as true (VCMI
`readBool`). Message+guards: flag; if set, string message, flag has-guards
(then army), 4 reserved bytes. Reserved bytes are skipped, not checked.
Owner u8 0xFF -> `None`; owner u32 kept raw (255 = neutral).

| Class ids | kind | Body |
|---|---|---|
| 98 town, 77 random town | `town` | AB+: u32 identifier; u8 owner; flag + name; flag + army; u8 formation; flag custom buildings: if set 6-byte built mask + 6-byte forbidden mask, else u8 has-fort; AB+: 9-byte obligatory spells mask; 9-byte possible-spells mask (set = banned); u32 town event count (cap 1024), each = common event + 6-byte buildings mask + 7 x u16 creatures + 4 reserved; SoD+: u8 alignment (raw); 3 reserved. (`readTown`) |
| 34 hero, 70 random hero, 62 prison | `hero` | AB+: u32 identifier; u8 owner; u8 hero type (0xFF random -> `None`); flag + name; SoD+: flag + u32 experience, RoE/AB: u32 experience (0 = unset); flag + u8 portrait; flag + u32 skill count (cap 28) + (u8 skill, u8 level); flag + army; u8 formation; flag artifacts: 18 (RoE/AB) / 19 (SoD) slot ids, u16 backpack count, ids; u8 patrol radius (0xFF none); AB+: flag + biography, u8 gender (0xFF default); SoD+: flag + 9-byte spell mask; AB only: u8 spell (raw; 0xFF none, 0xFE preset); SoD+: flag + 4 x u8 primary skills; 16 reserved. (`readHero`, `loadArtifactsOfHero`) |
| 54 monster, 71-75 and 162-164 random monsters | `monster` | AB+: u32 identifier; u16 count; u8 character; flag message: string + resources + artifact id; flag never flees; flag not growing; 2 reserved. (`readMonster`) |
| 53 mine (subid < 7) | `mine` | u32 owner. (`readMine`) |
| 53 (subid >= 7), 220 abandoned mine | `abandoned_mine` | 4-byte resource mask (bits 0-6 = resource ids). (`readAbandonedMine`) |
| 79 resource, 76 random resource | `resource` | message+guards; u32 amount (raw: VCMI scales it per resource type, we do not); 4 reserved. (`readResource`) |
| 5 artifact, 65-69 random artifacts | `artifact` | message+guards. (`readArtifact`) |
| 93 spell scroll | `spell_scroll` | message+guards; u32 spell id. (`readScroll`) |
| 17-20 dwellings | `dwelling` | u32 owner. (`readDwelling`) |
| 216, 217, 218 random dwellings | `random_dwelling` | u32 owner; 216/217: u32 faction identifier, if 0 a faction mask (u8 RoE, u16 AB+); 216/218: u8 min level, u8 max level (raw, 0-6). (`readDwellingRandom`) |
| 26 event | `event` | box; u8 player mask; flag computer activates; flag remove after visit; 4 reserved. (`readEvent`) |
| 6 Pandora's box | `pandora` | box. (`readPandora`) |
| generic set (below) | `generic` | no body. |

Box (events and Pandora's boxes, `readBoxContent`): message+guards; u32
experience; i32 mana; i8 morale; i8 luck; resources; 4 x u8 primary skills;
u8 count + (u8 skill, u8 level); u8 count + artifact ids; u8 count + u8 spell
ids; u8 count + (creature id, u16 count); 8 reserved.

Generic (no body in RoE/AB/SoD): every class id in VCMI's object enum that
is not listed above or below, i.e. 2-39, 41-138, 143, 147-161, 212 (subid
< 1000), 213, 221-231 minus the body classes. This includes banks (16, 24,
25, 84, 85), pyramid / WoG object 63, treasure chest, corpse, flotsam, lean-to,
campfire, wagon, black market, university and similar, whose readers only
read data at HotA levels.

Unsupported, raising `H3mUnsupportedObject` (an `H3mError` subclass with
`index`, `offset` (record), `body_offset`, `class_id`, `subid`); never skipped,
never length-guessed:
- known classes with a body we do not implement: garrison 33/219, grail 36,
  lighthouse 42, ocean bottle 59, scholar 81, seer hut 83, shipyard 87,
  shrines 88-90, sign 91, witch hut 113, hero placeholder 214, quest guard 215;
- border gate 212 with subid >= 1000 (HotA quest gate / grave);
- any class id outside the enum (0, 1, 40, 139-142, 144-146 HotA, 165-211,
  232+).
Because the object list is sequential, the first unsupported object stops
parsing; real maps with signs, seer huts, garrisons etc. are not yet fully
parseable.

### Global events
u32 count (cap 8192), each a common event: string name; string message;
resources; u8 player mask; SoD+: flag human affected (RoE/AB: reported as
`True`); flag computer affected; u16 first day; u16 repeat interval (0 = no
repeat); 16 reserved. Dict keys: `name`, `message`, `resources`,
`players_mask`, `human_affected`, `computer_affected`, `first_day`,
`repeat_days`. (`readEvents`, `readEventCommon`)

### End of data
VCMI reads nothing after the events. Remaining bytes are counted in
`trailing_bytes` and not interpreted or rejected.

### Unverified assumptions (objects section)
1. All layouts above come from VCMI source only; none has been checked
   against a real map in this repo (the gated real-map test asserts
   invariants only and accepts `H3mUnsupportedObject` as an outcome).
2. The generic (no-body) set is derived from VCMI's object enum and its
   dispatch; class ids missing from that enum (0, 1, 40, 139-142, 165-211) are
   treated as unknown. If real SoD maps use any of them, they will fail loudly
   and the set must be reviewed.
3. WoG (0x33) and Chronicles (0x1D) use SoD bodies; WoG-specific object
   classes, if any, will fail loudly.
4. Real maps are believed to end with zero padding after the events; we only
   count it (`trailing_bytes`). Not verified.
5. Reserved/"zero" bytes are skipped without checking (VCMI only warns).
6. Presence flags use the low bit (VCMI's tolerance); a stricter reading
   (only 0/1) is not used.
7. The first u16 template terrain mask's meaning is not established (VCMI
   ignores it); the second is taken as the allowed-terrains mask.
8. Field names `draw_order` and `type` follow VCMI's use (print priority,
   object group); both are kept raw.
9. Resource amounts are raw; VCMI applies a per-resource multiplier from game
   config (not part of the file format).
10. Random creature ids in armies (values above the creature count, encoding
   level/upgrade) are kept raw.
11. Count caps (templates 65536, objects 262144, events 8192, town events
   1024, hero skills 28) are our sanity bounds, not engine limits.

## Not implemented
Bodies of the unsupported classes listed above; HotA layouts. Errors raise
`H3mError`.
