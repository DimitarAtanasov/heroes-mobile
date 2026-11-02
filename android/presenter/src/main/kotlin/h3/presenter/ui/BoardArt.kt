package h3.presenter.ui

import h3.presenter.Atlas
import h3.presenter.FrameMeta
import h3.sim.BattleState
import h3.sim.Hex
import h3.sim.HexCell

/** A point in canvas units (the unit of the [BoardFit] the art was laid out with). */
data class ArtPoint(val x: Int, val y: Int)

/** A rectangle in canvas units; [right] and [bottom] are exclusive. */
data class ArtRect(val left: Int, val top: Int, val right: Int, val bottom: Int) {
    val width: Int get() = right - left
    val height: Int get() = bottom - top
}

/**
 * One atlas sprite to draw: copy [src] of atlas page [page] into [dst]. When [flipX] is set the
 * draw is mirrored horizontally about the vertical line x = [pivotX] (the defender, android-app.md
 * 4.2 layer 5: a flip at draw time, never a second texture).
 */
data class SpriteDraw(val page: Int, val src: ArtRect, val dst: ArtRect, val flipX: Boolean, val pivotX: Int)

/** The count plate: a [rect] behind [text], whose baseline is at ([textX], [textBaselineY]). */
data class CountPlate(val rect: ArtRect, val text: String, val textX: Int, val textBaselineY: Int, val textSize: Int)

/** A living stack placed on the board: its roster row, head cell and the cells it covers (head first). */
data class BoardStack(val row: StackRosterRow, val head: HexCell, val cells: List<HexCell>)

/**
 * Everything the board canvas needs to draw one stack, as integers in canvas units. [sprite] is null
 * when no atlas frame exists: draw the token instead (a disc of [tokenRadius] at each of
 * [tokenCentres], joined for a two-hex stack, with [letter] at ([letterX], [letterBaselineY])).
 * [outline] bounds what is drawn (sprite or token) for the active-stack outline; [plate] is null
 * for an empty badge.
 */
data class StackArt(
    val tokenCentres: List<ArtPoint>,
    val tokenRadius: Int,
    /** Stroke width of the bar joining the two discs of a two-hex token. */
    val tokenLinkWidth: Int,
    val letter: String,
    val letterX: Int,
    val letterBaselineY: Int,
    val letterSize: Int,
    val sprite: SpriteDraw?,
    val plate: CountPlate?,
    val outline: ArtRect,
)

/**
 * Pure, integer-only layout of stack art on the board (UI only; never part of a state or a hash).
 * Sizes are board units (a cell is 44 wide) scaled by `BoardFit.unitsToDp`, so every size follows
 * the hex size of the fit. The layout units below are provisional until the sprite placement of
 * android-app.md 4.3 (milestone A9) replaces them.
 */
object BoardArt {
    const val TOKEN_RADIUS_UNITS = 16
    const val LETTER_SIZE_UNITS = 18
    const val LETTER_DROP_UNITS = 6
    const val PLATE_HEIGHT_UNITS = 14
    const val PLATE_BASE_WIDTH_UNITS = 6
    const val PLATE_CHAR_WIDTH_UNITS = 7
    const val PLATE_TEXT_SIZE_UNITS = 12
    const val PLATE_TEXT_DROP_UNITS = 3

    /** Distance from the hex centre down to the bottom edge of the plate and the feet of a sprite. */
    const val BASE_DROP_UNITS = 26

    /**
     * Living stacks of [state] joined with their rows in [roster], sorted by (head row, head col,
     * id) so lower rows are drawn later and overlap upper ones (android-app.md 4.2 layer 5). A
     * stack without a roster row is skipped.
     */
    fun boardStacks(state: BattleState, roster: StackRoster): List<BoardStack> {
        val rows = roster.attackers + roster.defenders
        val out = ArrayList<BoardStack>()
        for (s in state.stacks) {
            if (!s.alive) continue
            val row = rows.firstOrNull { it.id == s.id } ?: continue
            val head = HexCell(s.pos.first, s.pos.second)
            out.add(BoardStack(row, head, Hex.cellsAt(head, s.side, s.creature.doubleWide)))
        }
        return out.sortedWith(compareBy({ it.head.row }, { it.head.col }, { it.row.id }))
    }

    /**
     * Lays out [stack]. [centres] are the canvas centres of [BoardStack.cells], same order (head
     * first); [fit] gives the scale; [atlas] may be null (token fallback).
     */
    fun layout(stack: BoardStack, centres: List<ArtPoint>, fit: BoardFit, atlas: Atlas?): StackArt {
        require(centres.isNotEmpty()) { "a stack covers at least one cell" }
        val row = stack.row
        val head = centres[0]
        var sumX = 0
        for (c in centres) sumX += c.x
        val anchorX = Math.floorDiv(sumX, centres.size)
        val radius = fit.unitsToDp(TOKEN_RADIUS_UNITS)
        val baseY = head.y + fit.unitsToDp(BASE_DROP_UNITS)

        val sprite = spriteDraw(row, fit, atlas, anchorX, baseY)
        var tokenBox = ArtRect(head.x - radius, head.y - radius, head.x + radius, head.y + radius)
        for (c in centres) {
            tokenBox = ArtRect(
                minOf(tokenBox.left, c.x - radius), minOf(tokenBox.top, c.y - radius),
                maxOf(tokenBox.right, c.x + radius), maxOf(tokenBox.bottom, c.y + radius),
            )
        }
        return StackArt(
            tokenCentres = centres,
            tokenRadius = radius,
            tokenLinkWidth = 2 * radius,
            letter = row.fallbackLetter,
            letterX = head.x,
            letterBaselineY = head.y + fit.unitsToDp(LETTER_DROP_UNITS),
            letterSize = fit.unitsToDp(LETTER_SIZE_UNITS),
            sprite = sprite,
            plate = plate(row.countBadge, fit, anchorX, baseY),
            outline = sprite?.dst ?: tokenBox,
        )
    }

    private fun plate(text: String, fit: BoardFit, centreX: Int, bottom: Int): CountPlate? {
        if (text.isEmpty()) return null
        val w = fit.unitsToDp(PLATE_BASE_WIDTH_UNITS + PLATE_CHAR_WIDTH_UNITS * text.length)
        val h = fit.unitsToDp(PLATE_HEIGHT_UNITS)
        val left = centreX - Math.floorDiv(w, 2)
        return CountPlate(
            rect = ArtRect(left, bottom - h, left + w, bottom),
            text = text,
            textX = centreX,
            textBaselineY = bottom - fit.unitsToDp(PLATE_TEXT_DROP_UNITS),
            textSize = fit.unitsToDp(PLATE_TEXT_SIZE_UNITS),
        )
    }

    /**
     * The cropped frame sits inside its full canvas at (offsetX, offsetY); the full canvas is
     * centred on [anchorX] with its bottom edge on [baseY]. Without frame metadata the crop is the
     * whole canvas.
     */
    private fun spriteDraw(row: StackRosterRow, fit: BoardFit, atlas: Atlas?, anchorX: Int, baseY: Int): SpriteDraw? {
        val r = row.spriteRect(atlas) ?: return null
        val meta: FrameMeta? = atlas?.meta?.get(row.idleKey)
        val fullW = fit.unitsToDp(meta?.fullWidth ?: r.w)
        val fullH = fit.unitsToDp(meta?.fullHeight ?: r.h)
        val left = anchorX - Math.floorDiv(fullW, 2) + fit.unitsToDp(meta?.offsetX ?: 0)
        val top = baseY - fullH + fit.unitsToDp(meta?.offsetY ?: 0)
        return SpriteDraw(
            page = r.page,
            src = ArtRect(r.x, r.y, r.x + r.w, r.y + r.h),
            dst = ArtRect(left, top, left + fit.unitsToDp(r.w), top + fit.unitsToDp(r.h)),
            flipX = row.flipX,
            pivotX = anchorX,
        )
    }
}
