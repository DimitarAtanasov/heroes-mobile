# Battle presenter (`h3re.present`)

Status: draft v2 (view_version 2; v2 closes android-app.md gap G1). Reference: `tools/h3re/h3re/present.py`; tests:
`tools/h3re/tests/test_present.py`. Serves engine-design.md 1.5/1.6
(tap-to-preview, tap-again-to-confirm).

## 1. Contract

- `view(state) -> dict` is pure: it reads the state through the public battle
  API (`legal_commands`, `round_order`, `strike_preview`, `cells`), never
  touches an RNG, never mutates the state (the `state_hash` is unchanged) and
  is deterministic across calls.
- Output leaves are `int`, `bool`, `str`, `None`; no floats. `view_json(state)`
  is canonical JSON (`sort_keys`, separators `,` `:`).
- `view_version` (`VIEW_VERSION`, now 2) changes on any incompatible shape
  change.
- Not a simulation module. It is not a lint target today; it contains no floats,
  clocks, I/O or unordered iteration that reaches output, so adding
  `present.py` to the determinism lint targets is cheap and recommended.

## 2. Shape

- `phase`: `not_started` | `active` | `over`; `round`, `winner`, `active`
  (stack id or null), `bonus_turn`, `morale_pending`.
- `grid`: `width` 17, `height` 11, `rows[r][c]` = `{c, r, playable, obstacle,
  stack, part}` (`part` is `head`/`tail` for a living stack's cell). v2 adds
  `row_offset` (`"even"` | `"odd"`, the policy's row parity: which rows are
  shifted half a cell right; the board never hard-codes it) and
  `edge_columns_walkable` (the policy flag behind `playable`).
- `stacks`: per stack `id, side, slot, creature, count, alive, top_hp,
  unit_hp, hp` (total), `speed, shots, shooter, double_wide, flyer,
  defending, morale, luck, active, pos, cells`. v2 adds, for the info card:
  `attack` and `defense` (creature value plus the side's hero skill, before the
  defend bonus), `defend_bonus` (the `battle.defend_bonus` value while the stack
  is defending, else 0), `dmg_min`, `dmg_max` (per creature), `retaliations`
  (left this round) and the flags `strikes_twice`, `shoots_twice`,
  `no_enemy_retaliation`, `unlimited_retaliation`.
- `queue`: `round_order` as `{stack, status}` with status `active` | `done` |
  `waited` | `pending`.
- `actions`: `global` (begin/wait/defend, `{command}`) and `by_hex`, sorted by
  hex. Each entry is `{hex, move, target}`: `move` is `{command, path}` or null, where `path` (v2) is the list of hexes the stack
  walks, start excluded and the destination last (`battle._reach`; a flyer's path
  is the destination alone);
  `target` (for a living enemy, keyed at its head hex) is `{stack, shoot,
  attacks}`, where `shoot` = `{command, preview}` and each attack =
  `{from_hex, command, path, preview}` (one per "petal"; `from_hex` is the stack's
  own position when it attacks without moving, and then `path` is `[]`; otherwise
  `path` is the move path to `from_hex`). `preview` = `{floor, expected, ceiling,
  kills}` from `battle.strike_preview` (retaliation is not included); v2 `kills`
  = `{floor, expected, ceiling}`, the number of target creatures killed by each
  damage value (`rules.apply_damage` on the target's count and top HP; the damage
  range itself is `rules.damage_range`'s floor and ceiling).
- Commands are dicts: `{type: begin|wait|defend|move|shoot|attack, stack, dest|
  target|from_hex}`. Every command of `legal_commands` appears exactly once in
  `actions`.

## 3. Tap semantics

`candidate_commands(state, hex)` returns the real commands a tap can mean: all
Shoot/Attack commands on the enemy stack covering the hex (either cell of a
two-hex unit), or the Move to that hex. `candidate_actions(state, hex)` returns
the matching `by_hex` entry (with previews) or None. First tap: show path,
petals and `preview`; second tap on the same hex/petal sends the command.

## 4. v2 notes

- v2 changes the view only: no state, command, event or hash changes (the state
  hash is unchanged by building a view; `test_present` and `PresentTest` pin it).
- Everything v2 adds is an `int`, `bool`, `str`, list or dict; no RNG use.
- The Kotlin port is `h3.sim.Present` (`view`, `viewJson`, `candidateCommands`,
  `candidateActions`); `viewJson` is byte-identical to `view_json` and pinned by
  `present.json` (see `conformance-present.md`).
- Not provided (not needed by android-app.md G1): per-hex info for long-press,
  and retaliation damage in previews.
