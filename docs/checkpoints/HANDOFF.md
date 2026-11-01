# Handoff (resume here)

Branch: `ccr-c70423ba-3alf1w`. Checkpoints 0-52 and ADR-0010 are committed and pushed; the working
tree was clean at save time. License: GPL-2.0-or-later (ADR-0010). Python is the reference oracle;
Kotlin must reproduce its hashes (ADR-0004, ADR-0007).

Verify the state first:
- `python3 -m unittest discover -s tools/h3re/tests` (570 tests, 4 skipped without H3_DATA_DIR)
- `python3 tools/lint/banned_api_lint.py` (0 violations, 8 files)
- `cd tools/h3re && python3 -m h3re.vectors --check` (vectors in sync)
- `cd android && gradle :sim:test` (50 Kotlin tests; Maven Central can return HTTP 429: wait and retry)

## Done
- Python: readers (LOD, DEF, PCX, TXT, H3M incl. objects), rules, battle, adventure, encounter, town,
  hero, replay files, presenter, content loader, determinism gate (soak, bisector, lint), data packs.
- Kotlin `android/sim` (plain JVM, no Android deps): canonical JSON + SHA-256, PCG32 + streams,
  Rational, damage Rules, Hex grid + movement, typed BattleState + codec, `Battle.apply`.
  All proven equal to Python by generated vectors. The `:app` module is a 13-line stub; it builds
  only with `-PwithApp=true` and cannot be built here (dl.google.com is blocked).

## Next (in order)
1. Kotlin `legal_commands` and `strike_preview` (needed by UI and AI), then the greedy AI.
2. Kotlin port of the presenter view-model (`present.py`) as the UI contract.
3. Kotlin readers for the player's own data (LOD, DEF, PCX, TXT, H3M) via the Storage Access
   Framework; sprite decoding per `defimg.py` and the VCMI-confirmed palette rules.
4. Android app: Compose Canvas battle board driven by the view-model, tap-to-preview then
   tap-to-confirm; needs a machine or CI with Google Maven access. GPL is accepted, so VCMI's client
   rendering design may be ported with provenance headers (ADR-0010).
5. Python: unsupported H3M object bodies (sign, seer hut, garrison, shrine ...), adventure
   constants into data (needs a reviewed re-pin), spells after rules.md section 9 experiments.
6. Port adventure/encounter/town/hero/replay to Kotlin after the battle app works.

## Open items / caveats
- `bad_morale_table` is not in data/battle_policy.json (comes from the rules pack); Kotlin takes it as input.
- `_OMIT_WHEN_DEFAULT` is empty, so omit-at-default is only tested synthetically in Kotlin.
- ADR-0009 proposes that Kotlin Rational overflow throws; the owner has not confirmed it.
- Lead mutation check on the good-morale roll (`m > 0` -> `m >= 0`) survived; judged an equivalent
  mutant (zero-probability chance draws nothing). ~~Worth a proof test.~~ Closed: test_rng.py
  `CHANCE_EDGES` and Kotlin `RngEdgeTest` pin that the guards consume no draw (state compared).
- ~~Missing tests: adventure `Move.dest` float/bool rejection; changing stored town/hero content
  changes `state_hash`.~~ Closed (`CommandInputTypeTest`, `StoredContentHashTest` in town/hero).
- OPEN BUG found by those tests (3 `expectedFailure` in test_adventure.py): `Move.hero` accepts
  bools (`isinstance(..., int)`), and `EndTurn.player` accepts 0.0/False (`!=` comparison).
- The ability-text table in data/txt_maps/crtraits.json is placeholder; check against a real file.

## Needs the user (cannot be verified without real data)
A legal HoMM3 install with `H3_DATA_DIR` set; real .h3m maps (RoE/AB/SoD); results of the rules.md
section 9 experiments (speed ties, wait order, bad-morale table, damage-roll distribution, adventure costs).
