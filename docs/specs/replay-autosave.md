# Replay autosave and resume

Status: draft. Code: `android/presenter/.../ReplayAutosave.kt`, tests `ReplayAutosaveTest.kt`.
Related: `android-app.md` 7.2, `replay.md`, `BattleSession` (`AutosaveSink`, `loadLog`).

A save is a replay file (format v1, kind `battle`). There is no second format. The presenter
module does no file I/O; the app supplies a `ByteSink`.

## 1. Autosave

`ReplayAutosave(scenarioJson, seed, packs, sink, initialCommands = [])` is an `AutosaveSink`.
After every accepted command it appends the command to its own list, calls `Replay.record` on the
whole list and gives the bytes to `sink.write`. The file therefore always holds the full log, the
pack hashes in the header and the checksum, and equals what Python records for the same commands.

- `ByteSink.write(bytes)` receives a complete file. The app implements it as temp file, fsync,
  atomic rename (7.2) and may coalesce so the newest wins. It may throw.
- Nothing escapes `onCommand`: any `Exception` from record or sink is counted in `failures`
  (`lastError` keeps the text). The next command records the whole log again, so one failed write
  loses nothing once a later write succeeds. `BattleSession.autosaveFailures` stays 0.
- An entry whose `seq` is not the next index is a gap: counted as a failure, not recorded.
- Cost: `Replay.record` replays the commands to get `final_hash`, so a write is O(n) engine steps
  and a game is O(n^2) in total. Battles are tens to low hundreds of commands; the work runs on the
  session worker. If it shows up in profiles, the fix is a `record` variant in `:sim` that takes the
  known state, not a second format.
- A resumed session builds its autosave with `ReplayAutosave.resuming(resumed, seed, packs, sink)`
  (`loadLog` does not call autosave).

## 2. Resume

`ReplayResume.load(bytes, packs)` returns `ResumeResult`, never throws:

- `Ok(Resumed(scenarioJson, seed, commands, finalHash))`: checksum, packs, replay and `final_hash`
  verified (`Replay.load`). `scenarioJson` is the canonical scenario text.
- `Failed(error, message)` with `error` one of `Malformed, Truncated, Tampered, UnsupportedVersion,
  UnsupportedKind, MismatchedRulesPack, MismatchedPolicy, MismatchedCreatures, Diverged`
  (`replay.md` section 4, same order), or `Unreadable` for any unexpected exception.
  The app keeps the file and shows the reason (7.2); it never deletes it.

`ReplayResume.into(session, resumed, reply)` calls `BattleSession.loadLog` with entries
`(i, command, Origin.Replay)`: all commands or none, AI off while loading, one snapshot, no
autosave. The session must be fresh and built from `Scenario.parse(resumed.scenarioJson, packs)`
and `resumed.seed`; call `into` instead of `start()`. The AI then moves if an AI side is to move.

Known limits: a replay stores no origins, so every resumed entry is `Replay` and the AI command
cap (stall guard) restarts at zero. If the session was built with another seed or scenario, the
commands are most likely refused (`Illegal`) but this is not checked.

## 3. Acceptance

`ReplayAutosaveTest` on the `replay.json` scenarios (12: golden and soak) in three modes
(scripted humans, AI vs AI, human vs AI):

1. Every write equals `Replay.record` of the log so far; scripted games equal the Python bytes.
2. Resume in a fresh session gives the same state hash and command log.
3. A crash after command k (bytes of write k) resumes to the state after k, and the same
   configuration continues to the original final hash, log and file bytes.
4. Every proper prefix is `Truncated`; byte flips are named failures (mostly `Tampered`); resealed
   files give `Diverged`, `UnsupportedVersion`, `UnsupportedKind`.
5. Another rules, policy or creatures pack gives the matching `Mismatched*`.
6. A sink that always throws, throws `IllegalStateException`, or fails two calls in three never
   stops the game or changes its result; a gap or an unrecordable scenario is counted.
