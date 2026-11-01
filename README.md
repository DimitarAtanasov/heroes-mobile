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

- Early stage; the CLI is still being written.
- File format readers are unverified against real game files. Tests use synthetic data only.
- The H3M parser stops after the teams section and is not yet verified.
- Combat/economy rules and engine design are in progress (checkpoint 3 in `docs/checkpoints/GRAPH.md`).
