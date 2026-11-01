# HoMM3 .H3M map header (clean-room notes)

Implemented in `tools/h3re/h3re/h3m.py`. Files are gzip streams; little-endian.
Strings are u32 length + bytes (cp1252). Decompression is capped at 64 MiB.

## Header
| Field | Type |
|---|---|
| format | u32: 0x0E RoE, 0x15 AB, 0x1C SoD, 0x33 WoG |
| has hero | u8 |
| map size | u32 (square side) |
| two levels | u8 |
| name, description | strings |
| difficulty | u8 (0-4) |
| max hero level | u8, only if not RoE |

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

## Not implemented
Everything after teams (allowed heroes/artifacts/spells/skills, rumors, hero
data, terrain, objects, events). WoG (0x33) is parsed with SoD layout; its
extra header data is unverified. Layouts are from memory of community docs and
are verified only against synthetic fixtures. Errors raise `H3mError`.
