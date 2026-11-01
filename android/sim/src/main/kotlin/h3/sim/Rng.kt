package h3.sim

import java.math.BigInteger
import java.security.MessageDigest

const val RNG_VERSION = 1

private const val MULT = 6364136223846793005UL

/** PCG32 (XSH-RR 64/32), mirroring tools/h3re/h3re/rng.py exactly. */
class Pcg32(seed: ULong, seq: ULong = 0UL) {
    var state: ULong = 0UL
        private set
    val inc: ULong = (seq shl 1) or 1UL

    init {
        step()
        state += seed
        step()
    }

    private fun step() {
        state = state * MULT + inc
    }

    /** Next 32-bit output, returned as a non-negative Long (0..2^32-1). */
    fun nextU32(): Long {
        val old = state
        step()
        val xorshifted = (((old shr 18) xor old) shr 27).toUInt()
        val rot = (old shr 59).toInt()
        return xorshifted.rotateRight(rot).toLong() and 0xFFFFFFFFL
    }

    /** Uniform in the half-open interval [lo, hi); span must be in 1..2^32. */
    fun range(lo: Long, hi: Long): Long {
        val span = hi - lo
        require(span > 0) { "empty range" }
        require(span <= (1L shl 32)) { "range wider than 2**32" }
        val threshold = ((1L shl 32) - span) % span
        while (true) {
            val r = nextU32()
            if (r >= threshold) return lo + r % span
        }
    }

    /** Uniform in the inclusive interval [lo, hi]. */
    fun randint(lo: Long, hi: Long): Long = range(lo, hi + 1)

    /** True with probability num/den; consumes no draw when num <= 0 or num >= den. */
    fun chance(num: Long, den: Long): Boolean {
        require(den > 0) { "den must be positive" }
        if (num <= 0) return false
        if (num >= den) return true
        return range(0, den) < num
    }
}

object RngStreams {
    private fun enc(b: ByteArray): ByteArray {
        val n = b.size
        return byteArrayOf(n.toByte(), (n shr 8).toByte(), (n shr 16).toByte(), (n shr 24).toByte()) + b
    }

    /** Little-endian signed two's complement, at least 8 bytes, length max(8, (bit_length(|x|)+8)/8) as in Python. */
    internal fun seedBytes(seed: BigInteger): ByteArray {
        val n = maxOf(8, (seed.abs().bitLength() + 8) / 8)
        val be = seed.toByteArray()
        val pad = if (seed.signum() < 0) 0xFF.toByte() else 0.toByte()
        val full = ByteArray(n) { pad }
        be.copyInto(full, n - be.size)
        return full.reversedArray()
    }

    fun derive(masterSeed: BigInteger, domain: String, id: String = ""): Pcg32 {
        val msg = "h3re-rng".toByteArray(Charsets.US_ASCII) +
            byteArrayOf(RNG_VERSION.toByte()) +
            enc(seedBytes(masterSeed)) +
            enc(domain.toByteArray(Charsets.UTF_8)) +
            enc(id.toByteArray(Charsets.UTF_8))
        val d = MessageDigest.getInstance("SHA-256").digest(msg)
        return Pcg32(le64(d, 0), le64(d, 8))
    }

    fun derive(masterSeed: Long, domain: String, id: String = ""): Pcg32 =
        derive(BigInteger.valueOf(masterSeed), domain, id)

    private fun le64(d: ByteArray, off: Int): ULong {
        var v = 0UL
        for (i in 7 downTo 0) v = (v shl 8) or (d[off + i].toULong() and 0xFFUL)
        return v
    }
}
