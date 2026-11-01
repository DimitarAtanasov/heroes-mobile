# Deterministic RNG (`sim.rng`)

Reference implementation: `tools/h3re/h3re/rng.py`. Resolves the open choice in
`engine-design.md` section 1.4: **PCG32 (XSH-RR 64/32)** is chosen. It is fixed
forever; `RNG_VERSION = 1` is stored in save files.

## Algorithm

State is 64-bit, increment `inc = (seq << 1) | 1`, multiplier
`6364136223846793005`, all arithmetic mod 2^64.

- Seeding: `state = 0; step; state += seed; step`.
- Step: `state = state * MULT + inc`.
- Output (from the pre-step state `old`):
  `xorshifted = (((old >> 18) ^ old) >> 27) mod 2^32`, `rot = old >> 59`,
  result = `rotr32(xorshifted, rot)`.

Published check vector, seed 42, seq 54: `a15c02b7 7b47f409 ba1d3330 83d2f293
bfa4784b cbed606e` (verified by the tests).

## API

- `Pcg32(seed, seq=0)`, `next_u32()`.
- `range(lo, hi)`: uniform in the **half-open** interval `[lo, hi)`, span at
  most 2^32. Rejection sampling: with `span = hi - lo`, draws `r <
  (2^32 - span) mod span` are discarded; the result is `lo + r mod span`. Note
  that engine-design names this call `range(lo, hi_inclusive)`; the inclusive
  form is `randint`, so the spec text should be read accordingly.
- `randint(lo, hi)`: inclusive `[lo, hi]` (= `range(lo, hi + 1)`); matches the
  `rng.randint(a, b)` contract that `rules.base_damage` consumes.
- `chance(num, den)`: true with probability exactly `num/den`
  (`range(0, den) < num`); no draw is consumed when `num <= 0` or `num >= den`.

## Named streams

`derive_stream(master_seed, domain, id="")` (or `RngStreams(seed).stream(...)`)
hashes `SHA-256("h3re-rng" || version byte || len-prefixed(master_seed as
little-endian signed bytes, at least 8) || len-prefixed(domain UTF-8) ||
len-prefixed(id UTF-8))` (lengths are 4-byte little-endian). The first 8
digest bytes (little-endian) are the PCG seed, the next 8 the sequence.
Domains follow engine-design: `"battle:<battle_id>"`, `"map-gen"`, `"weekly"`,
`"ai:<player>"`. Streams are independent, so adding draws in one subsystem
cannot shift another.

Draw order is part of the spec (see `rules.md`); changing the number or order of
draws within a stream changes replays and requires a version bump.
