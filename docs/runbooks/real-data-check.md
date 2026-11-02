# Runbook: check the project against your own Heroes 3 files

Purpose: find out how the readers and the Android sprite loader behave on your legally owned game
files, and send back a result we can act on **without sending any game content** (laws 1 and 9 in
`CLAUDE.md`). Nothing is copied, changed or uploaded by these steps. Estimated time: 5 minutes.

You need Python 3.13 and a checkout of this repository. No other packages.

## 1. Point the tools at your game folder

`DATA_DIR` is the folder that contains `Data/` (with `H3sprite.lod`, `H3bitmap.lod`, ...) and
`Maps/`. Names may be in any letter case. Use the real path of your install.

| System | Command (in the shell you will use for steps 2 and 3) |
|---|---|
| Linux, macOS | `export H3_DATA_DIR="/path/to/HoMM3"` |
| Windows PowerShell | `$env:H3_DATA_DIR = "C:\Games\HoMM3"` |
| Windows cmd | `set H3_DATA_DIR=C:\Games\HoMM3` |

On Windows use `py -3` or `python` where the commands below say `python3`.

## 2. Run the real-file tests (optional, local only)

From the repository root:

```
python3 -m unittest -v tools/h3re/tests/test_real_files.py tools/h3re/tests/test_content.py tools/h3re/tests/test_h3m.py
```

Without `H3_DATA_DIR` the real-file tests print `skipped`; with it they run against your files. The
tests that matter are `RealLodTests`, `RealMapTests`, `RealCrtraitsTest` and `RealMapObjectTests`. The
last lines read `OK (skipped=N)` or `FAILED (failures=N, ...)`.

Do not send this output. Failure messages can contain file and member names and a short piece of a
parse error. Send step 3 only. If you want, tell us the single result line in your own words
(for example "FAILED (failures=2)").

## 3. Make the report

From the repository root:

```
cd tools/h3re
python3 -m h3re real-report "$H3_DATA_DIR" --out ../../report.json
```

(PowerShell: `python3 -m h3re real-report "$env:H3_DATA_DIR" --out ..\..\report.json`;
cmd: `python -m h3re real-report "%H3_DATA_DIR%" --out ..\..\report.json`.)

It reads the folder only, never writes anything but `report.json`, and refuses to write the report
inside your game folder. It prints one line such as
`wrote ../../report.json: 14 archive(s), 40 map(s); findings: SPRITE_NO_IDLE`.
Exit status 0 means a report was written. It always finishes, even on damaged files: failures are
recorded in the report. Option `--sample N` (default 5) sets how many files of each kind per archive
are decoded; leave it alone first.

Open `report.json` in a text editor before sending it. It is plain JSON and you can read all of it.

### What the report contains, and nothing else

* the report version, the h3re version, the Python version and your OS family (`linux`, `win32`, `darwin`);
* the file names of your `*.lod` and `*.h3m` files relative to the folder you gave (unusual
  characters become `?`), their sizes in bytes and the number of entries in each archive;
* per archive and per kind (DEF, PCX, TXT): how many members exist, how many were decoded, how many
  worked, how many failed, and the **names of the exception types** (for example `DefError`);
* per map: whether the header and the object section parse, the map format name (RoE, AB, SoD, ...),
  the map size and number of levels, the exception type, a short reason code, and the reader's fixed
  stage label; for an unsupported object only its numeric class id and subid;
* for the sprite loader: which of `H3sprite.lod` and `H3ab_spr.lod` exist and open, and for the
  three DEF names it asks for (`CPKMAN.DEF`, `CLCBOW.DEF`, `CGRIFF.DEF`): found where, decodes,
  and has an idle frame (group 2, frame 0).

It contains no file contents, no pixels, no text from TXT or map files, no map names or
descriptions, no other member names, no hashes and no folder path of yours. If a map file name is
personal, replace it with anything (`m1`) in the editor; the rest of the file does not depend on it.

## 4. What to send back

Send **only `report.json`**, in a message or as an attachment. Do not send the game files,
extracted files, screenshots of the game, or the step 2 output.

## 5. What we do with each result

The report ends with a `findings` list of fixed codes. Each code, and what happens next:

| Finding | Meaning | What we do |
|---|---|---|
| `DATA_DIR_INVALID` | The folder you gave is not a directory. | Nothing; check the path in step 1 and rerun. |
| `NO_LOD_FOUND` | No `*.lod` within 6 folder levels. | Ask where your install keeps `Data/`; the tools expect `Data/*.lod`. |
| `NO_MAPS_FOUND` | No `*.h3m` under a folder named `Maps`. | Same; map tests stay skipped until a `Maps` folder is given. |
| `SCAN_TRUNCATED` | More than 200 LODs or 100 maps; only the first sorted ones were read. | Raise the caps in `real_report.py` if the missing ones matter. |
| `LOD_OPEN_FAILED` | An archive does not open (`error_type` says why). | Compare size and entry count with `docs/specs/lod.md`; fix the reader if the format differs (spec first, ADR if it changes). An archive from an edition we have not seen is documented, not guessed. |
| `DEF_DECODE_FAILED` | Some DEFs do not decode (`DefError` and count). | Ask for the numbers only (frame format, error stage) via a new report field; fix `defimg.py` per `docs/specs/def.md`, add a synthetic fixture for the case. |
| `PCX_DECODE_FAILED` | Some PCX do not decode. | Same path with `pcx.py` and `docs/specs/pcx.md`. |
| `TXT_PARSE_FAILED` | Some TXT do not parse (`TxtError`: size cap, encoding, line cap). | Decide per `docs/specs/txt.md`: encoding or cap change, or a per-file option. |
| `MAP_UNSUPPORTED_FORMAT` | A map is in a format the parser rejects on purpose (for example HotA, format id 0x20). | No bug. Counted; supporting it is a separate decision recorded in an ADR. |
| `MAP_HEADER_FAILED` | A map header fails (`reason` and `stage` say where). | Real defect or a variant we do not know: write a synthetic fixture for that stage, fix `h3m.py` per `docs/specs/h3m.md`. |
| `MAP_OBJECTS_FAILED` | The header parses but the object section fails. For `unsupported_object` the class id and subid are the object we have not implemented. | Add the object body to the parser from `docs/specs/` with a synthetic test; the most frequent class ids go first. |
| `SPRITE_LOD_MISSING` | `H3sprite.lod` or `H3ab_spr.lod` was not found where the Android loader looks (`Data/`, then the folder itself). Check `sprites.layout`: `nested` means they exist deeper. | If `nested`: fix the import step to copy `Data/` to the right place. If `absent`: ask which archive holds the creature sprites in your edition. |
| `SPRITE_LOD_BAD` | A sprite archive exists but does not open. | Treated like `LOD_OPEN_FAILED`. |
| `SPRITE_DEF_MISSING` | A DEF name in `SpriteLoadPlan.DEFAULT_TABLE` is in neither archive. The three names are unverified stand-ins (see the comment in that file). | Replace the names in the table with the correct ones (Kotlin change by the app owner, with its test); better, key by `CRTRAITS.TXT` row. We would ask you for the DEF file names of three creatures by name only. |
| `SPRITE_DEF_BAD` | The DEF is found but does not decode. | Same path as `DEF_DECODE_FAILED`. |
| `SPRITE_NO_IDLE` | The DEF decodes but block 2 (idle) is missing or its first frame is empty. | The "group 2 is idle" rule in `android-app.md` 4.3 is wrong for this DEF; we correct the spec first, then the loader. |

An empty `findings` list means everything we check works on your files; tell us that too. A finding
never changes a golden hash or any simulation behaviour: these readers are not part of the
simulation. Any fix goes through the usual rules (a failing synthetic test first, full suite, no game data
in the repo).

## Privacy checklist before sending

* The file is `report.json` and you opened it.
* It has no line that looks like prose, a map title or a path to your computer.
* You are sending nothing else.
