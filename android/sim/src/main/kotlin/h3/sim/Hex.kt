package h3.sim

/**
 * Battle grid geometry and movement: a port of the hex helpers in `battle.py`
 * (docs/specs/battle.md sections 2-3). Int arithmetic only. Python is the oracle
 * (ADR-0004); the vectors in `hex.json` pin every function here (ADR-0007).
 */

/** A hex as (col, row). Natural order is Python tuple order: column first, then row. */
data class HexCell(val col: Int, val row: Int) : Comparable<HexCell> {
    override fun compareTo(other: HexCell): Int =
        if (col != other.col) col.compareTo(other.col) else row.compareTo(other.row)
}

object Hex {
    const val WIDTH = 17
    const val HEIGHT = 11
    const val ATTACKER = 0
    const val DEFENDER = 1

    /** Axial steps in the same order as `_AXIAL_DIRS`. */
    private val AXIAL_DIRS = arrayOf(
        intArrayOf(1, 0), intArrayOf(-1, 0), intArrayOf(0, -1),
        intArrayOf(1, -1), intArrayOf(0, 1), intArrayOf(-1, 1),
    )

    fun inGrid(h: HexCell): Boolean = h.col in 0 until WIDTH && h.row in 0 until HEIGHT

    /** Python: `row_offset == "odd"` selects odd, anything else is even. */
    private fun isOdd(rowOffset: String) = rowOffset == "odd"

    /** `r & 1` for any Int r (two's complement, matches Python for negatives). */
    private fun par(r: Int) = r and 1

    /** (q, r) of an offset hex. */
    fun toAxial(h: HexCell, rowOffset: String = "even"): Pair<Int, Int> {
        val r = h.row
        val half = if (isOdd(rowOffset)) Math.floorDiv(r - par(r), 2) else Math.floorDiv(r + par(r), 2)
        return Pair(h.col - half, r)
    }

    fun fromAxial(q: Int, r: Int, rowOffset: String = "even"): HexCell {
        val half = if (isOdd(rowOffset)) Math.floorDiv(r - par(r), 2) else Math.floorDiv(r + par(r), 2)
        return HexCell(q + half, r)
    }

    /** Sorted in-grid neighbours (at most 6). */
    fun neighbours(h: HexCell, rowOffset: String = "even"): List<HexCell> {
        val (q, r) = toAxial(h, rowOffset)
        val out = ArrayList<HexCell>(6)
        for (d in AXIAL_DIRS) {
            val n = fromAxial(q + d[0], r + d[1], rowOffset)
            if (inGrid(n)) out.add(n)
        }
        out.sort()
        return out
    }

    fun distance(a: HexCell, b: HexCell, rowOffset: String = "even"): Int {
        val (aq, ar) = toAxial(a, rowOffset)
        val (bq, br) = toAxial(b, rowOffset)
        val dq = aq - bq
        val dr = ar - br
        return (Math.abs(dq) + Math.abs(dr) + Math.abs(dq + dr)) / 2
    }

    /** The cell behind a two-hex head: col-1 for the attacker, col+1 for the defender. */
    fun tail(head: HexCell, side: Int, doubleWide: Boolean): HexCell? {
        if (!doubleWide) return null
        return if (side == ATTACKER) HexCell(head.col - 1, head.row) else HexCell(head.col + 1, head.row)
    }

    /** Head first, then tail (if any). */
    fun cellsAt(head: HexCell, side: Int, doubleWide: Boolean): List<HexCell> {
        val t = tail(head, side, doubleWide)
        return if (t == null) listOf(head) else listOf(head, t)
    }

    /** In the grid and, unless edge columns are walkable, not in column 0 or 16. */
    fun playable(h: HexCell, edgeColumnsWalkable: Boolean): Boolean {
        if (!inGrid(h)) return false
        if (edgeColumnsWalkable) return true
        return h.col in 1..(WIDTH - 2)
    }

    /** All cells of a stack at [head] are playable, not blocked and not occupied. */
    fun fits(
        head: HexCell, side: Int, doubleWide: Boolean, edgeColumnsWalkable: Boolean,
        obstacles: Set<HexCell>, occupied: Set<HexCell>,
    ): Boolean {
        for (c in cellsAt(head, side, doubleWide)) {
            if (!playable(c, edgeColumnsWalkable) || c in occupied || c in obstacles) return false
        }
        return true
    }

    /**
     * Cells held by living stacks other than the mover: the caller passes each living
     * stack's cells (dead stacks contribute nothing, see [livingOccupancy]).
     */
    fun livingOccupancy(units: List<Triple<HexCell, Int, Boolean>>, alive: List<Boolean>): Set<HexCell> {
        require(units.size == alive.size)
        val occ = HashSet<HexCell>()
        for (i in units.indices) {
            if (!alive[i]) continue
            val (head, side, dw) = units[i]
            occ.addAll(cellsAt(head, side, dw))
        }
        return occ
    }

    /**
     * Every head the mover can reach this turn, mapped to its path (start excluded, destination
     * last). Iteration order is the Python dict order: walkers in breadth-first discovery order
     * (neighbours visited in sorted order, first discovery wins), flyers in row-major order.
     * The start cell is not itself checked, only the cells it moves to.
     */
    fun reach(
        pos: HexCell, side: Int, doubleWide: Boolean, flyer: Boolean, speed: Int,
        rowOffset: String, edgeColumnsWalkable: Boolean,
        obstacles: Set<HexCell>, occupied: Set<HexCell>,
    ): Map<HexCell, List<HexCell>> {
        val result = LinkedHashMap<HexCell, List<HexCell>>()
        if (flyer) {
            for (r in 0 until HEIGHT) for (c in 0 until WIDTH) {
                val h = HexCell(c, r)
                if (h != pos && distance(pos, h, rowOffset) <= speed &&
                    fits(h, side, doubleWide, edgeColumnsWalkable, obstacles, occupied)
                ) result[h] = listOf(h)
            }
            return result
        }
        val parent = HashMap<HexCell, HexCell?>()
        val dist = LinkedHashMap<HexCell, Int>()
        parent[pos] = null
        dist[pos] = 0
        val queue = ArrayDeque<HexCell>()
        queue.addLast(pos)
        while (queue.isNotEmpty()) {
            val cur = queue.removeFirst()
            val d = dist.getValue(cur)
            if (d >= speed) continue
            for (n in neighbours(cur, rowOffset)) {
                if (n in dist || !fits(n, side, doubleWide, edgeColumnsWalkable, obstacles, occupied)) continue
                dist[n] = d + 1
                parent[n] = cur
                queue.addLast(n)
            }
        }
        for (h in dist.keys) {
            if (h == pos) continue
            val path = ArrayList<HexCell>()
            var x: HexCell = h
            while (x != pos) {
                path.add(x)
                x = parent.getValue(x)!!
            }
            path.reverse()
            result[h] = path
        }
        return result
    }

    /** Sorted head hexes the mover can move to (Python `reachable`). */
    fun reachable(
        pos: HexCell, side: Int, doubleWide: Boolean, flyer: Boolean, speed: Int,
        rowOffset: String, edgeColumnsWalkable: Boolean,
        obstacles: Set<HexCell>, occupied: Set<HexCell>,
    ): List<HexCell> =
        reach(pos, side, doubleWide, flyer, speed, rowOffset, edgeColumnsWalkable, obstacles, occupied)
            .keys.sorted()

    /** True when any cell of [b] neighbours any cell of [a] (Python `_adjacent_cells`). */
    fun adjacentCells(a: List<HexCell>, b: List<HexCell>, rowOffset: String): Boolean {
        val bs = b.toSet()
        return a.any { c -> neighbours(c, rowOffset).any { it in bs } }
    }
}
