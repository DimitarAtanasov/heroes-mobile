# Spec: `:presenter` (Kotlin, pure JVM)

Status: implemented (milestones A2/A4 slice). Source of truth for behaviour: `android-app.md`
sections 2, 5.1, 7.1 and ADR-0011 D1/D2/D7. Code: `android/presenter/src/main/kotlin/h3/presenter/`.

## 1. Scope

A plain JVM module between `:sim` and the Android UI. It depends only on `:sim` and the Kotlin
stdlib. No Android types, no file I/O, no floats in anything that feeds the engine. Threads exist
only as the injected worker `Executor`. The Kotlin banned-API lint scans `android/sim` only.

## 2. `TapReducer` (android-app.md 5.1)

`TapReducer(battle).reduce(ui: TapState, event: TapEvent, state: BattleState): TapState`, pure.

- States: `Idle`, `Previewing(hex, candidates, selected)`, `Confirmed(command)`.
- Events: `Tap(hex)`, `LongPress(hex)`, `Select(i)`, `Cancel`.
- Candidates come from `Present.candidateCommands` (in `legalCommands` order) with damage
  previews from `Present.candidateActions`. The reducer never builds a command from parts.
- Tap on a hex with no candidate: no-op (the state object is returned unchanged).
  Deviation from 5.1, decided by the task brief: 5.1 sends a non-actionable tap in a preview to
  Idle; here only `Cancel` does. Revisit when the app is wired.
- Tap on a legal hex or target: `Previewing`. `hex` is canonical: the destination of a move, or
  the head cell of the target stack, so both cells of a two-hex unit give the same preview.
- Tap on the previewed hex: `Confirmed(selected command)`, only if that command is still in
  `legalCommands(state)`; otherwise the preview is rebuilt from the current state.
- Tap on another legal hex re-targets. `LongPress` previews and never confirms. `Select(i)`
  picks among several candidates (attack from different hexes). Default selection: Shoot, else
  the Attack without moving, else the first.
- `Confirmed` is terminal; any event after it behaves as from `Idle`. The 150 ms confirm guard
  of 5.1 belongs to the app (it needs a clock); the reducer has none.

## 3. `BattleSession` (android-app.md 7.1)

`BattleSession(battle, codec, ai: BattleAi.GreedyAi, initial, masterSeed, humanSides, worker, autosave, maxAiCommands)`.

- Stream: `RngStreams.derive(masterSeed, "battle:" + battleId)`, as `battle_rng`. The state is
  the fold of `Battle.apply` over the log, so any executor, listener or timing gives the same hash.
- Queue: `submit(expectedSeq, command, origin, reply)`. FIFO; judged when dequeued. Results:
  `Accepted(snapshot)`, `Stale` (expectedSeq != log size; also rejects duplicates), `Illegal`
  (engine `IllegalCommand`, no draw), `NotYourTurn` (a Human-origin command while the active
  stack is on an AI side, or before `Begin`), `Over`.
- `start()` queues `Begin` (origin Session) if needed, then the session plays AI sides after
  every accepted command until a human side, the end, or `maxAiCommands` is reached. AI commands
  are logged with origin Ai. One `GreedyAi` serves all AI sides (it tracks defends per side).
- `Snapshot(seq, state, stateHash, command, origin, events)`: immutable; `view()` builds the
  presenter view on demand. Published to listeners in registration order, after `AutosaveSink`.
  A throwing listener is counted in `listenerFailures` and skipped.
- `AutosaveSink.onCommand(entry, snapshot)` is the only persistence hook; the app writes files.
- Threads: `BattleSession.newWorker()` gives a daemon thread `h3-sim`; tests pass a direct
  executor. Re-entrant submits from a listener are queued, not recursed.
- `finalHash()`: state hash of the newest snapshot.

## 4. Tests (`android/presenter/src/test/kotlin/h3/presenter/`)

Vectors and `MiniJson` are read from `:sim`'s test output (nothing copied).
`TapReducerTest` (transitions, two-hex targets, no-ops, legality, determinism);
`BattleSessionTest` (all 64 recorded AI games equal a plain apply loop, and the Python hash for
the 40+ non-perturbed ones; stale/duplicate/illegal/wrong-turn rejection; human/AI alternation;
snapshot immutability; listener order; threaded equals direct).

## 5. Not yet here

Animation timeline builder (4.4), replay-file autosave format (7.2), Kotlin pack loading.
