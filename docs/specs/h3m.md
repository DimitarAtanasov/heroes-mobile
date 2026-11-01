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
readers named below, `readEvents`, `readEventCommon`, `readMessageAndGuards`, `readQuest`,
`readCreatureSet`), `lib/mapping/MapReaderH3M.cpp` (id widths, sentinels,
bitmask byte counts, `readInt3`, `readBool`), `lib/mapping/MapFeaturesH3M.cpp`
(per-version sizes), `lib/mapObjects/ObjectTemplate.cpp` (`readMap`), and
`lib/constants/EntityIdentifiers.h` (object class ids). The bodies added for
signs through quest guards were checked against VCMI commit c53e0e8; each
reader carries a provenance comment naming it (ADR-0003, ADR-0010).

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
subid for mines, grails and border gates). `MapObject` carries `index`, `offset`
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
| 91 sign, 59 ocean bottle | `sign` | string message; 4 reserved. (`readSign`) |
| 33 garrison, 219 garrison (vertical) | `garrison` | u32 owner (raw, 255 = neutral); army; AB+: flag removable units (RoE: reported as `True`); 8 reserved. (`readGarrison`) |
| 36 grail (subid < 1000) | `grail` | i32 radius. (`readGrail`) |
| 42 lighthouse | `lighthouse` | u32 owner (raw). (`readLighthouse`) |
| 87 shipyard | `shipyard` | u32 owner (raw). (`readShipyard`) |
| 81 scholar | `scholar` | i8 bonus type (raw: -1 random, 0 primary, 1 secondary, 2 spell; VCMI clamps out-of-range values, we keep them); u8 bonus id; 6 reserved. (`readScholar`) |
| 88-90 shrines | `shrine` | u32 spell id (255 -> `None`; 0 is a real spell id). (`readShrine`) |
| 113 witch hut | `witch_hut` | RoE: no body (`skills_mask`/`skills` are `None`); AB+: 4-byte skill mask, set bit = ALLOWED (not inverted), `skills` = ids < 28. (`readWitchHut`) |
| 214 hero placeholder | `hero_placeholder` | u8 owner (0xFF -> `None`); u8 hero type (0xFF -> `None`); if 0xFF, u8 power rank, else `power_rank` is `None`. (`readHeroPlaceholder`) |
| 83 seer hut | `seer_hut` | quest (below); if no quest, 1 reserved byte and `reward` is `None`, else a reward (below); 2 reserved. RoE quest: one artifact id (u8; 0xFF = no quest) giving `{"type": 5, "artifacts": [id], "deadline": None, texts None}`. AB+ (and every version for quest guards): the quest record below. (`readSeerHut`, `readSeerHutQuest`) |
| 215 quest guard | `quest_guard` | quest record (below), nothing else; `quest` is `None` for type 0. (`readQuestGuard`) |
| generic set (below) | `generic` | no body. |

Box (events and Pandora's boxes, `readBoxContent`): message+guards; u32
experience; i32 mana; i8 morale; i8 luck; resources; 4 x u8 primary skills;
u8 count + (u8 skill, u8 level); u8 count + artifact ids; u8 count + u8 spell
ids; u8 count + (creature id, u16 count); 8 reserved.

Quest record (`readQuest`), dict `quest` or `None`: u8 type, read as i8 and
required to be 0-10 (else `H3mError`, as VCMI's strict read throws). 0 = no
quest (nothing else follows). Type payloads: 1 level (u32 `level`); 2 primary
skills (4 x u8 `primary_skills`); 3 kill hero, 4 kill creature (u32
`target_identifier`, the identifier of the target object); 5 artifacts (u8
count, then artifact ids, `artifacts`); 6 army (u8 count, then (creature id,
u16 count), `creatures`); 7 resources (7 x u32 `resources`); 8 be hero (u8
`hero`, 0xFF -> `None`); 9 be player (u8 `player`, 0xFF -> `None`); 10 is
HotA's multi-mission placeholder and raises `H3mError` (not supported before
HotA). Types 1-9 then have i32 `deadline` (last day, -1 = none, raw) and three
strings `first_visit`, `next_visit`, `completed`.

Seer hut reward (`readSeerHutQuest`), dict `reward`: u8 type, read as i8 and
required to be 0-10 (else `H3mError`). 0 nothing; 1 u32 `experience`; 2 u32
`mana`; 3 i8 `morale`; 4 i8 `luck`; 5 i8 `resource` + u32 `amount`; 6 u8
`primary_skill` + u8 `amount`; 7 u8 `skill` + i8 `level`; 8 `artifact` id
(u8/u16 by version); 9 u8 `spell`; 10 `creature` id + u16 `count`. Values are
kept raw (VCMI clamps morale/luck to -3..3 and skill level to 1..3; we do not).

Generic (no body in RoE/AB/SoD): every class id in VCMI's object enum that
is not listed above or below, i.e. 2-39, 41-138, 143, 147-161, 212 (subid
< 1000), 213, 221-231 minus the body classes. This includes border guard 9,
keymaster 10 and border gate 212 (subid < 1000; read with VCMI's generic
reader), banks (16, 24, 25, 84, 85), pyramid / WoG object 63, treasure chest,
corpse, flotsam, lean-to, campfire, wagon, black market, university and
similar, whose readers only read data at HotA levels.

Unsupported, raising `H3mUnsupportedObject` (an `H3mError` subclass with
`index`, `offset` (record), `body_offset`, `class_id`, `subid`); never skipped,
never length-guessed:
- border gate 212 with subid >= 1000 (HotA quest gate 1000, grave 1001; VCMI
  reads other subids >= 1002 generically, we still reject them as HotA-only);
- grail 36 with subid >= 1000 (HotA arena battle location);
- any class id outside the enum (0, 1, 40, 139-142, 144-146 HotA, 165-211,
  232+).
These are HotA-only or unknown; HotA maps are already rejected at the header,
so a real RoE/AB/SoD map reaches them only if it uses an id VCMI does not know.
Quest type 10 (HotA multi-mission) raises a plain `H3mError` with its offset.
Because the object list is sequential, the first unsupported object stops
parsing.

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
   1024, hero skills 28) are our sanity bounds, not engine limits. Quest
   artifact/creature counts are u8 and checked against remaining bytes.
12. RoE seer hut: VCMI also treats an artifact id >= the RoE artifact count
   (127) as "no quest" (and then reads the 1 empty-reward byte); we treat only
   0xFF as no quest, so such an out-of-range id is read as an artifact quest.
   A real map doing this would desynchronise one of the two readers.
13. Quest guards read the AB-style quest record in every version, including
   RoE (VCMI does not gate it); the class is believed absent from RoE maps.
14. Witch hut mask polarity (set = allowed) and the RoE witch hut having no
   body follow VCMI (`readBitmaskSkills(..., false)`, `levelAB` gate).
15. Kill-hero / kill-creature targets are the u32 identifier of the target
   object (matching hero/monster `identifier`); not resolved here.
16. The shrine spell is a u32 where 255 means none; other out-of-range values
   are kept raw.

## Not implemented
HotA-only object subids and quest type 10 listed above; HotA layouts. Errors raise
`H3mError`.
