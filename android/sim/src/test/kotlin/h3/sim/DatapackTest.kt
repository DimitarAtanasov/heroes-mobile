package h3.sim

import java.math.BigInteger
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertTrue

/** Conformance of the Kotlin data-pack loader against `vectors/datapack.json` (docs/specs/conformance-datapack.md). */
class DatapackTest {
    private val doc by lazy { loadVector("datapack.json") }
    private val shipped by lazy { doc["shipped"].obj() }
    private val valid by lazy { doc["valid"].list().map { it.obj() } }
    private val invalid by lazy { doc["invalid"].list().map { it.obj() } }

    private fun Any?.str() = this as String

    private fun rat(v: Any?): Rational = v.list().let { Rational.of(it[0].big().toLong(), it[1].big().toLong()) }

    private fun assertRationalEq(expected: Rational, actual: Rational, what: String) {
        assertEquals(expected.numerator, actual.numerator, "$what numerator")
        assertEquals(expected.denominator, actual.denominator, "$what denominator")
    }

    private fun checkRulesParsed(p: Map<String, Any?>, d: RulesDoc, what: String) {
        val k = d.pack
        assertRationalEq(rat(p["ad_bonus_per_point"]), k.adBonusPerPoint, "$what ad_bonus_per_point")
        assertRationalEq(rat(p["ad_bonus_cap"]), k.adBonusCap, "$what ad_bonus_cap")
        assertRationalEq(rat(p["da_penalty_per_point"]), k.daPenaltyPerPoint, "$what da_penalty_per_point")
        assertRationalEq(rat(p["da_penalty_cap"]), k.daPenaltyCap, "$what da_penalty_cap")
        assertRationalEq(rat(p["hate_bonus"]), k.hateBonus, "$what hate_bonus")
        assertRationalEq(rat(p["luck_bonus"]), k.luckBonus, "$what luck_bonus")
        assertRationalEq(rat(p["half"]), k.half, "$what half")
        for ((name, actual) in listOf("offense" to k.offense, "archery" to k.archery, "armorer" to k.armorer)) {
            val exp = p[name].list()
            assertEquals(exp.size, actual.size, "$what $name size")
            exp.forEachIndexed { i, e -> assertRationalEq(rat(e), actual[i], "$what $name[$i]") }
        }
        assertEquals(p["morale_die"].big().toLong(), k.moraleDie, "$what morale_die")
        assertEquals(p["bad_morale_numerators"].list().map { it.big().toLong() }, k.badMoraleNumerators)
        assertEquals(p["vcmi_bad_morale_numerators"].list().map { it.big().toLong() }, k.vcmiBadMoraleNumerators)
    }

    private fun checkPolicyParsed(p: Map<String, Any?>, d: PolicyDoc) {
        assertEquals(p.keys, d.values.keys)
        for ((k, e) in p) {
            val a = d.values[k]
            when (e) {
                is BigInteger -> assertEquals(e.toLong(), (a as Number).toLong(), k)
                is List<*> -> assertEquals(
                    e.map { row -> row.list().map { it.big().toInt() } },
                    a, k,
                )
                else -> assertEquals(e, a, k)
            }
        }
    }

    private fun checkCreaturesParsed(p: List<Any?>, d: CreaturesDoc) {
        assertEquals(p.size, d.creatures.size)
        p.forEachIndexed { i, x ->
            val e = x.obj()
            val c = d.creatures[i]
            fun n(k: String) = e[k].big().toInt()
            fun b(k: String) = e[k] as Boolean
            val exp = BattleCreature(
                name = e["name"].str(), attack = n("attack"), defense = n("defense"), dmgMin = n("dmg_min"),
                dmgMax = n("dmg_max"), hp = n("hp"), speed = n("speed"), shots = n("shots"),
                flyer = b("flyer"), doubleWide = b("double_wide"), noEnemyRetaliation = b("no_enemy_retaliation"),
                unlimitedRetaliation = b("unlimited_retaliation"), noMeleePenalty = b("no_melee_penalty"),
                noRangePenalty = b("no_range_penalty"), strikesTwice = b("strikes_twice"),
                shootsTwice = b("shoots_twice"), noMorale = b("no_morale"),
                hates = e["hates"].list().map { it.str() },
            )
            assertEquals(exp, c, "creature $i")
        }
    }

    /** Parse [text] as [kind]; returns the content hash (creatures: the pack hash with the shipped rules). */
    private fun parseAndCheck(kind: String, text: String, parsed: Any?, what: String): String {
        return when (kind) {
            "rules" -> Datapack.parseRules(text).also { checkRulesParsed(parsed.obj(), it, what) }.contentHash
            "policy" -> Datapack.parsePolicy(text).also { checkPolicyParsed(parsed.obj(), it) }.contentHash
            "creatures" -> {
                val c = Datapack.parseCreatures(text)
                checkCreaturesParsed(parsed.list(), c)
                Datapack.packHash(Datapack.parseRules(shipped["rules"].obj()["text"].str()), c)
            }
            else -> error("kind $kind")
        }
    }

    @Test
    fun shippedPacks() {
        assertEquals((1L shl 31) - 1, doc["max_int"].big().toLong())
        assertEquals(Datapack.MAX_INT, doc["max_int"].big().toLong())
        for (kind in listOf("rules", "policy", "creatures")) {
            val s = shipped[kind].obj()
            assertEquals(s["hash"].str(), parseAndCheck(kind, s["text"].str(), s["parsed"], kind), kind)
        }
        val pack = Datapack.load(
            shipped["rules"].obj()["text"].str(), shipped["policy"].obj()["text"].str(),
            shipped["creatures"].obj()["text"].str(),
        )
        assertEquals(shipped["pack_hash"].str(), pack.packHash)
        assertEquals(shipped["rules"].obj()["hash"].str(), pack.rules.contentHash)
        assertEquals(shipped["policy"].obj()["hash"].str(), pack.policy.contentHash)
        assertEquals(shipped["canonical_policy"].str(), Canonical.encode(mapOf("battle_policy" to pack.policy.values)).toString(Charsets.US_ASCII))
        assertEquals(listOf("Test Brute", "Test Glider", "Test Pikeman", "Test Slinger"), pack.creatures.creatures.map { it.name })
    }

    @Test
    fun shippedPackBuildsExistingKotlinObjects() {
        val pack = Datapack.load(
            shipped["rules"].obj()["text"].str(), shipped["policy"].obj()["text"].str(),
            shipped["creatures"].obj()["text"].str(),
        )
        // RulesPack drives the real damage code.
        val rules = Rules(pack.rules.pack)
        assertEquals(Rational.of(3L, 1L), pack.rules.pack.adBonusCap)
        assertEquals(Rational.ZERO, rules.attackDefenseFactor(5, 5).increase)
        assertEquals(Rational.of(1L, 4L), rules.attackDefenseFactor(10, 5).increase)
        // BattlePolicyPack: defaults equal the pack values (+ the rules pack bad-morale table).
        val pol = pack.policy.battlePolicyPack(pack.rules).defaultPolicy()
        val m = BattleCodec.policyToMap(pol)
        for ((k, v) in pack.policy.values) {
            if (k == "schema_version") continue
            val got = m[k]
            if (v is Number) assertEquals(v.toLong(), (got as Number).toLong(), k) else assertEquals(v, got, k)
        }
        assertEquals(pack.rules.pack.badMoraleNumerators.map { it.toInt() }, pol.badMoraleTable)
    }

    @Test
    fun validVariantsParseAndHashIdentically() {
        assertTrue(valid.size >= 30, "valid cases: ${valid.size}")
        val groups = HashMap<String, String>()
        for (v in valid) {
            val id = v["id"].str()
            val kind = v["kind"].str()
            val h = parseAndCheck(kind, v["text"].str(), v["parsed"], id)
            assertEquals(v["hash"].str(), h, id)
            if (v["same_hash_as"] == "shipped") {
                assertEquals(shipped[kind].obj()["hash"].str(), h, id)
            } else {
                val g = v["group"].str()
                assertEquals(groups.getOrPut(g) { h }, h, "$id group $g")
                assertTrue(h != shipped[kind].obj()["hash"].str(), "$id must differ from shipped")
            }
        }
    }

    @Test
    fun everyInvalidPackIsRejectedWithPathAndCategory() {
        assertTrue(invalid.size >= 500, "invalid cases: ${invalid.size}")
        val categories = HashSet<String>()
        for (c in invalid) {
            val id = c["id"].str()
            val kind = c["kind"].str()
            val text = c["text"].str()
            val e = assertFailsWith<DatapackError>(id) {
                when (kind) {
                    "rules" -> Datapack.parseRules(text)
                    "policy" -> Datapack.parsePolicy(text)
                    "creatures" -> Datapack.parseCreatures(text)
                    else -> error(kind)
                }
            }
            assertEquals(c["category"].str(), e.category, "$id: ${e.message}")
            if (e.category != "invalid_json") assertEquals(c["message"].str(), e.message, id)
            categories.add(e.category)
        }
        val all = setOf(
            "invalid_json", "duplicate_key", "float", "type", "unknown_key", "missing_key", "range", "length",
            "enum", "schema_version", "table", "distinct", "dmg_order", "duplicate_name", "unknown_creature", "empty",
        )
        assertEquals(all, categories, "every category is exercised")
    }

    @Test
    fun invalidMessagesNameThePath() {
        val e = assertFailsWith<DatapackError> {
            Datapack.parseCreatures("""{"schema_version":1,"creatures":[{"name":"A","attack":1,"defense":1,"dmg_min":1,"dmg_max":1,"hp":0,"speed":1}]}""")
        }
        assertEquals("creatures[0].hp: 0 out of range 1..100000", e.message)
        assertEquals(Category.RANGE, e.category)
    }

    @Test
    fun limitsAndBoolAsInt() {
        val base = shipped["rules"].obj()["text"].str()
        fun withHalf(v: String) = base.replace(Regex("\"half\":\\s*\\[1, 2\\]"), "\"half\": $v")
        Datapack.parseRules(withHalf("[1, 2147483647]"))
        assertEquals("rules.half[1]: 2147483648 out of range 1..2147483647",
            assertFailsWith<DatapackError> { Datapack.parseRules(withHalf("[1, 2147483648]")) }.message)
        assertEquals("rules.half[0]: expected integer, got bool",
            assertFailsWith<DatapackError> { Datapack.parseRules(withHalf("[true, 2]")) }.message)
        assertEquals("rules.json: floats are not allowed (got 1.0)",
            assertFailsWith<DatapackError> { Datapack.parseRules(withHalf("[1.0, 2]")) }.message)
    }
}
