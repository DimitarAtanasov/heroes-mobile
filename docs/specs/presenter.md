# Battle presenter (`h3re.present`)

Status: draft v1. Reference: `tools/h3re/h3re/present.py`; tests:
`tools/h3re/tests/test_present.py`. Serves engine-design.md 1.5/1.6
(tap-to-preview, tap-again-to-confirm).

## 1. Contract

- `view(state) -> dict` is pure: it reads the state through the public battle
  API (`legal_commands`, `round_order`, `strike_preview`, `cells`), never
  touches an RNG, never mutates the state (the `state_hash` is unchanged) and
  is deterministic across calls.
- Output leaves are `int`, `bool`, `str`, `None`; no floats. `view_json(state)`
  is canonical JSON (`sort_keys`, separators `,` `:`).
- `view_version` (`VIEW_VERSION`, now 1) changes on any incompatible shape
  change.
- Not a simulation module. It is not a lint target today; it contains no floats,
  clocks, I/O or unordered iteration that reaches output, so adding
  `present.py` to the determinism lint targets is cheap and recommended.

## 2. Shape

- `phase`: `not_started` | `active` | `over`; `round`, `winner`, `active`
  (stack id or null), `bonus_turn`, `morale_pending`.
- `grid`: `width` 17, `height` 11, `rows[r][c]` = `{c, r, playable, obstacle,
  stack, part}` (`part` is `head`/`tail` for a living stack's cell).
- `stacks`: per stack `id, side, slot, creature, count, alive, top_hp,
  unit_hp, hp` (total), `speed, shots, shooter, double_wide, flyer,
  defending, morale, luck, active, pos, cells`.
- `queue`: `round_order` as `{stack, status}` with status `active` | `done` |
  `waited` | `pending`.
- `actions`: `global` (begin/wait/defend, `{command}`) and `by_hex`, sorted by
  hex. Each entry is `{hex, move, target}`: `move` is `{command}` or null;
  `target` (for a living enemy, keyed at its head hex) is `{stack, shoot,
  attacks}`, where `shoot` = `{command, preview}` and each attack =
  `{from_hex, command, preview}` (one per "petal"; `from_hex` is the stack's
  own position when it attacks without moving). `preview` =
  `{floor, expected, ceiling}` from `battle.strike_preview` (retaliation is not
  included).
- Commands are dicts: `{type: begin|wait|defend|move|shoot|attack, stack, dest|
  target|from_hex}`. Every command of `legal_commands` appears exactly once in
  `actions`.

## 3. Tap semantics

`candidate_commands(state, hex)` returns the real commands a tap can mean: all
Shoot/Attack commands on the enemy stack covering the hex (either cell of a
two-hex unit), or the Move to that hex. `candidate_actions(state, hex)` returns
the matching `by_hex` entry (with previews) or None. First tap: show path,
petals and `preview`; second tap on the same hex/petal sends the command.
