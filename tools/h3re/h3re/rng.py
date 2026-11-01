"""Deterministic RNG for the simulation core: PCG32 (XSH-RR 64/32).

Implemented from the published algorithm description (64-bit LCG state,
output permutation = xorshift-high then random rotate). Integer-only, so
results are identical on every platform. See docs/specs/rng.md.
"""

import hashlib

RNG_VERSION = 1  # stored in save files; algorithm is fixed forever

_MASK64 = (1 << 64) - 1
_MASK32 = (1 << 32) - 1
_MULT = 6364136223846793005


class Pcg32:
    """PCG32 generator. ``seed`` is the initial state, ``seq`` the stream."""

    __slots__ = ("state", "inc")

    def __init__(self, seed, seq=0):
        self.state = 0
        self.inc = ((int(seq) << 1) | 1) & _MASK64
        self._step()
        self.state = (self.state + int(seed)) & _MASK64
        self._step()

    def _step(self):
        self.state = (self.state * _MULT + self.inc) & _MASK64

    def next_u32(self):
        old = self.state
        self._step()
        xorshifted = (((old >> 18) ^ old) >> 27) & _MASK32
        rot = old >> 59
        return ((xorshifted >> rot) | (xorshifted << ((-rot) & 31))) & _MASK32

    def range(self, lo, hi):
        """Uniform integer in the half-open interval [lo, hi).

        Unbiased: draws below ``(2**32 - span) % span`` are rejected so the
        remaining draws split evenly into ``span`` residue classes.
        """
        span = hi - lo
        if span <= 0:
            raise ValueError("empty range")
        if span > (1 << 32):
            raise ValueError("range wider than 2**32")
        threshold = ((1 << 32) - span) % span
        while True:
            r = self.next_u32()
            if r >= threshold:
                return lo + r % span

    def randint(self, lo, hi):
        """Uniform integer in the inclusive interval [lo, hi]
        (same contract as random.Random.randint, used by rules.py)."""
        return self.range(lo, hi + 1)

    def chance(self, num, den):
        """True with probability num/den (exact, integer only)."""
        if den <= 0:
            raise ValueError("den must be positive")
        if num <= 0:
            return False
        if num >= den:
            return True
        return self.range(0, den) < num


def _enc(b):
    return len(b).to_bytes(4, "little") + b


def derive_stream(master_seed, domain, ident=""):
    """Named independent stream: Pcg32 seeded from
    SHA-256(version, master_seed, domain, id); first 8 bytes -> state seed,
    next 8 bytes -> sequence (both little-endian)."""
    seed_i = int(master_seed)
    seed_b = seed_i.to_bytes(max(8, (seed_i.bit_length() + 8) // 8), "little", signed=True)
    msg = (
        b"h3re-rng"
        + bytes([RNG_VERSION])
        + _enc(seed_b)
        + _enc(str(domain).encode("utf-8"))
        + _enc(str(ident).encode("utf-8"))
    )
    d = hashlib.sha256(msg).digest()
    return Pcg32(int.from_bytes(d[:8], "little"), int.from_bytes(d[8:16], "little"))


class RngStreams:
    """Factory of named streams from one master seed."""

    def __init__(self, master_seed):
        self.master_seed = master_seed

    def stream(self, domain, ident=""):
        return derive_stream(self.master_seed, domain, ident)
