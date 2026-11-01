# HoMM3 .H3M map header (clean-room notes)

Implemented in `tools/h3re/h3re/h3m.py`. Files are gzip streams; little-endian.
Strings are u32 length + bytes (cp1252). Decompression is capped at 64 MiB.
Truncated gzip streams, trailing bytes after the stream, and multi-member
gzip files are rejected with `H3mError` (real maps are one gzip member).

## Header
| Field | Type |
|---|---|
| format | u32: 0x0E RoE, 0x15 AB, 0x1C SoD, 0x33 WoG |
| has hero | u8 |
| map size | u32 (square side); see note below |
| two levels | u8 |
| name, description | strings |
| difficulty | u8 (0-4) |
| max hero level | u8, only if not RoE |

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
u8 castle), 4-7 pos, 8-9 none, 10 transport artifact (u8).
Loss: u8 type (0xFF none); 0/1 pos; 2 u16 days.
Teams: u8 count; if nonzero, 8 u8 team ids.

## After teams (parsed; stops before terrain/objects)
In order. "Mask" = little-endian bit order (bit i = byte i//8, bit i%8).
1. Allowed heroes mask: 16 bytes (RoE), 20 bytes (AB+). Set bit = allowed.
   Exposed as `allowed_heroes_mask` / `allowed_heroes` (ids < 128 RoE, < 156).
2. AB+: u32 placeholder count (cap 256), then u8 hero ids -> `placeholder_heroes`.
3. SoD+: u8 disposed count; each u8 id, u8 portrait, string name, u8 player
   bitmask -> `disposed_heroes` (dicts).
4. 31 reserved bytes (all versions).
5. AB+: allowed artifacts mask, 17 bytes (AB) / 18 (SoD). Set bit = BANNED
   (inverted vs heroes) -> `allowed_artifacts_mask`, `banned_artifacts`
   (ids < 129 AB, < 141 SoD).
6. SoD+: spells mask 9 bytes (70 spells), skills mask 4 bytes (28 skills);
   set bit = banned -> `*_mask`, `banned_spells`, `banned_skills`.
7. Rumors: u32 count (cap 4096), each (string name, string text) -> `rumors`.
8. SoD+: 156 predefined hero records -> `predefined_heroes` {id: dict} (only
   customised heroes present). Record: u8 flag (0 = none); u8 has-exp (u32);
   u8 has-skills (u32 count <= 28, then u8 skill, u8 level); u8 has-artifacts
   (19 x u16 slots: 16 worn, catapult, spellbook, misc5; 0xFFFF empty; then
   u16 backpack count + u16 ids); u8 has-bio (string); u8 gender (0xFF
   default); u8 has-spells (9-byte mask); u8 has-primary (4 x u8 A/D/P/K).
New `H3mHeader` fields default to empty/None, so older construction still works.

## Unverified against real files
No real maps were used; layouts come from recollection of community docs and
synthetic fixtures only. Especially uncertain:
- Bit polarity of artifacts/spells/skills masks (assumed set = banned).
- The 31 reserved bytes being present in RoE/AB, and their position.
- Exact mask byte lengths and id limits per version (AB artifacts 17 bytes).
- Predefined hero record layout, 19 artifact slots, u16 artifact ids.
- WoG (0x33) is parsed with the SoD layout; its extras are unknown.
- RoE/AB hero-count details (RoE 16-byte mask assumed).

## Not implemented
Terrain, objects, events. Errors raise `H3mError`.
