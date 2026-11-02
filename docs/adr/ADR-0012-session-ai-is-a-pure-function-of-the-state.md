# ADR-0012: The session AI is a pure function of the state

Status: proposed (2026-11-01). The owner accepts or amends it. Refines ADR-0011 D7 and records two
decisions about `:presenter` (`docs/specs/presenter-kotlin.md`).

## Context

The determinism audit of `:presenter` (2026-11-01) reproduced these problems in `BattleSession`:

- It drove the AI with the stateful `BattleAi.GreedyAi`, which keeps a defend counter per side
  and `ai:<side>` tie-break streams outside the command log. Its queue also handled pending
  submissions before it played a due AI turn. As a result the final hash depended on when
  submissions arrived (a holding executor and a direct executor differed in 31 of 40 replays), and
  a game resumed from its log could not reproduce the uninterrupted game. `android-app.md` 7.1 says
  the AI is a pure function of the state and a replay never re-runs the AI.
- The stalemate cap defaulted to `Int.MAX_VALUE`, counted human commands, and showed up as
  `NotYourTurn` when it was hit.

## Decision

- **D1, stateless AI.** The session takes a `BattleAi` and calls `BattleAi.choose(state)`. That
  call seeds its tie-break stream from the state hash and decides from the state alone. The
  stateful `GreedyAi` stays in `:sim` for the recorded conformance games, and the session does not
  use it. Per-state parity of `choose` with Python is pinned by `BattleAiTest` in `:sim`.
- **D2, AI before the queue.** When an AI side is to move, the session plays it before it reads the
  next queued submission. The log then depends only on the state and on the human commands
  accepted, not on when they were queued.
- **D3, resume is `loadLog`.** `loadLog(entries)` applies a recorded log in one atomic step on an
  empty session, with the AI off. It checks that every entry has the right seq and that the engine
  accepts it. If any entry fails, the session is unchanged. The AI takes over after the load.
- **D4, explicit stalemate cap.** `maxAiCommands` is a required parameter and counts AI commands
  only. When the cap is reached on an AI turn, `isStalled()` is true and submissions get `Stalled`.
- **D5, failures are results.** If the engine or the AI throws anything but `IllegalCommand`, the
  session publishes a terminal snapshot with `fault` set and answers every later submission with
  `Faulted`. Exceptions from listeners, autosave and replies (checked ones included) are counted
  and skipped. Every submission gets exactly one reply, `ShutDown` if the worker refuses the task.
- **D6, long-press.** `TapEvent.LongPress` returns the current UI state unchanged, as 5.1 says. The
  creature card is the app's concern. One documented deviation from 5.1 remains: a tap on a
  non-actionable hex while previewing is a no-op, not a return to Idle (only `Cancel` goes to Idle).
  We revisit this when the app is wired.

## Behaviour change

The 64 recorded AI games of `battle_ai.json` were played by the stateful AI. A session no longer
reproduces their recorded final hashes, and its test no longer compares them. It compares every
session with a plain `Battle.apply` loop that uses the same stateless chooser, for all 64 initial
states. No golden hash pinned in `:sim` or Python changes, and no vector changes. The AI picks
moves differently in long defend stalls: `choose` defends until round `STATELESS_DEFEND_ROUND`,
where `GreedyAi` stopped after `MAX_DEFENDS` defends in a row.

## Consequences

- Holding and direct executors give the same game for the same human submissions, and a resumed
  game equals the uninterrupted one (both are tested in `BattleSessionTest`).
- An AI change still cannot break old saves, because AI commands are in the log and `loadLog`
  never runs the AI.
- Constructor callers must pass `maxAiCommands`. `:app` does not construct a session yet.
