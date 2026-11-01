package h3.sim

/**
 * Exact rational number, the Kotlin counterpart of Python's `fractions.Fraction` for the damage
 * pipeline (rules.md 6.6, ADR-0002, ADR-0009).
 *
 * Invariants, as in `Fraction`: the denominator is positive, gcd(|numerator|, denominator) is 1,
 * and zero is stored as 0/1. Every operation normalizes its result, so [numerator] and
 * [denominator] are the reduced pair that Python reports. This matters: `RollPolicy` passes
 * them to `rng.chance(num, den)`, and an unreduced pair would draw from a different range.
 *
 * Overflow is never silent: sums and products use `Math.*Exact`, so an out-of-range value throws
 * [ArithmeticException] instead of wrapping. No BigInteger fallback is included because every
 * value the damage pipeline builds fits in Long once the ADR-0008 caps hold (count x dmg_max and
 * count x hp at most 2**31-1, attack and defense sums within Int): `RationalTest.damagePipelineStaysInLongAtTheCaps`
 * (RulesTest.kt) drives every roll policy at those extremes.
 *
 * [floor] is the single rounding step of the pipeline (Python `math.floor(Fraction)`). Integer
 * division of two Longs elsewhere is `Math.floorDiv`, matching Python's `//`.
 */
class Rational private constructor(val numerator: Long, val denominator: Long) : Comparable<Rational> {

    operator fun plus(o: Rational): Rational {
        // a/b + c/d with g = gcd(b, d): (a*(d/g) + c*(b/g)) / ((b/g)*d).
        val g = gcd(denominator, o.denominator)
        val bg = denominator / g
        val dg = o.denominator / g
        val num = Math.addExact(Math.multiplyExact(numerator, dg), Math.multiplyExact(o.numerator, bg))
        return of(num, Math.multiplyExact(bg, o.denominator))
    }

    operator fun minus(o: Rational): Rational = plus(o.negate())

    operator fun times(o: Rational): Rational {
        // Cross-reduce before multiplying so the products stay small.
        val g1 = gcd(numerator, o.denominator)
        val g2 = gcd(o.numerator, denominator)
        return of(
            Math.multiplyExact(numerator / g1, o.numerator / g2),
            Math.multiplyExact(denominator / g2, o.denominator / g1),
        )
    }

    operator fun div(o: Rational): Rational {
        if (o.numerator == 0L) throw ArithmeticException("Rational division by zero")
        return times(of(o.denominator, o.numerator))
    }

    fun add(o: Rational): Rational = plus(o)
    fun sub(o: Rational): Rational = minus(o)
    fun mul(o: Rational): Rational = times(o)

    fun negate(): Rational = of(Math.negateExact(numerator), denominator)

    fun isZero(): Boolean = numerator == 0L

    /** The one rounding step: floor toward negative infinity (Python `math.floor(Fraction)`). */
    fun floor(): Long = Math.floorDiv(numerator, denominator)

    override fun compareTo(other: Rational): Int =
        Math.multiplyExact(numerator, other.denominator).compareTo(
            Math.multiplyExact(other.numerator, denominator),
        )

    override fun equals(other: Any?): Boolean =
        other is Rational && other.numerator == numerator && other.denominator == denominator

    override fun hashCode(): Int = 31 * numerator.hashCode() + denominator.hashCode()

    override fun toString(): String = "$numerator/$denominator"

    companion object {
        val ZERO: Rational = Rational(0L, 1L)
        val ONE: Rational = Rational(1L, 1L)

        /** Normalized `n / d`. A zero denominator throws; a negative one moves its sign to the numerator. */
        fun of(n: Long, d: Long = 1L): Rational {
            if (d == 0L) throw ArithmeticException("Rational denominator is zero")
            val sn = if (d < 0L) Math.negateExact(n) else n
            val sd = if (d < 0L) Math.negateExact(d) else d
            if (sn == 0L) return ZERO
            val g = gcd(sn, sd)
            return Rational(sn / g, sd / g)
        }

        private fun gcd(a: Long, b: Long): Long {
            var x = Math.absExact(a)
            var y = Math.absExact(b)
            while (y != 0L) {
                val t = x % y
                x = y
                y = t
            }
            return x
        }
    }
}
