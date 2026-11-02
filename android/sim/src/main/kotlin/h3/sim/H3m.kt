package h3.sim

import java.util.zip.CRC32
import java.util.zip.DataFormatException
import java.util.zip.Inflater

// Kotlin port of the header half of tools/h3re/h3re/h3m.py (layout in docs/specs/h3m.md).
// ByteArray in (gzip-wrapped or plain), typed header out, every failure an H3mError.
// Parsing stops after the terrain tiles; objects are a later port (objects = true is refused).
// Integer-only; uint32 fields are Long. Strings are Windows-1252 decoded by hand so the
// result does not depend on the JVM charset tables (undefined bytes become U+FFFD).

const val H3M_ROE = 0x0E
const val H3M_AB = 0x15
const val H3M_SOD = 0x1C
const val H3M_CHR = 0x1D
const val H3M_WOG = 0x33
const val H3M_HOTA = 0x20

const val H3M_MAX_DECOMPRESSED = 64 * 1024 * 1024
const val H3M_MAX_STRING = 1 shl 20
const val H3M_TILE_BYTES = 7

/** Malformed, truncated or unsupported map data (Python H3mError). */
open class H3mError(message: String) : Exception(message)

/** The HotA format (0x20): a recognised but unsupported extended header. */
class H3mHotaError(message: String) : H3mError(message)

class H3mPlayer(
    val index: Int,
    val canHuman: Boolean,
    val canComputer: Boolean,
    val aiBehavior: Int,
    val allowedFactions: Int?,
    val factionRandom: Boolean,
    val hasMainTown: Boolean,
    val generateHeroAtMainTown: Boolean,
    val mainTownPos: List<Int>?,
    val hasRandomHero: Boolean,
    val mainHeroId: Int?,
    val mainHeroPortrait: Int?,
    val mainHeroName: String?,
    val heroes: List<Pair<Int, String>>,
) {
    val active: Boolean get() = canHuman || canComputer
}

/** Victory condition; only the fields of its [type] are non-null. */
class H3mVictory(
    val type: Int,
    val allowNormalVictory: Boolean,
    val appliesToAi: Boolean,
    val artifact: Int? = null,
    val creature: Int? = null,
    val count: Long? = null,
    val resource: Int? = null,
    val amount: Long? = null,
    val pos: List<Int>? = null,
    val hallLevel: Int? = null,
    val castleLevel: Int? = null,
)

/** Loss condition: [pos] for types 0 and 1, [days] for type 2. */
class H3mLoss(val type: Int, val pos: List<Int>? = null, val days: Int? = null)

class H3mDisposedHero(val id: Int, val portrait: Int, val name: String, val players: Int)

/** Predefined hero record (SoD+); absent optional parts are null. */
class H3mPredefinedHero(
    val experience: Long?,
    val secondarySkills: List<Pair<Int, Int>>?,
    val artifacts: List<Int?>?,
    val backpack: List<Int>?,
    val biography: String?,
    val gender: Int?,
    val spellsMask: ByteArray?,
    val primarySkills: List<Int>?,
)

/** Terrain tiles, level-major then row-major, 7 bytes each, kept compact in [raw]. */
class H3mTiles(val size: Int, val levels: Int, val raw: ByteArray) {
    val count: Int get() = raw.size / H3M_TILE_BYTES

    /** The 7 bytes of a tile: terrain, view, river type, river dir, road type, road dir, flags. */
    fun tile(x: Int, y: Int, level: Int = 0): List<Int> {
        if (x !in 0 until size || y !in 0 until size || level !in 0 until levels) {
            throw IndexOutOfBoundsException("tile ($x, $y, $level) out of bounds")
        }
        val o = ((level * size + y) * size + x) * H3M_TILE_BYTES
        return List(H3M_TILE_BYTES) { raw[o + it].toInt() and 0xFF }
    }
}

class H3mHeader(
    val format: Int,
    val version: String,
    val hasHero: Boolean,
    val size: Int,
    val twoLevels: Boolean,
    val levels: Int,
    val name: String,
    val description: String,
    val difficulty: Int,
    val maxHeroLevel: Int?,
    val players: List<H3mPlayer>,
    val victory: H3mVictory?,
    val loss: H3mLoss?,
    val teams: List<Int>,
    val allowedHeroesMask: ByteArray,
    val allowedHeroes: List<Int>,
    val placeholderHeroes: List<Int>,
    val disposedHeroes: List<H3mDisposedHero>,
    val allowedArtifactsMask: ByteArray?,
    val bannedArtifacts: List<Int>?,
    val allowedSpellsMask: ByteArray?,
    val bannedSpells: List<Int>?,
    val allowedSkillsMask: ByteArray?,
    val bannedSkills: List<Int>?,
    val rumors: List<Pair<String, String>>,
    val predefinedHeroes: Map<Int, H3mPredefinedHero>,
    val tiles: H3mTiles,
)

object H3m {
    private const val NO_CONDITION = 0xFF
    private const val MAX_RUMORS = 4096L
    private const val PREDEFINED_HEROES = 156
    private const val ARTIFACT_SLOTS = 19
    private const val NO_ARTIFACT = 0xFFFF
    private const val SPELL_BYTES = 9
    private const val SPELL_COUNT = 70
    private const val SKILL_BYTES = 4
    private const val SKILL_COUNT = 28

    private val VERSION_NAMES = mapOf(
        H3M_ROE to "RoE", H3M_AB to "AB", H3M_SOD to "SoD", H3M_CHR to "Chronicles", H3M_WOG to "WoG",
    )

    // Windows-1252 0x80..0x9F; undefined bytes decode to U+FFFD like Python errors="replace".
    private val CP1252_HIGH = intArrayOf(
        0x20AC, 0xFFFD, 0x201A, 0x0192, 0x201E, 0x2026, 0x2020, 0x2021,
        0x02C6, 0x2030, 0x0160, 0x2039, 0x0152, 0xFFFD, 0x017D, 0xFFFD,
        0xFFFD, 0x2018, 0x2019, 0x201C, 0x201D, 0x2022, 0x2013, 0x2014,
        0x02DC, 0x2122, 0x0161, 0x203A, 0x0153, 0xFFFD, 0x017E, 0x0178,
    )

    /**
     * Parse an .H3M file: gzip-wrapped (single member) or plain. [objects] = true is refused:
     * the object table is not ported yet.
     */
    fun parse(bytes: ByteArray, objects: Boolean = false): H3mHeader {
        if (objects) throw H3mError("object parsing is not supported by this port")
        val raw = if (bytes.size >= 2 && bytes[0] == 0x1F.toByte() && bytes[1] == 0x8B.toByte()) {
            gunzip(bytes)
        } else {
            bytes
        }
        return parseBytes(raw)
    }

    // ------------------------------------------------------------------ gzip

    private fun gunzip(d: ByteArray): ByteArray {
        // Header, as zlib reads it (wbits 31): ID, CM=8, FLG without reserved bits, MTIME, XFL, OS,
        // then FEXTRA / FNAME / FCOMMENT / FHCRC. Anything missing is a truncated stream.
        var p = 0
        fun need(n: Int) {
            if (n < 0 || p + n > d.size) throw H3mError("truncated gzip stream")
        }
        need(10)
        if (d[2].toInt() != 8) throw H3mError("bad gzip stream: unknown compression method")
        val flg = d[3].toInt() and 0xFF
        if (flg and 0xE0 != 0) throw H3mError("bad gzip stream: unknown header flags set")
        p = 10
        if (flg and 4 != 0) {
            need(2)
            val n = (d[p].toInt() and 0xFF) or ((d[p + 1].toInt() and 0xFF) shl 8)
            p += 2
            need(n)
            p += n
        }
        for (bit in intArrayOf(8, 16)) {
            if (flg and bit != 0) {
                while (true) {
                    need(1)
                    if (d[p++].toInt() == 0) break
                }
            }
        }
        if (flg and 2 != 0) {
            need(2)
            val crc = CRC32()
            crc.update(d, 0, p)
            val want = (d[p].toInt() and 0xFF) or ((d[p + 1].toInt() and 0xFF) shl 8)
            if (want.toLong() != (crc.value and 0xFFFFL)) throw H3mError("bad gzip stream: header crc mismatch")
            p += 2
        }
        // Body: raw deflate, capped. Output of exactly 64 MiB is accepted; Python rejects only
        // when the stream still has output past the cap, so at the cap we probe for one more byte.
        val inf = Inflater(true)
        try {
            inf.setInput(d, p, d.size - p)
            var out = ByteArray(1 shl 16)
            var n = 0
            while (!inf.finished()) {
                if (n == out.size) {
                    if (n >= H3M_MAX_DECOMPRESSED) {
                        val probe = try {
                            inf.inflate(ByteArray(1))
                        } catch (e: DataFormatException) {
                            throw H3mError("bad gzip stream: ${e.message}")
                        }
                        if (probe > 0) throw H3mError("decompressed map exceeds size limit")
                        if (inf.finished()) break
                        throw H3mError("truncated gzip stream")
                    }
                    out = out.copyOf(minOf(out.size * 2, H3M_MAX_DECOMPRESSED))
                }
                val got = try {
                    inf.inflate(out, n, out.size - n)
                } catch (e: DataFormatException) {
                    throw H3mError("bad gzip stream: ${e.message}")
                }
                n += got
                if (got == 0 && !inf.finished() && (inf.needsInput() || inf.needsDictionary())) {
                    throw H3mError("truncated gzip stream")
                }
            }
            val end = p + inf.bytesRead.toInt()
            if (d.size - end < 8) throw H3mError("truncated gzip stream")
            val crc = CRC32()
            crc.update(out, 0, n)
            fun le32(o: Int): Long = (0 until 4).fold(0L) { a, i -> a or ((d[o + i].toLong() and 0xFF) shl (8 * i)) }
            if (le32(end) != crc.value) throw H3mError("bad gzip stream: incorrect data check")
            if (le32(end + 4) != (n.toLong() and 0xFFFFFFFFL)) throw H3mError("bad gzip stream: incorrect length check")
            if (d.size - end - 8 > 0) {
                throw H3mError("${d.size - end - 8} bytes of trailing data after gzip stream (multi-member gzip not supported)")
            }
            return out.copyOf(n)
        } finally {
            inf.end()
        }
    }

    // ---------------------------------------------------------------- reader

    private class Reader(val data: ByteArray) {
        var pos = 0

        fun take(n: Long, what: String): Int {
            if (n < 0 || pos.toLong() + n > data.size) {
                throw H3mError("truncated data reading $what: need $n bytes at offset $pos, size ${data.size}")
            }
            val p = pos
            pos += n.toInt()
            return p
        }

        fun u8(what: String = "u8"): Int = data[take(1, what)].toInt() and 0xFF

        fun u16(what: String = "u16"): Int {
            val p = take(2, what)
            return (data[p].toInt() and 0xFF) or ((data[p + 1].toInt() and 0xFF) shl 8)
        }

        fun u32(what: String = "u32"): Long {
            val p = take(4, what)
            var v = 0L
            for (i in 0 until 4) v = v or ((data[p + i].toLong() and 0xFF) shl (8 * i))
            return v
        }

        fun skip(n: Long, what: String = "padding") {
            take(n, what)
        }

        fun bool(what: String): Boolean = u8(what) != 0

        fun string(what: String = "string"): String {
            val n = u32("$what length")
            if (n > H3M_MAX_STRING) throw H3mError("$what: implausible length $n")
            val p = take(n, what)
            val sb = StringBuilder(n.toInt())
            for (i in p until p + n.toInt()) {
                val b = data[i].toInt() and 0xFF
                sb.append(if (b in 0x80..0x9F) CP1252_HIGH[b - 0x80].toChar() else b.toChar())
            }
            return sb.toString()
        }

        fun pos3(what: String = "position"): List<Int> {
            val p = take(3, what)
            return List(3) { data[p + it].toInt() and 0xFF }
        }

        fun mask(n: Int, what: String): ByteArray {
            val p = take(n.toLong(), what)
            return data.copyOfRange(p, p + n)
        }

        /** A count bounded by [cap] and by the bytes that remain (each item needs [minEach]). */
        fun checked(n: Long, what: String, cap: Long, minEach: Int): Int {
            if (n > cap) throw H3mError("implausible $what $n at offset $pos")
            if (n * minEach > data.size - pos) {
                throw H3mError("truncated data: $what $n needs at least ${n * minEach} bytes at offset $pos, ${data.size - pos} remain")
            }
            return n.toInt()
        }
    }

    // ---------------------------------------------------------------- header

    private fun parseBytes(raw: ByteArray): H3mHeader {
        val r = Reader(raw)
        val fmt = r.u32("format")
        if (fmt == H3M_HOTA.toLong()) {
            throw H3mHotaError("unsupported map format 0x20 (HotA): it uses an extended header this parser does not implement")
        }
        val ver = fmt.toInt()
        val versionName = if (fmt in 0L..0xFFFFL) VERSION_NAMES[ver] else null
        if (versionName == null) throw H3mError("unsupported map format 0x${fmt.toString(16).uppercase()}")
        val hasHero = r.bool("has hero")
        val sizeL = r.u32("map size")
        if (sizeL < 1 || sizeL > 1024) throw H3mError("implausible map size $sizeL")
        val size = sizeL.toInt()
        val two = r.bool("two levels")
        val name = r.string("map name")
        val desc = r.string("map description")
        val diff = r.u8("difficulty")
        if (diff > 4) throw H3mError("invalid difficulty $diff")
        val mhl = if (ver != H3M_ROE) r.u8("max hero level") else null
        val players = List(8) { readPlayer(r, ver, it) }
        val victory = readVictory(r, ver)
        val loss = readLoss(r)
        val nt = r.u8("team count")
        val teams = if (nt != 0) List(8) { r.u8("team") } else emptyList()

        // Extra sections.
        val sodplus = ver >= H3M_SOD
        val heroMask = r.mask(if (ver == H3M_ROE) 16 else 20, "allowed heroes")
        val allowedHeroes = bits(heroMask, if (ver == H3M_ROE) 128 else 156)
        var placeholders: List<Int> = emptyList()
        if (ver != H3M_ROE) {
            val n = r.checked(r.u32("placeholder hero count"), "placeholder hero count", 256, 1)
            placeholders = List(n) { r.u8("placeholder hero id") }
        }
        val disposed = ArrayList<H3mDisposedHero>()
        if (sodplus) {
            val n = r.u8("disposed hero count")
            for (i in 0 until n) {
                disposed.add(
                    H3mDisposedHero(
                        r.u8("disposed hero id"), r.u8("disposed hero portrait"),
                        r.string("disposed hero name"), r.u8("disposed hero players"),
                    ),
                )
            }
        }
        r.skip(31, "reserved block")
        var artMask: ByteArray? = null
        var bannedArt: List<Int>? = null
        if (ver != H3M_ROE) {
            val m = r.mask(if (ver == H3M_AB) 17 else 18, "allowed artifacts")
            artMask = m
            bannedArt = bits(m, if (ver == H3M_AB) 129 else 144)
        }
        var spellMask: ByteArray? = null
        var bannedSpells: List<Int>? = null
        var skillMask: ByteArray? = null
        var bannedSkills: List<Int>? = null
        if (sodplus) {
            spellMask = r.mask(SPELL_BYTES, "allowed spells")
            bannedSpells = bits(spellMask, SPELL_COUNT)
            skillMask = r.mask(SKILL_BYTES, "allowed skills")
            bannedSkills = bits(skillMask, SKILL_COUNT)
        }
        val nr = r.checked(r.u32("rumor count"), "rumor count", MAX_RUMORS, 8)
        val rumors = ArrayList<Pair<String, String>>()
        for (i in 0 until nr) rumors.add(Pair(r.string("rumor name"), r.string("rumor text")))
        val predefined = LinkedHashMap<Int, H3mPredefinedHero>()
        if (sodplus) {
            for (hid in 0 until PREDEFINED_HEROES) {
                readPredefined(r)?.let { predefined[hid] = it }
            }
        }

        // Tiles. size <= 1024 bounds this at 14 MiB; take() checks the data is really there.
        val levels = if (two) 2 else 1
        val n = size.toLong() * size * levels * H3M_TILE_BYTES
        val p = r.take(n, "terrain tiles")
        val tiles = H3mTiles(size, levels, raw.copyOfRange(p, p + n.toInt()))

        return H3mHeader(
            fmt.toInt(), versionName, hasHero, size, two, levels, name, desc, diff, mhl, players,
            victory, loss, teams, heroMask, allowedHeroes, placeholders, disposed,
            artMask, bannedArt, spellMask, bannedSpells, skillMask, bannedSkills,
            rumors, predefined, tiles,
        )
    }

    /** Indices of set bits below [limit] (and within the mask). */
    private fun bits(m: ByteArray, limit: Int): List<Int> {
        val out = ArrayList<Int>()
        for (i in 0 until minOf(limit, m.size * 8)) {
            if ((m[i shr 3].toInt() shr (i and 7)) and 1 == 1) out.add(i)
        }
        return out
    }

    private fun readVictory(r: Reader, ver: Int): H3mVictory? {
        val t = r.u8("victory type")
        if (t == NO_CONDITION) return null
        val normal = r.bool("allow normal victory")
        val ai = r.bool("applies to ai")
        val wide = ver != H3M_ROE
        return when (t) {
            0 -> H3mVictory(t, normal, ai, artifact = if (wide) r.u16() else r.u8())
            1 -> {
                val c = if (wide) r.u16() else r.u8()
                H3mVictory(t, normal, ai, creature = c, count = r.u32())
            }
            2 -> {
                val res = r.u8()
                H3mVictory(t, normal, ai, resource = res, amount = r.u32())
            }
            3 -> {
                val pos = r.pos3()
                val hall = r.u8()
                H3mVictory(t, normal, ai, pos = pos, hallLevel = hall, castleLevel = r.u8())
            }
            4, 5, 6, 7 -> H3mVictory(t, normal, ai, pos = r.pos3())
            8, 9 -> H3mVictory(t, normal, ai)
            10 -> {
                val a = r.u8()
                H3mVictory(t, normal, ai, artifact = a, pos = r.pos3())
            }
            else -> throw H3mError("unknown victory condition type $t")
        }
    }

    private fun readLoss(r: Reader): H3mLoss? {
        val t = r.u8("loss type")
        if (t == NO_CONDITION) return null
        return when (t) {
            0, 1 -> H3mLoss(t, pos = r.pos3())
            2 -> H3mLoss(t, days = r.u16())
            else -> throw H3mError("unknown loss condition type $t")
        }
    }

    private fun readPlayer(r: Reader, ver: Int, idx: Int): H3mPlayer {
        val human = r.bool("can_human")
        val comp = r.bool("can_computer")
        if (!human && !comp) {
            r.skip(when (ver) { H3M_ROE -> 6L; H3M_AB -> 12L; else -> 13L }, "inactive player data")
            return H3mPlayer(idx, false, false, 0, null, false, false, false, null, false, null, null, null, emptyList())
        }
        val ai = r.u8("ai behavior")
        if (ver >= H3M_SOD) r.u8("customized towns flag")
        val factions = if (ver == H3M_ROE) r.u8() else r.u16()
        val random = r.bool("random faction")
        val hasTown = r.bool("has main town")
        var genHero = false
        var townPos: List<Int>? = null
        if (hasTown) {
            if (ver != H3M_ROE) {
                genHero = r.bool("generate hero at main town")
                r.u8("generate hero")
            }
            townPos = r.pos3()
        }
        val randHero = r.bool("random hero")
        val hid = r.u8("main hero id")
        var mainId: Int? = null
        var portrait: Int? = null
        var heroName: String? = null
        if (hid != 0xFF) {
            mainId = hid
            portrait = r.u8("portrait")
            heroName = r.string("main hero name")
        }
        val heroes = ArrayList<Pair<Int, String>>()
        if (ver != H3M_ROE) {
            r.u8("hero placeholder")
            val n = r.u32("hero count")
            if (n > 256) throw H3mError("implausible hero count $n")
            r.checked(n, "hero count", 256, 5)
            for (i in 0 until n.toInt()) heroes.add(Pair(r.u8("hero id"), r.string("hero name")))
        }
        return H3mPlayer(idx, human, comp, ai, factions, random, hasTown, genHero, townPos, randHero,
            mainId, portrait, heroName, heroes)
    }

    private fun readPredefined(r: Reader): H3mPredefinedHero? {
        if (r.u8("predefined hero flag") == 0) return null
        var exp: Long? = null
        var skills: List<Pair<Int, Int>>? = null
        var arts: List<Int?>? = null
        var backpack: List<Int>? = null
        var bio: String? = null
        var spells: ByteArray? = null
        var prim: List<Int>? = null
        if (r.bool("has experience")) exp = r.u32("experience")
        if (r.bool("has secondary skills")) {
            val n = r.u32("secondary skill count")
            if (n > 28) throw H3mError("implausible secondary skill count $n")
            r.checked(n, "secondary skill count", 28, 2)
            skills = List(n.toInt()) { Pair(r.u8("skill"), r.u8("skill level")) }
        }
        if (r.bool("has artifacts")) {
            arts = List(ARTIFACT_SLOTS) { r.u16("artifact").let { a -> if (a == NO_ARTIFACT) null else a } }
            val n = r.checked(r.u16("backpack count").toLong(), "backpack count", 0xFFFF, 2)
            backpack = List(n) { r.u16("backpack artifact") }
        }
        if (r.bool("has biography")) bio = r.string("biography")
        val g = r.u8("gender")
        if (r.bool("has spells")) spells = r.mask(SPELL_BYTES, "hero spells")
        if (r.bool("has primary skills")) prim = List(4) { r.u8("primary skill") }
        return H3mPredefinedHero(exp, skills, arts, backpack, bio, if (g != 0xFF) g else null, spells, prim)
    }
}
