package h3.sim

import java.nio.ByteBuffer
import java.nio.charset.CharacterCodingException
import java.nio.charset.Charset
import java.nio.charset.CodingErrorAction

/**
 * Generic reader for HoMM3-style tab-separated TXT tables. Port of tools/h3re/h3re/txt.py
 * (spec docs/specs/txt.md). Python is the reference oracle; see vectors/txt.json.
 * Bytes in, table out. No floats, no I/O.
 */
enum class TxtErrorCategory(val key: String) {
    HEADER_ROWS("header_rows"),
    TOO_LARGE("too_large"),
    TOO_MANY_LINES("too_many_lines"),
    UNKNOWN_ENCODING("unknown_encoding"),
    DECODE("decode"),
}

class TxtError(val category: TxtErrorCategory, message: String) : IllegalArgumentException(message)

data class TxtTable(val header: List<List<String>>, val rows: List<List<String>>)

object Txt {
    const val MAX_BYTES: Int = 16 * 1024 * 1024
    const val MAX_LINES: Int = 200_000
    const val DEFAULT_ENCODING: String = "cp1252"

    private val ENCODINGS = mapOf(
        "cp1252" to "windows-1252", "windows-1252" to "windows-1252",
        "cp1250" to "windows-1250", "windows-1250" to "windows-1250",
        "cp1251" to "windows-1251", "windows-1251" to "windows-1251",
        "gbk" to "GBK", "cp936" to "GBK",
        "utf-8" to "UTF-8", "utf8" to "UTF-8", "utf_8" to "UTF-8",
    )

    fun parse(
        data: ByteArray,
        headerRows: Int = 0,
        maxBytes: Int = MAX_BYTES,
        maxLines: Int = MAX_LINES,
        encoding: String = DEFAULT_ENCODING,
        lenientNewlines: Boolean = false,
        quoting: Boolean = true,
    ): TxtTable {
        if (headerRows < 0) {
            throw TxtError(TxtErrorCategory.HEADER_ROWS, "header_rows must be a non-negative int, got $headerRows")
        }
        if (data.size > maxBytes) {
            throw TxtError(TxtErrorCategory.TOO_LARGE, "input is ${data.size} bytes, exceeds cap of $maxBytes")
        }
        var off = 0
        if (data.size >= 3 && data[0] == 0xEF.toByte() && data[1] == 0xBB.toByte() && data[2] == 0xBF.toByte()) off = 3
        val cs = try {
            Charset.forName(ENCODINGS[encoding.lowercase()] ?: throw IllegalArgumentException())
        } catch (e: IllegalArgumentException) {
            throw TxtError(TxtErrorCategory.UNKNOWN_ENCODING, "unknown encoding '$encoding'")
        }
        val text = try {
            cs.newDecoder().onMalformedInput(CodingErrorAction.REPORT)
                .onUnmappableCharacter(CodingErrorAction.REPORT)
                .decode(ByteBuffer.wrap(data, off, data.size - off)).toString()
        } catch (e: CharacterCodingException) {
            throw TxtError(TxtErrorCategory.DECODE, "not valid $encoding")
        }
        if (text.isEmpty()) return TxtTable(emptyList(), emptyList())
        val parsed = scan(text, quoting, lenientNewlines, maxLines)
        val h = minOf(headerRows, parsed.size)
        return TxtTable(parsed.subList(0, h), parsed.subList(h, parsed.size))
    }

    // Separator search: returns start of the next TAB / record terminator at or after `from`,
    // or -1. `endOut[0]` receives the end of the match, `endOut[1]` 1 when it is a TAB.
    private fun findSep(text: String, from: Int, lenient: Boolean, out: IntArray): Int {
        val n = text.length
        var p = from
        while (p < n) {
            val c = text[p]
            if (c == '\t') { out[0] = p + 1; out[1] = 1; return p }
            if (c == '\r' && p + 1 < n && text[p + 1] == '\n') { out[0] = p + 2; out[1] = 0; return p }
            if (lenient && c == '\n') { out[0] = p + 1; out[1] = 0; return p }
            p++
        }
        return -1
    }

    private fun scan(text: String, quoting: Boolean, lenient: Boolean, maxLines: Int): List<List<String>> {
        val n = text.length
        val records = ArrayList<List<String>>()
        var fields = ArrayList<String>()
        val m = IntArray(2)
        var i = 0
        while (i < n) {
            val parts = StringBuilder()
            if (quoting && text[i] == '"') {
                var j = i + 1
                while (true) {
                    val k = text.indexOf('"', j)
                    if (k == -1) break // unterminated: field ends at the next TAB / record end
                    if (k + 1 < n && text[k + 1] == '"') { // doubled quote -> literal quote
                        parts.append(text, j, k + 1)
                        j = k + 2
                        continue
                    }
                    parts.append(text, j, k)
                    j = k + 1
                    break
                }
                i = j
            }
            val s = findSep(text, i, lenient, m)
            if (s == -1) {
                parts.append(text, i, n)
                fields.add(parts.toString())
                records.add(fields)
                fields = ArrayList()
                i = n
                break
            }
            parts.append(text, i, s)
            fields.add(parts.toString())
            i = m[0]
            if (m[1] == 0) {
                records.add(fields)
                fields = ArrayList()
                if (records.size > maxLines) {
                    throw TxtError(TxtErrorCategory.TOO_MANY_LINES, "input exceeds cap of $maxLines lines")
                }
            } else if (i >= n) { // trailing TAB at end of data: empty last field
                fields.add("")
                records.add(fields)
                fields = ArrayList()
            }
        }
        if (records.size > maxLines) {
            throw TxtError(TxtErrorCategory.TOO_MANY_LINES, "input has ${records.size} lines, exceeds cap of $maxLines")
        }
        return records
    }
}
