package h3.sim

import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertTrue

private fun unhex(s: String): ByteArray = ByteArray(s.length / 2) { s.substring(it * 2, it * 2 + 2).toInt(16).toByte() }

private fun hexOf(b: ByteArray): String = b.joinToString("") { "%02x".format(it.toInt() and 0xFF) }

/** Error category as named in the vector files. */
private fun categoryOf(e: Throwable): String = when (e) {
    is LodFormatError -> "LodFormatError"
    is LodKeyError -> "KeyError"
    else -> throw e
}

private fun le32(v: Long): ByteArray = ByteArray(4) { ((v shr (8 * it)) and 0xFFL).toByte() }

/** One-member archive for hand-built cases: header, one 32-byte entry, then the payload. */
private fun oneMember(name: String, size: Long, packed: Long, payload: ByteArray, count: Long = 1L): ByteArray {
    val header = "LOD\u0000".toByteArray(Charsets.ISO_8859_1) + le32(200L) + le32(count) + ByteArray(80)
    val nameBytes = name.toByteArray(Charsets.ISO_8859_1).copyOf(16)
    val entry = nameBytes + le32(92L + 32L) + le32(size) + le32(0L) + le32(packed)
    return header + entry + payload
}

class LodTest {
    private fun cases(): List<Any?> = loadVector("lod.json")["cases"].list()

    @Test
    fun conformanceVectorsReplay() {
        val all = cases()
        assertTrue(all.size >= 200, "vector count ${all.size}")
        for (c in all) {
            val o = c.obj()
            val name = o["name"] as String
            val blob = unhex(o["hex"] as String)
            val strict = o["strict"] as Boolean
            val exp = o["expect"].obj()

            if (exp["open"] == "LodFormatError") {
                val e = assertFailsWith<LodError>(name) { LodArchive.open(blob, strict) }
                assertEquals("LodFormatError", categoryOf(e), name)
                continue
            }
            val arc = LodArchive.open(blob, strict)
            assertEquals(exp["list"].list().map { it as String }, arc.list(), name)
            assertEquals(exp["members"].list().size, arc.size, name)
            for (mv in exp["members"].list()) {
                val m = mv.obj()
                val member = m["name"] as String
                val e = arc.entry(member)
                assertEquals(member, e.name, name)
                assertEquals(m["offset"].big().toLong(), e.offset, "$name $member offset")
                assertEquals(m["size"].big().toLong(), e.size, "$name $member size")
                assertEquals(m["type"].big().toLong(), e.type, "$name $member type")
                assertEquals(m["packed"].big().toLong(), e.packedSize, "$name $member packed")
                val lookup = m["lookup"] as String
                if (m.containsKey("error")) {
                    for (query in listOf(member, lookup)) {
                        val err = assertFailsWith<LodError>("$name $query") { arc.read(query) }
                        assertEquals(m["error"] as String, categoryOf(err), "$name $query")
                    }
                } else {
                    val want = m["data"] as String
                    assertEquals(want, hexOf(arc.read(member)), "$name $member")
                    assertEquals(want, hexOf(arc.read(lookup)), "$name $lookup (lookup)")
                }
            }
            val missing = exp["missing"] as String
            val err = assertFailsWith<LodError>("$name missing") { arc.read(missing) }
            assertEquals("KeyError", categoryOf(err), name)
            assertEquals(false, missing in arc, name)
        }
    }

    @Test
    fun everyProperPrefixOfBaseArchiveIsRefused() {
        val base = cases().map { it.obj() }.single { it["name"] == "valid_base_archive" }
        val blob = unhex(base["hex"] as String)
        assertTrue(LodArchive.open(blob).size == 2)
        for (k in 0 until blob.size) {
            val e = assertFailsWith<LodFormatError>("prefix $k") { LodArchive.open(blob.copyOf(k)) }
            assertEquals("LodFormatError", categoryOf(e), "prefix $k")
        }
    }

    @Test
    fun countFieldIsReadAtOffsetEight() {
        val arc = LodArchive.open(oneMember("A.BIN", 1L, 0L, byteArrayOf(9)))
        assertEquals(listOf("A.BIN"), arc.list())
        assertContentEquals(byteArrayOf(9), arc.read("a.bin"))
    }

    @Test
    fun hugeDeclaredSizeDoesNotAllocateAndIsRefused() {
        // Declared size 4 GiB - 1 with a 3-byte stream: refused as a size mismatch, no big buffer.
        val stream = unhex("789c4b4c4a0600024d0127")
        val arc = LodArchive.open(oneMember("BIG.BIN", 0xFFFFFFFFL, stream.size.toLong(), stream))
        val e = assertFailsWith<LodFormatError> { arc.read("BIG.BIN") }
        assertEquals("LodFormatError", categoryOf(e))
    }

    @Test
    fun memberNameCheckRejectsUnsafeNames() {
        for (bad in listOf("", ".", "..", "a/b", "a\\b", "C:x", "a\u0001", " a", "a ", "a\u0085", "a ")) {
            assertFailsWith<LodFormatError>("name [$bad]") { LodArchive.checkMemberName(bad) }
        }
        LodArchive.checkMemberName("DEF_ONE.DEF")
        LodArchive.checkMemberName("a b.txt")
    }

    @Test
    fun missingNameRaisesKeyError() {
        val arc = LodArchive.open(oneMember("A.BIN", 0L, 0L, ByteArray(0)))
        assertFailsWith<LodKeyError> { arc.entry("nope") }
        assertFailsWith<LodKeyError> { arc.read("nope") }
    }
}
