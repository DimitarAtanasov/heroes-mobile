# heroes-mobile

Clean-room, data-driven reimplementation tooling inspired by Heroes of Might and Magic 3.

The tools load the user's own legally owned game files at runtime. No original
assets or code are committed to this repository. This project is not affiliated
with or endorsed by the rights holders of Heroes of Might and Magic 3.

## Layout

- `tools/h3re/` - Python package with readers for LOD archives, DEF sprites and H3M maps, plus rules code and tests.
- `tools/h3re/tests/` - unit tests built on synthetic fixtures (no game files needed).
- `docs/specs/` - format and design specs written from public documentation and observed mechanics.
- `docs/checkpoints/GRAPH.md` - reverse-engineering workflow graph and checkpoint log.
- `.github/workflows/test.yml` - CI running the test suite on push and pull request.

## Running tests

Requires Python 3.13. From the repository root:

```sh
python3 -m unittest discover -s tools/h3re/tests
```

## CLI usage

```sh
cd tools/h3re && python3 -m h3re <lod-list|lod-extract|def-to-png|h3m-info>
```

## Status and limitations

- Early stage. Implemented:
  - LOD archive reader (list, extract, lazy access).
  - DEF sprite reader, hardened against malformed input.
  - H3M reader from the header through the post-teams sections. Terrain is parsed; objects are not yet parsed.
  - PCX and TXT table readers.
  - PCG32 deterministic RNG.
  - Battle damage rules.
  - Battle core (`h3re.battle`): hex grid, turn queue, movement, melee/ranged attacks, morale/luck, deterministic replay (spec: `docs/specs/battle.md`).
  - CLI (`lod-list`, `lod-extract`, `def-to-png`, `h3m-info`).
- All formats are verified only against synthetic fixtures. None has been checked against real game files.
- Engine design is in `docs/specs/engine-design.md`; progress is logged in `docs/checkpoints/GRAPH.md`.
