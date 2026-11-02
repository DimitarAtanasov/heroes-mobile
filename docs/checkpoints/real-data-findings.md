# Findings on real game files (structure only, no content)

Source: files the owner supplied from their own Heroes III Complete + HotA install (Wine prefix layout,
`...\game\prefix\drive_c\game\Data`). Nothing from them is in the repo (Laws 1 and 9); only counts and
facts about format are recorded here.

## 2026-11-02: first contact (H3ab_spr.lod, H3ab_ahd.snd, H3ab_ahd.vid, two hd_*.p32 files)
- `H3ab_spr.lod` opens: 569 entries, 347 DEF, 222 other, no PCX or TXT members. `real-report` ran and
  wrote a report (findings: NO_MAPS_FOUND, SPRITE_LOD_MISSING because `H3sprite.lod` was not supplied,
  SPRITE_DEF_MISSING for the three placeholder DEF names, which live in the base archive).
- **All 347 DEFs decode** with `defimg.parse_def` (0 failures). The DEF reader is confirmed on real data.
- DEF group counts: 320 have 1 group (map objects), 27 have 5 to 21 groups (creature-like animations).
  **All 27 multi-group DEFs have a non-empty frame 0 in group 2**, so the "group 2 is idle" rule of
  `android-app.md` 4.3 holds for this archive. The base archive is still unchecked.
- DEF member names are mixed-case in the archive (for example `CHalf.def`, `Cboar.def`, `CADRGN.def`),
  so case-insensitive matching is required (it is).
- `hd_*.p32` files (magic `P32F`) are HD-style images, a format the project does not read. Their
  presence says the install carries HD/HotA-era assets. Decision still open: editions (G5, spec 3.3).
- `H3ab_ahd.snd` and `H3ab_ahd.vid` are audio and video index files; audio and video are out of scope.

## Still needed to proceed with 0.2
`H3sprite.lod` (base creature DEFs and battle sprites), `H3bitmap.lod` (contains `CRTRAITS.TXT`),
`H3ab_bmp.lod`, and optionally a few `.h3m` maps. Best path: run `real-report` locally and send only
`report.json`. `VIDEO.VID` (about 600 MB) is not needed.
