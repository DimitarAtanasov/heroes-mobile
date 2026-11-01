# Spec: `:presenter` (Kotlin, pure JVM)

Status: implemented (milestones A2/A4 slice). Source of truth for behaviour: `android-app.md`
sections 2, 5.1, 7.1, ADR-0011 D1/D2/D7 and ADR-0012. Code: `android/presenter/src/main/kotlin/h3/presenter/`.

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
- Tap on the previewed hex: `Confirmed(selected command)`, only if that command is still one of
  the hex's candidates in the given state (so a previewed attack whose target moved away is not
  confirmed, even though it is still legal); otherwise the preview is rebuilt from that state.
- Tap on another legal hex re-targets. `LongPress` returns the current state unchanged (5.1: a
  long-press never changes the preview state; the app shows the card). `Select(i)` picks among
  several candidates (attack from different hexes). Default selection: Shoot, else the Attack
  without moving, else the first. The no-op tap while previewing stays a recorded deviation
  (ADR-0012 D6).
- `Confirmed` is terminal; any event after it behaves as from `Idle`. The 150 ms confirm guard
  of 5.1 belongs to the app (it needs a clock); the reducer has none.

## 3. `BattleSession` (android-app.md 7.1, ADR-0012)

`BattleSession(battle, codec, ai: BattleAi?, initial, masterSeed, humanSides, worker, maxAiCommands, autosave = null)`.

- Stream: `RngStreams.derive(masterSeed, "battle:" + battleId)`, as `battle_rng`. The state is
  the fold of `Battle.apply` over the log, so any executor, listener or timing gives the same hash.
- AI: `BattleAi.choose(state)`, a pure function of the state (no counters or streams outside the
  log). When an AI side is to move the session plays it before reading the queue, so the log does
  not depend on when submissions arrive. `ai = null` means no AI: non-human sides are then driven by
  `Ai` or `Replay` submissions. `humanSides` is copied.
- Queue: `submit(expectedSeq, command, origin, reply)`. FIFO; judged when dequeued. Every submit
  gets exactly one reply: `Accepted(snapshot)`, `Stale` (expectedSeq != log size; also rejects
  duplicates), `Illegal` (engine `IllegalCommand`, no draw), `NotYourTurn` (a Human-origin command
  while the active stack is on a non-human side, or before `Begin`), `Over`, `Stalled`,
  `Faulted(reason)`, or `ShutDown` (on the caller, when the worker refuses the task).
- `start()` queues `Begin` (origin Session) if the initial state has not started; then the AI plays.
- Stalemate guard: `maxAiCommands` (required) counts AI commands only. When it is used up on an AI
  turn, `isStalled()` is true and submissions get `Stalled`.
- Resume: `loadLog(entries, reply)` on an empty session (before `start`) applies a recorded log
  atomically with the AI off. Each entry must have seq = its index and be accepted by the engine;
  on a failure the session is unchanged and the reply is `Illegal("step i: ...")`. A non-empty
  session answers `Stale`. On success listeners get one snapshot (the end state), and autosave is
  not called.
- `Snapshot(seq, state, stateHash, command, origin, events, fault)`: immutable; `view()` builds the
  presenter view on demand. Published to listeners in registration order, after `AutosaveSink`.
  A throwing listener, autosave or reply (any `Exception`, checked ones included) is counted
  (`listenerFailures`, `autosaveFailures`) and skipped.
- Faults: if the engine or the AI throws anything but `IllegalCommand`, the session publishes one
  terminal snapshot with `fault` set (state of the last accepted command), `fault()` returns the
  reason, and every later submission gets `Faulted`.
- Locking: one drain loop runs at a time, and the lock guards only that flag. Apply, autosave,
  listeners and replies run outside it. `log()` returns an immutable list published after each
  command and never blocks.
- `AutosaveSink.onCommand(entry, snapshot)` is the only persistence hook; the app writes files.
- Threads: `BattleSession.newWorker()` gives a daemon thread `h3-sim`; tests pass a direct or a
  holding executor. Re-entrant submits from a listener are queued, not recursed.
- `finalHash()`: state hash of the newest snapshot.

## 4. Tests (`android/presenter/src/test/kotlin/h3/presenter/`)

Vectors and `MiniJson` are read from `:sim`'s test output (nothing copied).
`TapReducerTest` (transitions, two-hex targets, no-ops, legality, a target that moved away,
stale previews for moves, attacks and shoots, long-press, determinism). Each scenario test asserts
that its scenario was found.
`BattleSessionTest` (all 64 recorded initial states: session equals a plain apply loop with the
stateless chooser; holding equals direct executor; resume via `loadLog` equals the uninterrupted
game; `loadLog` atomicity; stale/duplicate/illegal/wrong-turn rejection; stalemate cap; faults;
failing listeners, autosave and replies; no deadlock from `log()`; snapshot immutability;
listener order; threaded equals direct; many submitters; shutdown; the named stream).

## 5. Not yet here

Animation timeline builder (4.4), replay-file autosave format (7.2), Kotlin pack loading.
