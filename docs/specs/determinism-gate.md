# Determinism gate

Ported (ideas only) from the Forge fuzz soak, divergence bisector and banned-API
lint. The simulation core (`battle`, `adventure`, `rules`, `rng`) must be a pure,
integer-only function of (initial state, command log, seed). Three tools guard it.

## 1. Soak (`tools/h3re/h3re/soak.py`)

`python3 -m h3re.soak --games N [--seed-base S] [--max-steps M] [--kind battle|adventure] [-q]`
(run from `tools/h3re`). For each of N seeds and each kind:

- A scenario is built purely from the seed (random creatures, obstacles, heroes;
  random grid, roads, armies, pools).
- Battles are driven by `battle_ai.GreedyAI` (both sides); adventures by a seeded
  random script of `Move` / `EndTurn` (capped at M commands).
- Checks, comparing `state_hash` and the event repr after every step:
  1. a second live run equals the first;
  2. replaying the recorded command log twice equals the live run;
  3. snapshot-and-resume: at the midpoint state and RNG (`state`, `inc`) are pickled,
     restored, and the remaining commands must reproduce the trace; the restored
     state must have the same canonical form.
- Exit status 1 and a `FAIL <kind> seed N: ... diverges at step K` line on failure.

Trace digest and policy matrix:

- Every run ends with `DIGEST <hex>`: SHA-256 over the per-run digests, each a
  SHA-256 over the length-prefixed per-step (state hash, events repr) of the live
  run. `--digest-out F` writes it; `--expect-digest-file F` exits 1 on a mismatch.
- `--policy-matrix` repeats every seed under `soak.POLICY_MATRIX` (default plus
  three non-default `BattlePolicy` / `AdventurePolicy` combinations), threading the
  policy through scenario build, live runs, replay and snapshot-resume. Adding or
  editing matrix entries changes the digest but is not a golden re-pin (the digest is
  only ever compared between two runs of the same code).
- CI runs the matrix under `PYTHONHASHSEED=0` and `=12345` and fails if the
  digests differ (set/dict ordering must not reach state or events).

## 2. Bisector (`tools/h3re/h3re/bisect_tool.py`)

- `python3 -m h3re.bisect_tool A.json B.json` compares two command logs
  (`{"kind", "seed", "commands": [{"type": "Move", ...}]}`).
- `python3 -m h3re.bisect_tool --kind K --seed S --perturb rng@K|drop@K|dup@K [--emit F]`
  generates the seed's log and compares it with a perturbed replay.
- Policies: `--policy NAME` (a `soak.POLICY_MATRIX` name; the kind selects the battle or
  adventure kwargs) applies to both sides; `--policy-a` / `--policy-b` set one side.
  `--override` / `--override-a` / `--override-b` take field overrides as a JSON object or
  `field=value;field=value` (values JSON, lists become tuples), layered over the named
  policy. Field names are validated against the kind's policy dataclass; unknown names
  or fields are rejected (usage error, exit 2; no run). A log may carry an optional
  header `"policy": {"name": N|null, "fields": {...}}` (omitted when default, so old
  logs are unchanged), used unless the CLI names a policy for that side; `--emit`
  writes it. Each run prints `policy A: ...` and `policy B: ...` before the report, so
  the same log under two policies localises a policy-caused divergence. Seed mode
  generates the log under side A's policy and replays it under B's.
- Output: first divergent step, both commands, and the differing state fields as
  dotted paths (`stacks[5].top_hp: 29 != 25`). Exit 1 if they diverge.

## 3. Banned-API lint (`tools/lint/banned_api_lint.py`)

`python3 tools/lint/banned_api_lint.py [--allowlist F] [files]` (default: the four
simulation modules). AST based. Rules:

| Rule | Bans |
|---|---|
| FLOAT_LITERAL | float constants |
| TRUE_DIV | `/` and `/=` |
| FLOAT_CALL | `float()` |
| MATH_FLOAT | `math` functions returning floats (floor, ceil, trunc, gcd, lcm, isqrt, comb, perm, factorial are allowed) |
| BANNED_IMPORT | time, datetime, random, os, sys, io, pathlib, subprocess, threading, ... |
| BANNED_CALL | open, print, input, eval, exec, id, hash, calls on banned modules |
| ITER_UNORDERED | iterating a set, set-valued name, or dict `.keys/.values/.items()` without `sorted()` (comprehensions directly consumed by sum/min/max/any/all/len/sorted/set are exempt) |

Allowlist: `tools/lint/banned_api_allowlist.json`, entries
`{"file", "rule", "function"?, "justification"}`; a missing justification is an
error. Inline alternative: `# det-lint-allow: RULE -- reason` on the line.

Current allowlist (reviewed, order-free): `battle._speed_sorted` (rank table
keyed by id), `AdventurePolicy.__post_init__` (`any` over values), `adventure._search`
(result dict looked up by key).

## CI

Job `determinism` in `.github/workflows/test.yml` runs the lint, a 30-game soak (max 120 steps), and the policy-matrix soak twice under different `PYTHONHASHSEED` values with a digest comparison.
