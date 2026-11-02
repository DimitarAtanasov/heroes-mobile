package h3.sim

import java.io.ByteArrayOutputStream
import java.util.zip.CRC32
import java.util.zip.Deflater
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertNull
import kotlin.test.assertTrue

private fun unhex(s: String): ByteArray = ByteArray(s.length / 2) { s.substring(it * 2, it * 2 + 2).toInt(16).toByte() }

private fun hexOf(b: ByteArray?): String? = b?.joinToString("") { "%02x".format(it.toInt() and 0xFF) }

// ---- canonical JSON: sorted keys, compact, ASCII only (Python json.dumps(sort_keys, ensure_ascii)).

private fun canon(v: Any?, sb: StringBuilder) {
    when (v) {
        null -> sb.append("null")
        is Boolean -> sb.append(if (v) "true" else "false")
        is Number -> sb.append(v.toString())
        is String -> {
            sb.append('"')
            for (c in v) {
                when {
                    c == '"' -> sb.append("\\\"")
                    c == '\\' -> sb.append("\\\\")
                    c == '\n' -> sb.append("\\n")
                    c == '\r' -> sb.append("\\r")
                    c == '\t' -> sb.append("\\t")
                    c == '\b' -> sb.append("\\b")
                    c == '\u000c' -> sb.append("\\f")
                    c.code < 0x20 || c.code > 0x7E && c.code != 0x7F -> sb.append("\\u").append("%04x".format(c.code))
                    else -> sb.append(c)
                }
            }
            sb.append('"')
        }
        is List<*> -> {
            sb.append('[')
            v.forEachIndexed { i, e -> if (i > 0) sb.append(','); canon(e, sb) }
            sb.append(']')
        }
        is Map<*, *> -> {
            sb.append('{')
            v.keys.map { it as String }.sorted().forEachIndexed { i, k ->
                if (i > 0) sb.append(',')
                canon(k, sb)
                sb.append(':')
                canon(v[k], sb)
            }
            sb.append('}')
        }
        else -> error("cannot serialise ${v::class}")
    }
}

private fun canonText(v: Any?): String = StringBuilder().also { canon(v, it) }.toString()

private fun sha256Hex(b: ByteArray): String =
    hexOf(java.security.MessageDigest.getInstance("SHA-256").digest(b))!!

private fun pair(p: Pair<Int, Int>) = listOf(p.first, p.second)

private fun dumpVictory(v: H3mVictory?): Any? = v?.let {
    val m = LinkedHashMap<String, Any?>()
    m["type"] = it.type
    m["allow_normal_victory"] = it.allowNormalVictory
    m["applies_to_ai"] = it.appliesToAi
    it.artifact?.let { x -> m["artifact"] = x }
    it.creature?.let { x -> m["creature"] = x }
    it.count?.let { x -> m["count"] = x }
    it.resource?.let { x -> m["resource"] = x }
    it.amount?.let { x -> m["amount"] = x }
    it.pos?.let { x -> m["pos"] = x }
    it.hallLevel?.let { x -> m["hall_level"] = x }
    it.castleLevel?.let { x -> m["castle_level"] = x }
    m
}

private fun dumpLoss(l: H3mLoss?): Any? = l?.let {
    val m = LinkedHashMap<String, Any?>()
    m["type"] = it.type
    it.pos?.let { x -> m["pos"] = x }
    it.days?.let { x -> m["days"] = x }
    m
}

private fun dumpPredefined(p: H3mPredefinedHero): Any? {
    val m = LinkedHashMap<String, Any?>()
    p.experience?.let { m["experience"] = it }
    p.secondarySkills?.let { m["secondary_skills"] = it.map(::pair) }
    p.artifacts?.let { m["artifacts"] = it }
    p.backpack?.let { m["backpack"] = it }
    p.biography?.let { m["biography"] = it }
    p.gender?.let { m["gender"] = it }
    p.spellsMask?.let { m["spells_mask"] = hexOf(it) }
    p.primarySkills?.let { m["primary_skills"] = it }
    return m
}

private const val RAW_TILES_MAX = 16

/** Same shape as vectors_h3m.dump_header. */
internal fun dumpHeader(h: H3mHeader): Map<String, Any?> {
    val tiles = LinkedHashMap<String, Any?>()
    tiles["count"] = h.tiles.count
    tiles["sha256"] = sha256Hex(h.tiles.raw)
    if (h.tiles.count <= RAW_TILES_MAX) tiles["raw"] = hexOf(h.tiles.raw)
    val m = LinkedHashMap<String, Any?>()
    m["format"] = h.format
    m["version"] = h.version
    m["has_hero"] = h.hasHero
    m["size"] = h.size
    m["two_levels"] = h.twoLevels
    m["levels"] = h.levels
    m["name"] = h.name
    m["description"] = h.description
    m["difficulty"] = h.difficulty
    m["max_hero_level"] = h.maxHeroLevel
    m["players"] = h.players.map { p ->
        linkedMapOf<String, Any?>(
            "index" to p.index, "can_human" to p.canHuman, "can_computer" to p.canComputer,
            "ai_behavior" to p.aiBehavior, "allowed_factions" to p.allowedFactions,
            "faction_random" to p.factionRandom, "has_main_town" to p.hasMainTown,
            "generate_hero_at_main_town" to p.generateHeroAtMainTown, "main_town_pos" to p.mainTownPos,
            "has_random_hero" to p.hasRandomHero, "main_hero_id" to p.mainHeroId,
            "main_hero_portrait" to p.mainHeroPortrait, "main_hero_name" to p.mainHeroName,
            "heroes" to p.heroes.map { listOf(it.first, it.second) },
        )
    }
    m["victory"] = dumpVictory(h.victory)
    m["loss"] = dumpLoss(h.loss)
    m["teams"] = h.teams
    m["allowed_heroes_mask"] = hexOf(h.allowedHeroesMask)
    m["allowed_heroes"] = h.allowedHeroes
    m["placeholder_heroes"] = h.placeholderHeroes
    m["disposed_heroes"] = h.disposedHeroes.map {
        linkedMapOf<String, Any?>("id" to it.id, "portrait" to it.portrait, "name" to it.name, "players" to it.players)
    }
    m["allowed_artifacts_mask"] = hexOf(h.allowedArtifactsMask)
    m["banned_artifacts"] = h.bannedArtifacts
    m["allowed_spells_mask"] = hexOf(h.allowedSpellsMask)
    m["banned_spells"] = h.bannedSpells
    m["allowed_skills_mask"] = hexOf(h.allowedSkillsMask)
    m["banned_skills"] = h.bannedSkills
    m["rumors"] = h.rumors.map { listOf(it.first, it.second) }
    m["predefined_heroes"] = h.predefinedHeroes.entries.associate { it.key.toString() to dumpPredefined(it.value) }
    m["tiles"] = tiles
    return m
}

// ---- small helpers to build maps by hand in the API tests.

private fun le32(v: Long): ByteArray = ByteArray(4) { ((v shr (8 * it)) and 0xFF).toByte() }
private fun str(s: String): ByteArray = le32(s.length.toLong()) + s.toByteArray(Charsets.ISO_8859_1)

/** Smallest valid RoE map: 1x1, no teams, 8 inactive players, no conditions. */
private fun tinyRoe(name: String = "T"): ByteArray {
    var b = le32(H3M_ROE.toLong()) + byteArrayOf(1) + le32(1) + byteArrayOf(0) + str(name) + str("") + byteArrayOf(0)
    for (i in 0 until 8) b += ByteArray(2 + 6)
    b += byteArrayOf(0xFF.toByte(), 0xFF.toByte(), 0) // no victory, no loss, no teams
    b += ByteArray(16) + ByteArray(31) + le32(0) // heroes mask, reserved, rumors
    b += ByteArray(7) // one tile
    return b
}

private fun gzipOf(data: ByteArray): ByteArray {
    val def = Deflater(9, true)
    def.setInput(data)
    def.finish()
    val out = ByteArrayOutputStream()
    out.write(byteArrayOf(0x1F, 0x8B.toByte(), 8, 0, 0, 0, 0, 0, 0, 3))
    val buf = ByteArray(4096)
    while (!def.finished()) out.write(buf, 0, def.deflate(buf))
    def.end()
    val crc = CRC32().also { it.update(data) }
    out.write(le32(crc.value))
    out.write(le32(data.size.toLong()))
    return out.toByteArray()
}

class H3mTest {
    @Test
    fun conformanceVectorsReplay() {
        val all = loadVector("h3m.json")["cases"].list()
        assertTrue(all.size >= 1500, "vector count ${all.size}")
        val blobs = LinkedHashMap<String, ByteArray>()
        var ok = 0
        var bad = 0
        for (cv in all) {
            val c = cv.obj()
            val name = c["name"] as String
            val data = if (c.containsKey("hex")) {
                unhex(c["hex"] as String).also { blobs[name] = it }
            } else {
                val base = blobs[c["of"] as String] ?: error("$name: unknown base")
                base.copyOfRange(0, c["cut"].big().toInt())
            }
            val exp = c["expect"].obj()
            if (exp["ok"] == true) {
                ok++
                val h = H3m.parse(data)
                assertEquals(canonText(exp["header"]), canonText(dumpHeader(h)), name)
            } else {
                bad++
                val e = assertFailsWith<H3mError>(name) { H3m.parse(data) }
                assertEquals(exp["hota"] == true, e is H3mHotaError, name)
            }
        }
        assertTrue(ok >= 200 && bad >= 1000, "ok=$ok bad=$bad")
    }

    @Test
    fun tinyMapParses() {
        val h = H3m.parse(tinyRoe("Hi"))
        assertEquals("RoE", h.version)
        assertEquals("Hi", h.name)
        assertEquals(1, h.size)
        assertEquals(1, h.levels)
        assertNull(h.maxHeroLevel)
        assertNull(h.victory)
        assertNull(h.loss)
        assertEquals(emptyList(), h.teams)
        assertEquals(8, h.players.size)
        assertFalse(h.players[0].active)
        assertEquals(128, h.allowedHeroesMask.size * 8)
        assertEquals(listOf(0, 0, 0, 0, 0, 0, 0), h.tiles.tile(0, 0))
        assertFailsWith<IndexOutOfBoundsException> { h.tiles.tile(1, 0) }
        assertFailsWith<IndexOutOfBoundsException> { h.tiles.tile(0, 0, 1) }
    }

    @Test
    fun objectsAreNotPortedAndRefused() {
        assertFailsWith<H3mError> { H3m.parse(tinyRoe(), objects = true) }
    }

    @Test
    fun cp1252StringsDecodeLikePython() {
        val raw = tinyRoe("")
        // name length 0 -> replace with raw bytes: E9 80 81 9F FF
        val name = byteArrayOf(0xE9.toByte(), 0x80.toByte(), 0x81.toByte(), 0x9F.toByte(), 0xFF.toByte())
        val patched = raw.copyOfRange(0, 10) + le32(5) + name + raw.copyOfRange(14, raw.size)
        assertEquals("é€�Ÿÿ", H3m.parse(patched).name)
    }

    @Test
    fun gzipWrappedAndPlainAgree() {
        val raw = tinyRoe("Z")
        assertEquals("Z", H3m.parse(gzipOf(raw)).name)
        assertEquals("Z", H3m.parse(raw).name)
        assertFailsWith<H3mError> { H3m.parse(gzipOf(raw) + byteArrayOf(0)) }
        assertFailsWith<H3mError> { H3m.parse(gzipOf(raw) + gzipOf(raw)) }
        val g = gzipOf(raw)
        for (cut in 2 until g.size) assertFailsWith<H3mError>("cut $cut") { H3m.parse(g.copyOfRange(0, cut)) }
    }

    @Test
    fun hotaIsDistinct() {
        assertFailsWith<H3mHotaError> { H3m.parse(le32(0x20) + ByteArray(64)) }
        assertFailsWith<H3mError> { H3m.parse(le32(0x99) + ByteArray(64)) }
    }

    @Test
    fun everyCutOfTinyMapFails() {
        val raw = tinyRoe()
        for (n in 0 until raw.size) assertFailsWith<H3mError>("cut $n") { H3m.parse(raw.copyOfRange(0, n)) }
        H3m.parse(raw)
    }
}
