# Presenter geometry and timeline (`:presenter`)

Groundwork for `android-app.md` sections 4.1, 4.4 and 5.2 (milestones A4 and A7). Both pieces are
pure JVM, with no Android types, so the Compose screens stay thin.

## 1. BoardGeometry (`h3.presenter.BoardGeometry`)

- Board space is the spec's: cells 44 apart, rows 42 apart, shifted rows offset 22 to the right,
  first cell box at (14, 86). Hexes are pointy-top: a cell box is 44 wide and 56 tall (pointed ends),
  which tiles exactly with the 42 row pitch. The board bounding box is 770 x 476.
- Shifted rows: `row_offset == "odd"` shifts odd rows, otherwise even rows (the default). This
  agrees with `Hex.toAxial` and `Hex.neighbours`; a test derives every adjacency from the geometry.
- Screen = board * scale + offset; scale fits the bounding box into the viewport minus a margin,
  times zoom; pan adds to the centred offset. The margin is clamped to a quarter of the shorter side
  so tiny viewports stay valid. Width or height <= 0 is rejected.
- `hitTest(x, y): HexCell?` inverts the transform, considers the cells of the three nearest rows whose
  polygon contains the point (borders count), and returns the nearest centre; ties break by
  (row, col). Outside every polygon (including the jagged strips of the bounding box) it returns null.
- `hitTestUnit(x, y, units)` maps a tap on either cell of a living unit to `UnitHit(id, head)`.
- Float rule: pixel math is `Double`. Only `Int` cells leave this class towards the engine. No pixel,
  scale or float enters a command, state or hash (`android-app.md` section 2 rule 3).

## 2. Timeline (`h3.presenter.Timeline`)

- `build(before, events, prefs): List<Segment>`; `skip(events)`. Immutable inputs, data out, no
  clock, no `BattleCommand` in any signature (a reflection test checks it).
- Segments are strictly sequential: the first starts at 0, each starts at the previous end, so the
  list is sorted and cannot overlap; durations are non-negative `Int` milliseconds.
- Mapping: `Moved` gives one `MOVE_STEP` per path hex (start from the stack's position in `before`,
  tracked across several `Moved` events); melee `DamageDealt` gives ATTACK, HIT, DAMAGE_NUMBER; ranged
  gives SHOOT, PROJECTILE, HIT, DAMAGE_NUMBER (retaliation is a normal `DamageDealt`); `UnitDied`
  DEATH; `RoundStarted` ROUND_BANNER; `TurnStarted` TURN_PULSE; luck and morale events overlays;
  `BattleEnded` a zero-duration BATTLE_END. `Waited`, `Defended`, `BattleStarted` have no clip.
- Timing: frames per clip (`Timeline.Frames`) times the speed's frame time (100, 67, 33 ms;
  SKIP = 0). `SKIP` returns `skip(events)`: only the BATTLE_END hand-off, at 0.
- Test: for every step of the golden playouts, build and skip for all four speeds leave the state
  hash and the state value unchanged, are deterministic, well formed, bounded by `maxDurationMs`,
  and monotone in speed.

## 3. Ambiguities and decisions

1. 4.4 lists `(startMs, durationMs, kind, stack, group, from, to)`. `group` (CRANIM animation
   group) needs creature data (G3), so it is absent; the renderer derives it from `kind`.
2. 4.4 says input is the previous view; this takes the previous `BattleState` (the view is derived
   from it). The after-state is not needed: the events carry everything.
3. 4.4 says `UiTiming` lives in `:app`; the frame table is here so the builder is testable. `:app`
   may override it later.
4. Clips are sequential, not overlapping. Parallel clips (a damage number during the hit) are a
   later refinement; the display-model invariant (end == next view) is untouched.
5. The spec says tie-break "(row, col)" while `HexCell` orders by (col, row); geometry follows the spec.
6. 5.2 puts `BoardGeometry` in `:app`; here it is in `:presenter` (as asked) under `h3.presenter`.
   Petal and sprite-bounds priority (5.2 item 3) are not covered; they need `:app` sprite sizes.
