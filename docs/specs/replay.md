# Replay file format

Status: draft v1. Code: `tools/h3re/h3re/replay.py`, tests `tools/h3re/tests/test_replay.py`.
Related: ADR-0001 (state hash), `battle.md`, `battle-scenario.md`, `determinism-gate.md`.

A replay is a self-contained, canonical record of one battle: the scenario, the
seed and the full command log, pinned to the exact rule packs and to the final
state hash. Verifying replays the battle and checks everything.

## 1. Encoding

One JSON document: sorted keys, separators `,` and `:`, ASCII only
(`ensure_ascii`), no trailing newline. Values are integers, strings, booleans,
null, lists and objects. Floats, NaN and timestamps never appear. Recording the
same inputs gives identical bytes. A file that parses but is not in this exact
form is rejected (`Malformed`). Suggested extension: `.h3r`.

```
{"body": {"commands": [...], "scenario": {...}},
 "checksum": "<sha256 hex>",
 "header": {...}}
```

`checksum` is SHA-256 of the canonical encoding of `{"body":..., "header":...}`.

## 2. Header (all keys required, unknown keys rejected)

| key | meaning |
|---|---|
| `format_version` | integer, 1 |
| `kind` | `"battle"`. `"adventure"` is reserved for later saves; any other kind, and reserved ones for now, are `UnsupportedKind` |
| `seed` | master seed (integer) |
| `battle_id` | scenario battle id (names stream `battle:<id>`) |
| `scenario_hash` | SHA-256 of the canonical scenario JSON in the body |
| `command_count` | length of `body.commands` |
| `final_hash` | `battle.state_hash` of the state after the last command |
| `rules_hash` | `rules.RULES_HASH` |
| `policy_hash` | `battle.POLICY_HASH` |
| `creatures_hash` | `datapack.load_dir().content_hash` (the rules+creatures pack) |

## 3. Body

- `scenario`: the decoded scenario document (`battle-scenario.md`), stored whole so the
  file needs no external input. Key order is canonicalised.
- `commands`: the full command log, starting with `Begin`, in the bisect/soak encoding
  (`soak.encode_command`: `{"type": "Move", "stack": 1, "dest": [3, 4]}`). The log
  need not end the battle.

## 4. Verification order and errors

All are subclasses of `ReplayError` (a `ValueError`).

1. Decode: empty/cut data is `Truncated`; other garbage is `Malformed`.
2. `format_version` != 1: `UnsupportedVersion`.
3. Checksum: `Tampered`. (Checked before anything else about content, so a pack
   mismatch means a genuinely sealed file from another build.)
4. Structure/kind checks: `Malformed`, `UnsupportedKind`.
5. `MismatchedRulesPack`, `MismatchedPolicy`, `MismatchedCreatures`.
6. Replay: an illegal command or a final-hash mismatch is `Diverged`.

Truncation: every proper prefix of a valid file raises `Truncated`.

## 5. API and CLI

`record(scenario, commands, seed) -> bytes`, `verify(bytes) -> header`,
`load(bytes) -> (header, scenario, commands, final_state)`, `info(bytes) -> header`
(integrity checks, no replay or pack checks), `run_chooser(scenario, seed, chooser)`.

```
python3 -m h3re replay record SCENARIO.json --seed N [--chooser C] -o OUT.h3r
python3 -m h3re replay verify FILE      # exit 0, or 1 with one line "h3re: error: <ErrorName>: ..."
python3 -m h3re replay info FILE        # header, one "key: value" per line
```

## 6. Notes

- Golden check: the golden scenario with seed 12345 and the scripted chooser
  records and verifies with `final_hash` fbe9015b... (no re-pin).
- Version policy: any change to the layout bumps `format_version`; old versions are
  refused until a reader is added.
- `replay.py` is not a simulation module (it hashes, reads packs and encodes JSON), so it
  is not a banned-API lint target. It uses no clock, floats or unordered iteration.
