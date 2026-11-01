package h3.sim

import java.io.ByteArrayOutputStream
import java.util.Locale
import java.util.zip.DataFormatException
import java.util.zip.Inflater

// Kotlin port of tools/h3re/h3re/lod.py (layout in docs/specs/lod.md).
// Pure JVM: the caller supplies the archive bytes (the app reads them through
// the Storage Access Framework). Integers are Long for the uint32 fields.

const val LOD_HEADER_SIZE = 92
const val LOD_ENTRY_SIZE = 32
const val LOD_NAME_SIZE = 16
const val LOD_MAX_ENTRIES = 1L shl 20

/** Base class for LOD errors. */
open class LodError(message: String) : Exception(message)

/** Malformed, truncated or out-of-bounds archive or member (Python LodFormatError). */
class LodFormatError(message: String) : LodError(message)

/** Unknown member name (Python KeyError). */
class LodKeyError(message: String) : LodError(message)

/** One directory entry. uint32 fields are Long. [packedSize] 0 means stored raw. */
data class LodEntry(
    val name: String,
    val offset: Long,
    val size: Long,
    val type: Long,
    val packedSize: Long,
) {
    val compressed: Boolean get() = packedSize != 0L

    /** Bytes occupied by the payload in the file. */
    val storedSize: Long get() = if (compressed) packedSize else size
}

/** Read-only view of a LOD archive held in memory. */
class LodArchive private constructor(
    private val data: ByteArray,
    private val strict: Boolean,
) {
    // Keyed by upper-cased name. A LinkedHashMap keeps the first-appearance position
    // when a later duplicate replaces the value (last wins).
    private val entries = LinkedHashMap<String, LodEntry>()

    init {
        parse()
    }

    /** Member names in order of first appearance; each name is that of its last duplicate. */
    fun list(): List<String> = entries.values.map { it.name }

    /** Directory information for a member. Throws [LodKeyError] if absent. */
    fun entry(name: String): LodEntry = entries[key(name)] ?: throw LodKeyError("no member $name")

    operator fun contains(name: String): Boolean = entries.containsKey(key(name))

    val size: Int get() = entries.size

    /** Decompressed contents of a member. Throws [LodKeyError] or [LodFormatError]. */
    fun read(name: String): ByteArray {
        val e = entry(name)
        val raw = data.copyOfRange(e.offset.toInt(), (e.offset + e.storedSize).toInt())
        return if (e.compressed) inflateMember(raw, e) else raw
    }

    private fun parse() {
        if (data.size < LOD_HEADER_SIZE) throw LodFormatError("truncated header")
        if (!(data[0] == 'L'.code.toByte() && data[1] == 'O'.code.toByte() &&
                data[2] == 'D'.code.toByte() && data[3] == 0.toByte())
        ) {
            throw LodFormatError("bad magic: not a LOD archive")
        }
        val count = u32(8)
        if (count > LOD_MAX_ENTRIES) throw LodFormatError("entry count $count exceeds limit")
        val dirEnd = LOD_HEADER_SIZE + count * LOD_ENTRY_SIZE
        if (dirEnd > data.size) throw LodFormatError("directory outside file")

        for (index in 0 until count.toInt()) {
            val base = LOD_HEADER_SIZE + index * LOD_ENTRY_SIZE
            val name = decodeName(base)
            if (name.isEmpty()) throw LodFormatError("entry $index has an empty name")
            val entry = LodEntry(
                name = name,
                offset = u32(base + LOD_NAME_SIZE),
                size = u32(base + LOD_NAME_SIZE + 4),
                type = u32(base + LOD_NAME_SIZE + 8),
                packedSize = u32(base + LOD_NAME_SIZE + 12),
            )
            if (entry.offset + entry.storedSize > data.size) {
                throw LodFormatError("entry $name payload is outside the file")
            }
            val k = key(name)
            if (entries.containsKey(k) && strict) throw LodFormatError("duplicate member name $name")
            entries[k] = entry
        }
    }

    /** Little-endian uint32 at [pos], as Long. */
    private fun u32(pos: Int): Long {
        var v = 0L
        for (i in 3 downTo 0) v = (v shl 8) or (data[pos + i].toLong() and 0xFFL)
        return v
    }

    /** Latin-1 name up to the first NUL (Python _decode_name). */
    private fun decodeName(base: Int): String {
        var end = 0
        while (end < LOD_NAME_SIZE && data[base + end] != 0.toByte()) end++
        return String(data, base, end, Charsets.ISO_8859_1)
    }

    companion object {
        /** Parses [data]. Pass [strict] = true to reject duplicate names. */
        fun open(data: ByteArray, strict: Boolean = false): LodArchive = LodArchive(data, strict)

        /** Lookup key: str.upper() on the name, as in lod.py. */
        internal fun key(name: String): String = name.uppercase(Locale.ROOT)

        /**
         * Member-name check used before extraction (Python _check_member_name). Throws
         * [LodFormatError] for names that are not a safe single file name.
         */
        fun checkMemberName(name: String) {
            if (name.isEmpty() || name == "." || name == "..") throw LodFormatError("unsafe member name")
            for (ch in name) {
                if (ch == '/' || ch == '\\' || ch == ':' || ch == '\u0000' || ch.code < 0x20) {
                    throw LodFormatError("unsafe member name")
                }
            }
            // Python str.strip() whitespace among the Latin-1 names: space, NEL, NBSP.
            if (name.first() in PY_SPACE || name.last() in PY_SPACE) {
                throw LodFormatError("unsafe member name")
            }
        }

        private val PY_SPACE = charArrayOf(' ', '\u0085', ' ')
    }
}

/** Python `zlib.decompressobj().decompress(raw, size + 1)` with the same checks. */
private const val INFLATE_CHUNK = 65536

private fun inflateMember(raw: ByteArray, entry: LodEntry): ByteArray {
    // Output stops at size + 1 bytes, so a stream that expands past its declared size is
    // detected without unbounded memory use. Output is produced in chunks, so the declared
    // size never drives an allocation.
    val cap = entry.size + 1
    val inf = Inflater()
    try {
        inf.setInput(raw)
        val out = ByteArrayOutputStream()
        val chunk = ByteArray(minOf(INFLATE_CHUNK.toLong(), cap).toInt())
        var total = 0L
        while (total < cap && !inf.finished()) {
            val want = minOf(chunk.size.toLong(), cap - total).toInt()
            val before = inf.bytesRead
            val n = try {
                inf.inflate(chunk, 0, want)
            } catch (e: DataFormatException) {
                throw LodFormatError("corrupt zlib data: ${e.message}")
            }
            if (inf.needsDictionary()) throw LodFormatError("corrupt zlib data: needs dictionary")
            out.write(chunk, 0, n)
            total += n
            // No output and no input consumed: the stream needs more input (truncated).
            if (n == 0 && inf.bytesRead == before) break
        }
        if (total > entry.size) {
            throw LodFormatError("decompressed data exceeds declared size ${entry.size}")
        }
        if (!inf.finished()) throw LodFormatError("truncated zlib stream")
        if (total != entry.size) {
            throw LodFormatError("decompressed to $total bytes, expected ${entry.size}")
        }
        return out.toByteArray()
    } finally {
        inf.end()
    }
}
