package h3.sim

import java.math.BigInteger
import java.nio.ByteBuffer
import java.nio.charset.CharacterCodingException
import java.nio.charset.CodingErrorAction

/**
 * Replay file format (milestone A5; docs/specs/replay.md, docs/specs/conformance-replay.md).
 *
 * A port of `tools/h3re/h3re/replay.py`: [record] builds the canonical bytes (sorted keys, ASCII,
 * SHA-256 checksum over header and body), [verify] parses and replays them and checks every pinned
 * hash. The bytes are identical to Python's for the same scenario, commands and seed, and a file
 * written by either side verifies on the other. Integers and strings only; no floats.
 *
 * The errors keep the Python class names (nested here): [Replay.Malformed], [Replay.Truncated],
 * [Replay.Tampered], [Replay.UnsupportedVersion], [Replay.UnsupportedKind],
 * [Replay.MismatchedRulesPack], [Replay.MismatchedPolicy], [Replay.MismatchedCreatures],
 * [Replay.Diverged]; all are [Replay.ReplayError]. The check order is the one of replay.md section 4.
 */
object Replay {
    const val FORMAT_VERSION = 1
    const val KIND_BATTLE = "battle"
    private val RESERVED_KINDS = listOf("adventure")

    private val HEADER_KEYS = listOf(
        "battle_id", "command_count", "creatures_hash", "final_hash", "format_version", "kind",
        "policy_hash", "rules_hash", "scenario_hash", "seed",
    )
    private val DOC_KEYS = listOf("body", "checksum", "header")
    private val BODY_KEYS = listOf("commands", "scenario")

    open class ReplayError(message: String) : IllegalArgumentException(message)
    class Malformed(message: String) : ReplayError(message)
    class Truncated(message: String) : ReplayError(message)
    class Tampered(message: String) : ReplayError(message)
    class UnsupportedVersion(message: String) : ReplayError(message)
    class UnsupportedKind(message: String) : ReplayError(message)
    class MismatchedRulesPack(message: String) : ReplayError(message)
    class MismatchedPolicy(message: String) : ReplayError(message)
    class MismatchedCreatures(message: String) : ReplayError(message)
    class Diverged(message: String) : ReplayError(message)

    /** Result of [load]: the header, the scenario tree, the command log and the final state. */
    class Loaded(
        val header: Map<String, Any?>,
        val scenario: Map<String, Any?>,
        val commands: List<BattleCommand>,
        val finalState: BattleState,
    )

    // ------------------------------------------------------------------ helpers

    private fun isInt(v: Any?) = v is BigInteger

    private fun canon(v: Any?): ByteArray = Canonical.encode(v)

    private fun sha(b: ByteArray) = Canonical.sha256Hex(b)

    private fun packHashes(packs: Datapack): Map<String, Any?> = linkedMapOf(
        "rules_hash" to packs.rules.contentHash,
        "policy_hash" to packs.policy.contentHash,
        "creatures_hash" to packs.packHash,
    )

    private fun seal(header: Map<String, Any?>, body: Map<String, Any?>): ByteArray {
        val checksum = sha(canon(mapOf("header" to header, "body" to body)))
        return canon(mapOf("header" to header, "body" to body, "checksum" to checksum))
    }

    /** Python `_play`: the battle id and final state after [commands]. */
    private fun play(scenario: Map<String, Any?>, seed: BigInteger, commands: List<BattleCommand>, engine: BattleEngine): Pair<String, BattleState> {
        var state = try {
            Scenario.parseTree(scenario, engine)
        } catch (e: ScenarioError) {
            throw Malformed("bad scenario: ${e.message}")
        }
        val rng = RngStreams.derive(seed, "battle:${state.battleId}").asDrawSource()
        for ((i, cmd) in commands.withIndex()) {
            state = try {
                engine.battle.apply(state, cmd, rng).state
            } catch (e: IllegalCommand) {
                throw Diverged("illegal command at step $i: ${e.message}")
            }
        }
        return Pair(state.battleId, state)
    }

    // ------------------------------------------------------------------- record

    /** Python `replay.record`: replays [commands] on the scenario and returns the canonical file bytes. */
    fun record(
        scenarioJson: String, commands: List<BattleCommand>, seed: BigInteger, packs: Datapack,
        kind: String = KIND_BATTLE,
    ): ByteArray {
        if (kind in RESERVED_KINDS || kind != KIND_BATTLE) throw UnsupportedKind("kind '$kind' is not supported")
        val engine = BattleEngine(packs)
        val tree = try {
            ScenarioJson.parse(scenarioJson, rejectFloats = true)
        } catch (e: ScenarioJson.Syntax) {
            throw Malformed("scenario is not valid JSON: ${e.message}")
        } catch (e: ScenarioJson.Rejected) {
            throw Malformed(e.message ?: "rejected")
        }
        if (tree !is Map<*, *>) throw Malformed("bad scenario: scenario must be an object")
        val scenBytes = canon(tree)
        // Detach and take the canonical key order, as Python's json.loads(_canon(scenario)).
        @Suppress("UNCHECKED_CAST")
        val scen = ScenarioJson.parse(scenBytes.toString(Charsets.US_ASCII), rejectFloats = true) as Map<String, Any?>
        val (battleId, final) = play(scen, seed, commands, engine)
        val header = LinkedHashMap<String, Any?>()
        header["format_version"] = FORMAT_VERSION
        header["kind"] = kind
        header["seed"] = seed
        header["battle_id"] = battleId
        header["scenario_hash"] = sha(scenBytes)
        header["command_count"] = commands.size
        header["final_hash"] = engine.codec.stateHash(final)
        header.putAll(packHashes(packs))
        val body = mapOf("scenario" to scen, "commands" to commands.map { BattleCodec.commandToMap(it) })
        return seal(header, body)
    }

    fun record(
        scenarioJson: String, commands: List<BattleCommand>, seed: Long, packs: Datapack,
        kind: String = KIND_BATTLE,
    ): ByteArray = record(scenarioJson, commands, BigInteger.valueOf(seed), packs, kind)

    // --------------------------------------------------------------------- load

    /** Python's `bytes.decode("utf-8")` with its Truncated/Malformed split for invalid input. */
    private fun decodeUtf8(data: ByteArray): String {
        val dec = Charsets.UTF_8.newDecoder().onMalformedInput(CodingErrorAction.REPORT)
            .onUnmappableCharacter(CodingErrorAction.REPORT)
        val inBuf = ByteBuffer.wrap(data)
        try {
            val out = dec.decode(inBuf)
            return out.toString()
        } catch (e: CharacterCodingException) {
            // Python: the error is a truncation when the bad sequence runs to the end of the data.
            // Java leaves the input position at the start of the bad sequence.
            val rest = data.size - inBuf.position()
            val incompleteTail = rest in 1..3 && isIncompleteSequence(data, inBuf.position())
            if (incompleteTail) throw Truncated("data ends inside a character")
            throw Malformed("not UTF-8 text")
        }
    }

    private fun isIncompleteSequence(d: ByteArray, from: Int): Boolean {
        val b0 = d[from].toInt() and 0xff
        val need = when {
            b0 in 0xC2..0xDF -> 2
            b0 in 0xE0..0xEF -> 3
            b0 in 0xF0..0xF4 -> 4
            else -> return false
        }
        if (d.size - from >= need) return false
        for (k in from + 1 until d.size) if ((d[k].toInt() and 0xC0) != 0x80) return false
        return true
    }

    @Suppress("UNCHECKED_CAST")
    private fun parse(data: ByteArray): Pair<Map<String, Any?>, Map<String, Any?>> {
        val text = decodeUtf8(data)
        if (text.isEmpty()) throw Truncated("file is empty")
        val doc = try {
            ScenarioJson.parse(text, rejectFloats = true)
        } catch (e: ScenarioJson.Rejected) {
            throw Malformed(e.message ?: "rejected")
        } catch (e: ScenarioJson.Syntax) {
            // A cut file is a proper prefix of an object, so it fails inside the document;
            // "Extra data" or a non-object start is garbage instead.
            if (text.startsWith("{") && !e.extraData) throw Truncated("data ends early (at byte ${data.size})")
            throw Malformed("not a replay file: ${e.message}")
        }
        if (doc !is Map<*, *> || doc.keys.filterIsInstance<String>().sortedWith(PackJson.codePointOrder) != DOC_KEYS) {
            throw Malformed("not a replay file: bad top-level keys")
        }
        val header = doc["header"]
        val body = doc["body"]
        val checksum = doc["checksum"]
        if (header !is Map<*, *> || body !is Map<*, *> || checksum !is String) {
            throw Malformed("not a replay file: bad top-level types")
        }
        header as Map<String, Any?>
        body as Map<String, Any?>
        val version = header["format_version"]
        if (!isInt(version)) throw Malformed("header.format_version missing or not an integer")
        if ((version as BigInteger) != BigInteger.valueOf(FORMAT_VERSION.toLong())) {
            throw UnsupportedVersion("format_version $version is not supported (this code reads $FORMAT_VERSION)")
        }
        if (sha(canon(mapOf("header" to header, "body" to body))) != checksum) {
            throw Tampered("checksum does not match header and body")
        }
        if (!data.contentEquals(canon(doc))) throw Malformed("file is not in canonical form")
        if (header.keys.sortedWith(PackJson.codePointOrder) != HEADER_KEYS) throw Malformed("header has missing or unknown keys")
        if (body.keys.sortedWith(PackJson.codePointOrder) != BODY_KEYS) throw Malformed("body has missing or unknown keys")
        val kind = header["kind"]
        if ((kind is String && kind in RESERVED_KINDS) || kind != KIND_BATTLE) throw UnsupportedKind("kind ${kind} is not supported")
        for (k in listOf("seed", "command_count")) if (!isInt(header[k])) throw Malformed("header.$k must be an integer")
        for (k in listOf("battle_id", "scenario_hash", "final_hash", "rules_hash", "policy_hash", "creatures_hash")) {
            if (header[k] !is String) throw Malformed("header.$k must be a string")
        }
        val commands = body["commands"]
        if (commands !is List<*> || !commands.all { it is Map<*, *> }) throw Malformed("body.commands must be a list of objects")
        if (BigInteger.valueOf(commands.size.toLong()) != header["command_count"]) {
            throw Malformed("header.command_count does not match the body")
        }
        val scenario = body["scenario"]
        if (scenario !is Map<*, *> || sha(canon(scenario)) != header["scenario_hash"]) {
            throw Malformed("body.scenario does not match header.scenario_hash")
        }
        return Pair(header, body)
    }

    /** Header of a structurally valid, untampered file (no replay, no pack checks). */
    fun info(data: ByteArray): Map<String, Any?> = LinkedHashMap(parse(data).first)

    /** Python `soak.decode_command("battle", d)` restricted to the battle commands; failures are [Malformed]. */
    private fun decodeCommand(d: Map<String, Any?>): BattleCommand {
        try {
            val m = d.toMutableMap()
            // Attack's from_hex defaults to None, as in the Python dataclass.
            if (m["type"] == "Attack" && "from_hex" !in m) m["from_hex"] = null
            return BattleCodec.parseCommand(m)
        } catch (e: IllegalArgumentException) {
            throw Malformed("body.commands holds an undecodable command")
        }
    }

    /** Python `replay.load`: verifies [data] and returns header, scenario, commands and the final state. */
    @Suppress("UNCHECKED_CAST")
    fun load(data: ByteArray, packs: Datapack): Loaded {
        val (header, body) = parse(data)
        val cur = packHashes(packs)
        if (header["rules_hash"] != cur["rules_hash"]) throw MismatchedRulesPack("rules pack hash differs from this build")
        if (header["policy_hash"] != cur["policy_hash"]) throw MismatchedPolicy("battle policy pack hash differs from this build")
        if (header["creatures_hash"] != cur["creatures_hash"]) throw MismatchedCreatures("creatures pack hash differs from this build")
        val commands = (body["commands"] as List<*>).map { decodeCommand(it as Map<String, Any?>) }
        val engine = BattleEngine(packs)
        val scenario = body["scenario"] as Map<String, Any?>
        val (battleId, final) = play(scenario, header["seed"] as BigInteger, commands, engine)
        if (battleId != header["battle_id"]) throw Malformed("header.battle_id does not match the scenario")
        if (engine.codec.stateHash(final) != header["final_hash"]) throw Diverged("final state hash differs from the recorded one")
        return Loaded(LinkedHashMap(header), scenario, commands, final)
    }

    /** Python `replay.verify`: replays and checks; returns the header or throws a [ReplayError]. */
    fun verify(data: ByteArray, packs: Datapack): Map<String, Any?> = load(data, packs).header
}
