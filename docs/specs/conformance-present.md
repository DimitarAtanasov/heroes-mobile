# Conformance: presenter view v2 (`h3.sim.Present`)

Status: draft. Companion to `conformance.md` (not edited by this change; the orchestrator folds
this in). Python (`tools/h3re/h3re/present.py`) is authoritative (ADR-0004); the vectors are
`android/sim/src/test/resources/vectors/present.json`, written by
`h3re/vectors_present.py` (`generate()`; wire it into `vectors.generate()`), never by hand
(ADR-0007).

## What is pinned

- `Present.view(state)` and `Present.viewJson(state)`: the canonical JSON text (sorted keys,
  no spaces, ASCII) must be byte-identical to Python `view_json`. Every recorded state carries
  `view_sha256`; every 9th state (and the first and last of each case) also carries the full
  `view_json` text. (Texts for all states would make the file tens of megabytes.)
- `Present.candidateCommands(state, hex)` and `candidateActions(state, hex)`: for every 4th
  state (and the last), each hex with candidates lists the command dicts in `legal_commands`
  order and the SHA-256 of the canonical `candidate_actions` entry. Kotlin checks all 187 hexes:
  unlisted hexes must give an empty list and `null`.
- The state hash (`stateHash`) is unchanged by building a view; the state value is unchanged.
  `Present` takes no stream, so it cannot draw from an RNG.

## States

States are not repeated in `present.json`: an entry refers to `(case name, index)` of
`battle_states.json` (index 0 = initial state, i+1 = state after step i) and carries
`state_sha256`, which Kotlin compares with the hash of the state it loaded. The cases are the
`vectors_battle` playouts: default and non-default policies (alt-order, vcmi-like, strict, and
the mix policies, including `row_offset: "odd"`), two-hex units, flyers, shooters, ability and
tie armies. Randomness only from `Pcg32` / `derive_stream`.

## Semantics fixed by the port

- Lists keep Python order (legal-command order, `by_hex` sorted by (col, row), attacks in legal
  order); map key order does not matter (canonical text sorts keys).
- Move paths come from `Hex.reach` with the active stack excluded from the occupancy, the same
  as `Battle` (BFS discovery order, first discovery wins; flyers: the destination alone).
- Kill counts use `Battle.applyDamage` on the target's count, top HP and unit HP (0 for an
  empty target).
