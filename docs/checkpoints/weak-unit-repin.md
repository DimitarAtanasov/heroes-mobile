# Weak-unit vector re-pin (owner review pending)

Owner decision 2026-11-02: a creature with `dmg_min` 0 (and `dmg_max` >= 1) is a valid weak unit in
battle. The base roll is 0..`dmg_max`; the final damage keeps its minimum of 1 (no change to the
damage rule). Conformance vectors that pinned a refusal of `dmg_min` 0 are regenerated here with the
repo's generator (`python3 -m h3re.vectors`, which also runs `vectors_encounter`). No JSON was edited
by hand. This change needs owner review before merge (CLAUDE.md law 6; reason recorded in
`docs/specs/battle.md` section 10).

## Generator changes (`tools/h3re/h3re/vectors.py`)

The generator crashed after the rules change: it asserted a `ValueError` for `dmg_min` 0, and
`_Scripted([])` ran out of rolls ("script exhausted") once the call became a real roll.

- `base_damage` case (5, 0, 3): now a real roll with the fixed script `[0, 3, 1, 0, 2]` (both ends
  of 0..3, zeros included). The generator checks that the script is used up, as for every roll case.
- `resolve` context (count 3, 0..2): now resolved under PESSIMAL, EXPECTED and OPTIMAL in the same
  position. The other four error contexts are unchanged.
- `resolve_seeded` case (count 3, 0..2, luck 2): now resolved with seed 1, seq 0 (`Pcg32(1, 0)`).
  So that a seeded refusal stays pinned, one error case is added after it: count 3, `dmg_min` 3 >
  `dmg_max` 2, luck 2, seed 1, seq 0.
- `encounter.json` variant `creature-zero-damage` (archer `dmg_min` 0): no generator change; the
  variant is regenerated as is.

## Changed cases

### rules.json

sha256 of the file: `0349faa66465ed56c4eff6664d06e5f558e4055a2bf07870494652e23d250769` ->
`d30c9390154177f6a2114e0fc97614622430db4f398d10284e25084db5bfe96d`.

| Case | Old | New |
|---|---|---|
| `base_damage[163]` count 5, dmg 0..3 | `rolls: []`, `error: true` | `rolls: [0, 3, 1, 0, 2]`, `out: 6` |
| `resolve[759]` count 3, dmg 0..2, PESSIMAL | `error: true` | `damage: 1`, `lucky: false`, `unlucky: false` |
| `resolve[760]` count 3, dmg 0..2, EXPECTED | `error: true` | `damage: 3`, `lucky: false`, `unlucky: false` |
| `resolve[761]` count 3, dmg 0..2, OPTIMAL | `error: true` | `damage: 6`, `lucky: false`, `unlucky: false` |
| `resolve_seeded[253]` count 3, dmg 0..2, luck 2, seed 1, seq 0 | `error: true` | `damage: 1`, `lucky: false`, `unlucky: false`, `state_after: 11087163948811863063` |
| `resolve_seeded[254]` (added) count 3, dmg 3..2, luck 2, seed 1, seq 0 | (none) | `error: true` |

`resolve[759]` (PESSIMAL, base 3 x 0 = 0) shows the minimum-1 rule on a weak unit. Section sizes:
`base_damage` 166 and `resolve` 777 are unchanged; `resolve_seeded` grows from 254 to 255.

### encounter.json

sha256 of the file: `9ce9f2f4a7d7be85e0d81f385698f4cce168d464abb3f7227533a8f795aa209f` ->
`61f9f322e57d6f1846e42450affe7eee558bb91b053508b83fab3596aa52d298`.

Variant `creature-zero-damage` (`variants[12]`): its own `sha256` (the hash of the variant's game
state) is `2127e116c16979e0ba13072302f93a696780366e071f55c93d95b2e516a131e1` before and after. The
state is the same; only the verdict of one attempt changed:

| Case | Old | New |
|---|---|---|
| `variants[12].attempts[5]` Attack hero 0 -> `wolves` | `error: "battle cannot be set up: invalid damage range"`, `rng_after: [16664820097240435753, 16458010844088880383]` | `ok: 4b7ac369a58e0cc858d5d9ae1a966c4d6ee8d207f243ed3c23be1f3d3dac750e`, `rng_after: [15910703594411793501, 16458010844088880383]` |

The other 80 attempts of the variant, the other variants and the golden block are unchanged.

## Unchanged

- Every other vector file is byte-identical to a fresh generation, except `h3m.json` and `lod.json`.
  Those two differ only in zlib-compressed bytes: this machine's Python 3.14 links zlib-ng 1.3.1,
  which compresses differently from the zlib that produced the committed files. They do not involve
  damage, and they are not part of this change (left as committed).
- Golden hashes: no golden pin in `tools/h3re/tests` moved (battle `fbe9015b...`, and the adventure,
  encounter, hero and town goldens). The golden tests pass unchanged.

## Data pack and content floor (second commit)

Owner decision 2026-11-02, part 3: the creature `dmg_min` floor in the data pack goes from 1 to 0
(`tools/h3re/h3re/datapack.py`, Kotlin `Datapack.CR_INTS` and `DefaultCreatureValidator` in
`Content.kt`). `dmg_max` stays 1..10000 and `dmg_min <= dmg_max` stays. Python content validation
goes through `datapack.py`, so it follows. Generator changes:

- `vectors_pack.py`: the invalid case "dmg_min 0" is now valid, so it is replaced in place by
  "dmg_min 0 dmg_max 0" (refused by the `dmg_max` floor). A plain "dmg_min -1" was not used: the
  mutation walker already makes that text, so it would be de-duplicated and shift later indices.
  The valid "boundary stats" creature (`\U0001F600 Test`) moves from `dmg_min` 1 to 0, the new
  lower bound, so acceptance of 0 is pinned.
- `vectors_txt.py`: the content case `err_dmg_min_zero` is renamed `err_dmg_min_zero_ok` (as the
  existing `err_cost_negative_ok`), because it is now accepted.

### datapack.json

sha256 of the file: `9a7344a3bc368b9c9f369631f126bfe727c4d76e942588e83119c39b608a6894` ->
`d0eeff8b630a629eb100fc9b28a6968a22227fab0282773a0ba87fcfb5864aea`. Section sizes are unchanged.

| Case | Old | New |
|---|---|---|
| `invalid[726..728]`, `[772..774]`, `[824..826]`, `[876..878]` (dmg_min 2147483648 / -1 / 10**30 on creatures 0..3) | message `... out of range 1..10000` | message `... out of range 0..10000` (still refused) |
| `invalid[910]` | id `creatures: dmg_min 0`, message `creatures[0].dmg_min: 0 out of range 1..10000` | id `creatures: dmg_min 0 dmg_max 0`, message `creatures[0].dmg_max: 0 out of range 1..10000` |
| `valid[35..37]` (non-ascii names and boundary stats, 3 encodings) | creature `dmg_min` 1, hash `39524dfd...b240` | creature `dmg_min` 0, hash `87424c89...3b27` |

### content.json

sha256 of the file: `976f424d0e0cce66ba4ee5f9b137777520507ce42c60e224c647caaa193f5aa3` ->
`8daea1e5eb886b35d779a9bf6f9516e965e30f4cdb29387b5b73218982921598`.

| Case | Old | New |
|---|---|---|
| `cases[34]` | name `err_dmg_min_zero`, `error: {category: schema, row: 3}` | name `err_dmg_min_zero_ok`, `expect`: Glimmerwisp with `dmg_min` 0, `dmg_max` 5 |

All other vector files are unchanged by this commit.
