package h3.sim.hero

import h3.sim.Category
import h3.sim.DatapackError
import h3.sim.Pcg32
import h3.sim.RngStreams
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertNotEquals
import kotlin.test.assertTrue

/** A scripted draw source: returns the given values in turn and records the span (`hi`) of every draw. */
private class Script(vararg val values: Long) : HeroDraw {
    val spans = ArrayList<Long>()
    private var next = 0
    override fun range(lo: Long, hi: Long): Long {
        assertEquals(0L, lo)
        spans.add(hi)
        val v = values[next++]
        assertTrue(v in 0 until hi, "scripted draw $v outside 0..$hi")
        return v
    }
}

/** Unit tests of the hero core on the `data/hero_test.json` pack (carried by the vector file as `packs.test`). */
class HeroTest {
    private val text = HeroVectors.packs.getValue("test").str()
    private val content = HeroCore.parseHeroPackText(text, "hero.json")
    private val skills = content.rules.skills
    private val cap = (1L shl 31) - 1

    private fun hero(
        cls: String = "class.warden",
        secondary: List<Pair<String, Long>> = emptyList(),
        policy: HeroPolicy = DEFAULT_POLICY,
        c: HeroContent = content,
        hid: String = "h1",
    ) = HeroCore.createHero(hid, cls, c, secondary, policy)

    private fun resolve(s0: HeroState, rng: Pcg32, events: MutableList<HeroEvent>, pick: (HeroState) -> Int): HeroState {
        var s = s0
        while (s.hero.offer.isNotEmpty()) {
            val r = HeroCore.apply(s, ChooseSkill(s.hero.id, pick(s).toLong()), rng)
            events.addAll(r.events)
            s = r.state
        }
        return s
    }

    private fun gain(s0: HeroState, amount: Long, rng: Pcg32, events: MutableList<HeroEvent> = ArrayList(), pick: (HeroState) -> Int = { 0 }): HeroState {
        val r = HeroCore.apply(s0, GainXP(s0.hero.id, amount), rng)
        events.addAll(r.events)
        return resolve(r.state, rng, events, pick)
    }

    /** The test pack with the warden's primary tables replaced. */
    private fun wardenWith(low: String? = null, high: String? = null): HeroContent {
        var t = text
        if (low != null) t = t.replace("\"primary_low\": [40, 30, 15, 15]", "\"primary_low\": $low")
        if (high != null) t = t.replace("\"primary_high\": [30, 30, 20, 20]", "\"primary_high\": $high")
        assertNotEquals(text, t)
        return HeroCore.parseHeroPackText(t, "hero.json")
    }

    // ---- pack

    @Test
    fun testPackValues() {
        assertEquals(listOf(0L, 1000, 2000, 3200, 4600, 6200, 8000, 10000, 12200, 14700, 17500, 20600), content.rules.xpTable)
        assertEquals(Triple(8, 3, 10), Triple(content.rules.maxSecondary, content.rules.skillLevels, content.rules.primaryHighFromLevel))
        assertEquals(listOf("class.seer", "class.warden"), content.classes.map { it.id })
        val w = HeroCore.findClass(content, "class.warden")!!
        assertEquals(listOf(2, 2, 1, 1), w.startPrimary)
        assertEquals("skill.anvil" to 8L, w.secondaryWeights[0])
        assertEquals(skills, w.secondaryWeights.map { it.first })
        assertTrue(HeroCore.contentHash(content).startsWith("2720746c773ed8ad"))
    }

    @Test
    fun hashIgnoresFormatting() {
        val compact = HeroCore.parseHeroPackText(text.replace(", ", ",").replace(": ", ":"), "x.json")
        assertEquals(HeroCore.contentHash(content), HeroCore.contentHash(compact))
    }

    private fun bad(from: String, to: String, category: String, needle: String) {
        assertTrue(from in text, from)
        val e = assertFailsWith<DatapackError>(from) { HeroCore.parseHeroPackText(text.replace(from, to), "hero.json") }
        assertEquals(category, e.category, from)
        assertTrue(needle in e.message!!, "${e.message} lacks $needle")
    }

    @Test
    fun rejectsBadContent() {
        bad("[0, 1000, 2000, 3200", "[0, 1000, 2000, 2000", Category.TABLE, "strictly increasing")
        bad("[0, 1000, 2000", "[5, 1000, 2000", Category.TABLE, "start at 0")
        bad("\"xp_table\": [0, 1000, 2000, 3200, 4600, 6200, 8000, 10000, 12200, 14700, 17500, 20600]", "\"xp_table\": []", Category.EMPTY, "xp_table")
        bad("\"primary_low\": [10, 15, 40, 35]", "\"primary_low\": [0, 0, 0, 0]", HeroCategory.TOTAL, "positive total")
        bad("\"start_primary\": [0, 1, 2, 2]", "\"start_primary\": [1, 1, 1]", Category.LENGTH, "expected 4")
        bad("\"skill.anvil\": 1, \"skill.brook\": 3", "\"skill.brook\": 3", Category.MISSING_KEY, "missing")
        bad("\"skill.anvil\": 1, \"skill.brook\": 3", "\"skill.anvil\": 1, \"skill.zz\": 1, \"skill.brook\": 3", Category.UNKNOWN_KEY, "unknown")
        bad("\"skill.anvil\": 1, \"skill.brook\": 3", "\"skill.anvil\": -1, \"skill.brook\": 3", Category.RANGE, "out of range")
        bad("\"skill.jade\"]", "\"skill.jade\", \"skill.anvil\"]", Category.DUPLICATE_NAME, "duplicate")
        bad("\"primary_high_from_level\": 10", "\"primary_high_from_level\": 1", Category.RANGE, "out of range")
        bad("\"schema_version\": 1", "\"schema_version\": 9", Category.SCHEMA_VERSION, "schema_version")
        bad("\"max_secondary\": 8", "\"max_secondary\": 8.0", Category.FLOAT, "floats are not allowed")
    }

    @Test
    fun weightTotalsAreCappedAtIntMax() {
        val low = "\"primary_low\": [10, 15, 40, 35]"
        bad(low, "\"primary_low\": [1073741824, 1073741824, 0, 0]", HeroCategory.TOTAL, "weight total 2147483648 above 2147483647")
        bad("\"primary_high\": [20, 20, 30, 30]", "\"primary_high\": [2147483647, 1, 0, 0]", HeroCategory.TOTAL, "weight total")
        bad("\"skill.anvil\": 1, \"skill.brook\": 3", "\"skill.anvil\": 1073741824, \"skill.brook\": 1073741824", HeroCategory.TOTAL, "weight total")
        // exactly 2^31-1 is accepted
        val ok = text.replace(low, "\"primary_low\": [2147483646, 1, 0, 0]")
        assertEquals(listOf(cap - 1, 1L, 0L, 0L), HeroCore.parseHeroPackText(ok, "x").classes[0].primaryLow)
    }

    // ---- xp and levels

    @Test
    fun levelForXp() {
        val t = content.rules.xpTable
        val cases = mapOf(0L to 1, 999L to 1, 1000L to 2, 3199L to 3, 3200L to 4, 14700L to 10, 20599L to 11, 20600L to 12, 1_000_000_000L to 12)
        for ((xp, lv) in cases) assertEquals(lv, HeroCore.levelForXp(xp, t), "$xp")
    }

    @Test
    fun gainWithoutLevelDrawsNothing() {
        val r = HeroCore.apply(hero(), GainXP("h1", 999), NoDraw)
        assertEquals(listOf<HeroEvent>(XPGained("h1", 999, 999)), r.events)
        assertEquals(1 to 999L, r.state.hero.level to r.state.hero.xp)
    }

    @Test
    fun beyondTheTableHoldsTheLevel() {
        val s = gain(hero(), 20600, HeroCore.heroRng(1, "h1"))
        assertEquals(12, s.hero.level)
        val r = HeroCore.apply(s, GainXP("h1", 50000), NoDraw)
        assertEquals(12 to 70600L, r.state.hero.level to r.state.hero.xp)
        assertEquals(listOf<HeroEvent>(XPGained("h1", 50000, 70600)), r.events)
    }

    // ---- level-up

    @Test
    fun oneLevel() {
        val r = HeroCore.apply(hero(secondary = listOf("skill.anvil" to 1L)), GainXP("h1", 1000), HeroCore.heroRng(5, "h1"))
        val h = r.state.hero
        assertEquals(2, h.level)
        assertEquals(2 + 2 + 1 + 1 + 1, h.attack + h.defense + h.power + h.knowledge)
        assertEquals(
            listOf("XPGained", "LevelGained", "PrimaryGained", "SkillOffered"),
            r.events.map { it::class.simpleName },
        )
        assertEquals(SkillOffer("skill.anvil", 2), h.offer[0])
        assertEquals(1, h.offer[1].level)
        assertNotEquals("skill.anvil", h.offer[1].skill)
        assertEquals(SkillOffered("h1", 2, h.offer), r.events.last())
    }

    @Test
    fun primaryTablesSwitchAtLevelTen() {
        val c = wardenWith(low = "[1, 0, 0, 0]", high = "[0, 0, 0, 1]")
        val h = gain(hero(c = c), 20600, HeroCore.heroRng(3, "h1")).hero
        assertEquals(listOf(12, 2 + 8, 2, 1, 1 + 3), listOf(h.level, h.attack, h.defense, h.power, h.knowledge))
    }

    @Test
    fun primaryDrawWalksTheWeightsInOrder() {
        // a hero with nothing to offer draws only the primary skill: 40/30/15/15
        val maxed = skills.take(8).map { it to 3L }
        for ((r, idx) in listOf(0L to 0, 39L to 0, 40L to 1, 69L to 1, 70L to 2, 84L to 2, 85L to 3, 99L to 3)) {
            val script = Script(r)
            val res = HeroCore.apply(hero(secondary = maxed), GainXP("h1", 1000), script)
            assertEquals(listOf(100L), script.spans, "draw $r")
            assertEquals(PrimaryGained("h1", PRIMARY[idx], listOf(3, 3, 2, 2)[idx]), res.events[2], "draw $r")
        }
    }

    @Test
    fun drawOrderIsPrimaryThenUpgradeThenNew() {
        val s = Script(0, 0, 0)
        val r = HeroCore.apply(hero(secondary = listOf("skill.anvil" to 1L)), GainXP("h1", 1000), s)
        // warden primary_low 40+30+15+15, then the upgrade pool (anvil 8), then new skills (all but anvil and jade 0)
        assertEquals(listOf(100L, 8L, 34L), s.spans)
        assertEquals(listOf(SkillOffer("skill.anvil", 2), SkillOffer("skill.brook", 1)), r.state.hero.offer)
    }

    @Test
    fun weightedPairPoolIsUpgradesThenNewSkills() {
        val s = Script(0, 0, 0)
        val r = HeroCore.apply(hero(secondary = listOf("skill.anvil" to 1L), policy = HeroPolicy("weighted_pair")), GainXP("h1", 1000), s)
        assertEquals(listOf(100L, 42L, 34L), s.spans)
        assertEquals(listOf(SkillOffer("skill.anvil", 2), SkillOffer("skill.brook", 1)), r.state.hero.offer)
        // draw 41 is the last weight of the pool (ivy 6: 36..41 of 42)
        val s2 = Script(0, 41, 0)
        val r2 = HeroCore.apply(hero(secondary = listOf("skill.anvil" to 1L), policy = HeroPolicy("weighted_pair")), GainXP("h1", 1000), s2)
        assertEquals(SkillOffer("skill.ivy", 1), r2.state.hero.offer[0])
        assertEquals(SkillOffer("skill.anvil", 2), r2.state.hero.offer[1])
    }

    @Test
    fun skillDrawWalksTheWeightsInSkillOrder() {
        // warden, nothing held: two new skills (other_kind) over anvil 8, brook 6, cinder 2, drift 5, ...
        val expect = listOf(7L to "skill.anvil", 8L to "skill.brook", 13L to "skill.brook", 14L to "skill.cinder",
            15L to "skill.cinder", 16L to "skill.drift")
        for ((r, skill) in expect) {
            val res = HeroCore.apply(hero(), GainXP("h1", 1000), Script(0, r, 0))
            assertEquals(skill, res.state.hero.offer[0].skill, "draw $r")
        }
    }

    @Test
    fun chooseNewAndUpgrade() {
        val rng = HeroCore.heroRng(5, "h1")
        val s = HeroCore.apply(hero(secondary = listOf("skill.anvil" to 1L)), GainXP("h1", 1000), rng).state
        val new = s.hero.offer[1].skill
        val r1 = HeroCore.apply(s, ChooseSkill("h1", 1), rng)
        assertEquals(listOf<HeroEvent>(SkillLearned("h1", new, 1)), r1.events)
        assertEquals(listOf(SecondarySkill("skill.anvil", 1), SecondarySkill(new, 1)), r1.state.hero.secondary)
        assertTrue(r1.state.hero.offer.isEmpty())
        val r2 = HeroCore.apply(s, ChooseSkill("h1", 0), rng)
        assertEquals(listOf(SecondarySkill("skill.anvil", 2)), r2.state.hero.secondary)
    }

    @Test
    fun severalLevelsResolveOneAtATime() {
        val rng = HeroCore.heroRng(9, "h1")
        var s = HeroCore.apply(hero(), GainXP("h1", 4600), rng).state
        assertEquals(2, s.hero.level)
        val levels = arrayListOf(s.hero.level)
        while (s.hero.offer.isNotEmpty()) {
            s = HeroCore.apply(s, ChooseSkill("h1", 0), rng).state
            levels.add(s.hero.level)
        }
        assertEquals(listOf(2, 3, 4, 5, 5), levels)
        assertEquals(4, s.hero.secondary.sumOf { it.level })
    }

    @Test
    fun zeroWeightSkillNeverOffered() {
        val seen = LinkedHashSet<String>()
        for (i in 0 until 40) {
            val events = ArrayList<HeroEvent>()
            gain(hero(hid = "z$i"), 20600, HeroCore.heroRng(2, "z$i"), events) { it.hero.offer.size - 1 }
            for (e in events) if (e is SkillOffered) e.offers.forEach { seen.add(it.skill) }
        }
        assertFalse("skill.jade" in seen)
        assertTrue("skill.anvil" in seen)
    }

    @Test
    fun skillCapAndLevelsHold() {
        for (i in 0 until 20) {
            val s = gain(hero(hid = "c$i"), 20600, HeroCore.heroRng(4, "c$i")) { it.hero.level % it.hero.offer.size }
            val sec = s.hero.secondary
            assertTrue(sec.size <= 8)
            assertEquals(sec.size, sec.map { it.skill }.toSet().size)
            assertTrue(sec.all { it.level in 1..3 })
            assertEquals(11, sec.sumOf { it.level })
        }
    }

    private fun offers(secondary: List<Pair<String, Long>>, policy: HeroPolicy, seed: Long = 1): List<SkillOffer> =
        HeroCore.apply(hero(secondary = secondary, policy = policy), GainXP("h1", 1000), HeroCore.heroRng(seed, "h1")).state.hero.offer

    @Test
    fun fullSlotsOfferUpgradesOnly() {
        val eight = skills.take(8).map { it to 2L }
        val both = offers(eight, DEFAULT_POLICY)
        assertEquals(2, both.size)
        assertTrue(both.all { it.level == 3 })
        assertNotEquals(both[0].skill, both[1].skill)
        val one = offers(eight, HeroPolicy(offerFill = "single"))
        assertEquals(1, one.size)
        assertEquals(3, one[0].level)
    }

    @Test
    fun noSkillsOfferNewOnly() {
        val both = offers(emptyList(), DEFAULT_POLICY)
        assertEquals(listOf(1, 1), both.map { it.level })
        assertNotEquals(both[0].skill, both[1].skill)
        assertEquals(1, offers(emptyList(), HeroPolicy(offerFill = "single")).size)
    }

    @Test
    fun nothingToOffer() {
        val maxed = skills.take(8).map { it to 3L }
        val events = ArrayList<HeroEvent>()
        val s = gain(hero(secondary = maxed), 4600, HeroCore.heroRng(1, "h1"), events)
        assertEquals(5, s.hero.level)
        assertFalse(events.any { it is SkillOffered })
    }

    @Test
    fun weightedPairOffersTwoDistinctKinds() {
        val pol = HeroPolicy(offerMode = "weighted_pair")
        var twoUp = false
        var twoNew = false
        for (seed in 0L until 60) {
            val o = offers(listOf("skill.anvil" to 1L, "skill.hollow" to 1L), pol, seed)
            assertEquals(2, o.size)
            assertNotEquals(o[0].skill, o[1].skill)
            twoUp = twoUp || o.all { it.level == 2 }
            twoNew = twoNew || o.all { it.level == 1 }
            assertEquals(listOf(2, 1), offers(listOf("skill.anvil" to 1L, "skill.hollow" to 1L), DEFAULT_POLICY, seed).map { it.level })
        }
        assertTrue(twoUp && twoNew)
    }

    @Test
    fun policyValidation() {
        assertFailsWith<HeroValueError> { HeroPolicy(offerMode = "x") }
        assertFailsWith<HeroValueError> { HeroPolicy(offerFill = "x") }
    }

    // ---- illegal commands

    @Test
    fun illegalCommandsDrawNothingAndChangeNothing() {
        val rng = HeroCore.heroRng(5, "h1")
        val base = hero()
        val pending = HeroCore.apply(base, GainXP("h1", 1000), rng).state
        val cases = listOf(
            Triple(base, ChooseSkill("h1", 0), "no pending offer"),
            Triple(pending, ChooseSkill("h1", 2), "no such offer 2"),
            Triple(pending, ChooseSkill("h1", -1), "no such offer -1"),
            Triple(pending, ChooseSkill("h1", 1L shl 40), "no such offer 1099511627776"),
            Triple(pending, GainXP("h1", 5), "level-up offer pending: choose a skill first"),
            Triple(base, GainXP("h2", 5), "not hero 'h2'"),
            Triple(base, GainXP("h1", 0), "XP amount must be a positive integer"),
            Triple(base, GainXP("h1", -3), "XP amount must be a positive integer"),
            Triple(base, ChooseSkill("it's", 0), "not hero \"it's\""),
        )
        for ((s, cmd, msg) in cases) {
            val before = HeroCore.canonicalText(s)
            val e = assertFailsWith<IllegalCommand>(msg) { HeroCore.apply(s, cmd, NoDraw) }
            assertEquals(msg, e.message)
            assertEquals(before, HeroCore.canonicalText(s))
        }
    }

    private fun broken(f: (HeroClass) -> HeroClass): HeroState = hero().let { it.copy(classDef = f(it.classDef)) }

    @Test
    fun badClassWeightsRaiseBeforeAnyDraw() {
        val sec = HeroCore.findClass(content, "class.warden")!!.secondaryWeights
        val badSec = sec.mapIndexed { i, p -> if (i < 2) p.first to cap else p }
        val cases = listOf<Pair<(HeroClass) -> HeroClass, String>>(
            { c: HeroClass -> c.copy(primaryLow = listOf(cap, cap, 0, 0)) } to "primary_low",
            { c: HeroClass -> c.copy(primaryLow = listOf(0, 0, 0, 0)) } to "primary_low",
            { c: HeroClass -> c.copy(primaryLow = listOf(1, -1, 1, 1)) } to "primary_low",
            { c: HeroClass -> c.copy(primaryHigh = listOf(1, 1, 1)) } to "primary_high",
            { c: HeroClass -> c.copy(secondaryWeights = badSec) } to "secondary",
            { c: HeroClass -> c.copy(secondaryWeights = sec.dropLast(1)) } to "secondary",
            { c: HeroClass -> c.copy(secondaryWeights = listOf(sec[1], sec[0]) + sec.drop(2)) } to "secondary",
        )
        for ((f, which) in cases) {
            val s = broken(f)
            val before = HeroCore.canonicalText(s)
            val e = assertFailsWith<IllegalCommand>(which) { HeroCore.apply(s, GainXP("h1", 1000), NoDraw) }
            assertEquals("class 'class.warden': bad $which weights", e.message)
            assertEquals(before, HeroCore.canonicalText(s))
        }
        // a pending offer: ChooseSkill that would go on levelling is checked too
        val rng = HeroCore.heroRng(5, "h1")
        val s = HeroCore.apply(hero(), GainXP("h1", 4600), rng).state
        val bad = s.copy(classDef = s.classDef.copy(primaryLow = listOf(cap, cap, 0, 0)))
        assertFailsWith<IllegalCommand> { HeroCore.apply(bad, ChooseSkill("h1", 0), NoDraw) }
    }

    @Test
    fun unusedBadTablesDoNotBlockCommandsThatDrawNothing() {
        val s = broken { it.copy(primaryLow = listOf(0, 0, 0, 0)) }
        assertEquals(999L, HeroCore.apply(s, GainXP("h1", 999), NoDraw).state.hero.xp)
    }

    @Test
    fun totalsExactlyAtTheCapAreDrawable() {
        val s = broken { it.copy(primaryLow = listOf(cap - 1, 1, 0, 0)) }
        val r = HeroCore.apply(s, GainXP("h1", 1000), HeroCore.heroRng(1, "h1"))
        assertEquals(2, r.state.hero.level)
    }

    @Test
    fun xpIsCappedAtIntMax() {
        for (amount in listOf(cap + 1, 1L shl 40, Long.MAX_VALUE)) {
            val e = assertFailsWith<IllegalCommand>("$amount") { HeroCore.apply(hero(), GainXP("h1", amount), NoDraw) }
            assertEquals("XP would exceed 2147483647", e.message)
        }
        val s = hero().let { it.copy(hero = it.hero.copy(xp = cap - 1, level = 12)) }
        assertFailsWith<IllegalCommand> { HeroCore.apply(s, GainXP("h1", 2), NoDraw) }
        assertEquals(cap, HeroCore.apply(s, GainXP("h1", 1), NoDraw).state.hero.xp)
        // exactly the cap from zero is legal and levels the hero through the whole table
        val top = gain(hero(), cap, HeroCore.heroRng(1, "h1"))
        assertEquals(cap to 12, top.hero.xp to top.hero.level)
        assertFailsWith<IllegalCommand> { HeroCore.apply(top, GainXP("h1", 1), NoDraw) }
    }

    @Test
    fun createValidates() {
        fun err(cls: String = "class.seer", sec: List<Pair<String, Long>> = emptyList()) =
            assertFailsWith<HeroValueError> { hero(cls = cls, secondary = sec) }
        assertEquals("unknown hero class 'class.none'", err("class.none").message)
        assertEquals("unknown skill 'skill.zz'", err(sec = listOf("skill.zz" to 1L)).message)
        assertEquals("duplicate skill 'skill.anvil'", err(sec = listOf("skill.anvil" to 1L, "skill.anvil" to 2L)).message)
        assertEquals("bad skill level 4 for 'skill.anvil'", err(sec = listOf("skill.anvil" to 4L)).message)
        assertEquals("bad skill level 0 for 'skill.anvil'", err(sec = listOf("skill.anvil" to 0L)).message)
        assertEquals("at most 8 secondary skills", err(sec = skills.take(9).map { it to 1L }).message)
        assertEquals(8, hero(secondary = skills.take(8).map { it to 1L }).hero.secondary.size)
    }

    @Test
    fun streamNameAndApplyOverloads() {
        val a = HeroCore.heroRng(7, "x")
        val b = RngStreams.derive(7L, "hero:x")
        assertEquals((0 until 3).map { b.nextU32() }, (0 until 3).map { a.nextU32() })
        val r1 = HeroCore.apply(hero(), GainXP("h1", 3000), HeroCore.heroRng(3, "h1"))
        val r2 = HeroCore.apply(hero(), GainXP("h1", 3000), HeroCore.heroRng(3, "h1").asHeroDraw())
        assertEquals(r1, r2)
    }

    @Test
    fun everyStoredFieldIsInTheHash() {
        val base = HeroCore.stateHash(hero())
        assertNotEquals(base, HeroCore.stateHash(hero(policy = HeroPolicy(offerMode = "weighted_pair"))))
        assertNotEquals(base, HeroCore.stateHash(hero(policy = HeroPolicy(offerFill = "single"))))
        assertNotEquals(base, HeroCore.stateHash(hero(cls = "class.seer")))
        assertNotEquals(base, HeroCore.stateHash(hero(hid = "h2")))
        assertNotEquals(base, HeroCore.stateHash(hero(secondary = listOf("skill.anvil" to 1L))))
        assertNotEquals(base, HeroCore.stateHash(hero(c = wardenWith(low = "[41, 30, 15, 15]"))))
        assertNotEquals(base, HeroCore.stateHash(hero(c = wardenWith(high = "[31, 30, 20, 20]"))))
    }

    @Test
    fun pythonTextHelpers() {
        assertEquals("'a'", PyText.repr("a"))
        assertEquals("\"it's\"", PyText.repr("it's"))
        assertEquals("'a\\'b\"c'", PyText.repr("a'b\"c"))
        assertEquals("'a\\\\b\\tc\\nd\\re'", PyText.repr("a\\b\tc\nd\re"))
        assertEquals("'\\x01\\x7f\\xad\\u200b\\ue000é中'", PyText.repr("\u0001\u007f­​é中"))
        assertEquals("'😀'", PyText.repr("😀"))
        for (c in listOf('\t', '\n', '\u000b', '\u000c', '\r', '\u001c', '\u001f', ' ', '\u0085', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', '　')) {
            assertTrue(PyText.isSpace(c), "U+%04X".format(c.code))
        }
        for (c in listOf('a', '​', '᠎', '﻿', '\u0000', '\u001b', '­', '⁠')) {
            assertFalse(PyText.isSpace(c), "U+%04X".format(c.code))
        }
        assertTrue(PyText.blank(""))
        assertTrue(PyText.blank(" 　\u0085"))
        assertFalse(PyText.blank(" ​ "))
    }
}
