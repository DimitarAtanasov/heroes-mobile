package h3.app

import android.graphics.Bitmap
import android.graphics.Paint
import android.graphics.Rect
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.drawIntoCanvas
import androidx.compose.ui.graphics.nativeCanvas
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.unit.IntSize
import h3.presenter.Atlas
import h3.presenter.BoardGeometry
import h3.presenter.TapState
import h3.presenter.footprints
import h3.presenter.ui.ArtPoint
import h3.presenter.ui.ArtRect
import h3.presenter.ui.BoardArt
import h3.presenter.ui.BoardFit
import h3.presenter.ui.BoardStack
import h3.presenter.ui.StackArt
import h3.presenter.ui.StackRoster
import h3.sim.Hex
import h3.sim.HexCell

private val COL_CELL = Color(0xFF2E3B2F)
private val COL_LINE = Color(0xFF1B241C)
private val COL_OBSTACLE = Color(0xFF6B6B6B)
private val COL_MOVE = Color(0xFF4F9B57)
private val COL_TARGET = Color(0xFFB8453F)
private val COL_PREVIEW = Color(0xFFF2C94C)
private val COL_ACTIVE = Color(0xFFFFFFFF)
private val COL_ATTACKER = Color(0xFF2F6FB5)
private val COL_DEFENDER = Color(0xFFA04A9A)

/**
 * The player's own sprites, decoded at runtime from their game files (never shipped in the repo).
 * [atlas] holds the frame rectangles ([h3.presenter.Atlas.rects], [h3.presenter.Atlas.meta]) and
 * [pages] the page bitmaps, one per atlas page in order, in the premultiplied form the platform
 * expects. A missing page draws the token instead.
 */
class BoardSprites(val atlas: Atlas, val pages: List<Bitmap>)

/**
 * The 17x11 hex board on a Compose Canvas. Hex geometry comes from BoardGeometry (Double math,
 * UI only); sizes of sprites, plates and tokens come from BoardFit through BoardArt (integers in
 * canvas pixels); the only thing sent back to the engine side is an Int [HexCell].
 *
 * Each stack is its idle sprite from [sprites] (mirrored for the defender) when the atlas has one,
 * else a token with a letter. [roster] supplies the rows (count badge, active flag); when it is
 * null a roster without turn order is built from the state.
 */
@Composable
fun BoardView(
    ui: GameUi,
    onTapHex: (HexCell) -> Unit,
    modifier: Modifier = Modifier,
    roster: StackRoster? = null,
    sprites: BoardSprites? = null,
) {
    var boxSize by remember { mutableStateOf(IntSize.Zero) }
    val latestUi by rememberUpdatedState(ui)
    val latestTap by rememberUpdatedState(onTapHex)
    val rows = roster ?: StackRoster.build(ui.state, emptyList())
    Canvas(
        modifier = modifier
            .fillMaxSize()
            .onSizeChanged { boxSize = it }
            .pointerInput(boxSize) {
                detectTapGestures { pos ->
                    if (boxSize.width > 0 && boxSize.height > 0) {
                        val st = latestUi.state
                        val geo = BoardGeometry(boxSize.width, boxSize.height, st.policy.rowOffset)
                        val x = pos.x.toDouble()
                        val y = pos.y.toDouble()
                        val hit = geo.hitTestUnit(x, y, footprints(st))?.head ?: geo.hitTest(x, y)
                        if (hit != null) latestTap(hit)
                    }
                }
            },
    ) {
        if (boxSize.width > 0 && boxSize.height > 0) {
            val geo = BoardGeometry(boxSize.width, boxSize.height, ui.state.policy.rowOffset)
            drawBoard(ui, rows, sprites, geo, BoardFit.fit(boxSize.width, boxSize.height))
        }
    }
}

private fun hexPath(geo: BoardGeometry, h: HexCell): Path {
    val pts = geo.corners(h)
    val p = Path()
    for (i in pts.indices) {
        val x = pts[i].x.toFloat()
        val y = pts[i].y.toFloat()
        if (i == 0) p.moveTo(x, y) else p.lineTo(x, y)
    }
    p.close()
    return p
}

private fun artPoint(geo: BoardGeometry, h: HexCell): ArtPoint {
    val p = geo.center(h)
    return ArtPoint(p.x.toInt(), p.y.toInt())
}

private fun DrawScope.drawBoard(ui: GameUi, roster: StackRoster, sprites: BoardSprites?, geo: BoardGeometry, fit: BoardFit) {
    val st = ui.state
    val obstacles = st.obstacles.map { HexCell(it.first, it.second) }.toSet()
    val stacks = BoardArt.boardStacks(st, roster)
    val targetCells = HashSet<HexCell>()
    for (b in stacks) if (b.row.id in ui.targetIds) targetCells.addAll(b.cells)
    val activeCells = HashSet<HexCell>()
    if (st.winner == null) for (b in stacks) if (b.row.active) activeCells.addAll(b.cells)
    val previewHex: HexCell? = (ui.tap as? TapState.Previewing)?.hex

    for (r in 0 until Hex.HEIGHT) {
        for (c in 0 until Hex.WIDTH) {
            val h = HexCell(c, r)
            val path = hexPath(geo, h)
            val fill = when {
                h in obstacles -> COL_OBSTACLE
                else -> COL_CELL
            }
            drawPath(path, fill)
            if (ui.humanTurn && h in ui.moveHexes) drawPath(path, COL_MOVE.copy(alpha = 0.55f))
            if (ui.humanTurn && h in targetCells) drawPath(path, COL_TARGET.copy(alpha = 0.5f))
            drawPath(path, COL_LINE, style = Stroke(width = 1f))
        }
    }
    for (h in activeCells) drawPath(hexPath(geo, h), COL_ACTIVE, style = Stroke(width = 3f))
    if (previewHex != null) drawPath(hexPath(geo, previewHex), COL_PREVIEW, style = Stroke(width = 5f))

    for (b in stacks) {
        val art = BoardArt.layout(b, b.cells.map { artPoint(geo, it) }, fit, sprites?.atlas)
        val page = art.sprite?.let { sprites?.pages?.getOrNull(it.page) }
        if (page != null) drawSprite(art, page) else drawToken(b, art)
        drawPlate(art)
        if (b.row.active && st.winner == null) drawOutline(art.outline)
    }
}

private fun ArtRect.toRect(): Rect = Rect(left, top, right, bottom)

private fun DrawScope.drawSprite(art: StackArt, page: Bitmap) {
    val s = art.sprite ?: return
    val paint = Paint().apply { isFilterBitmap = true }
    drawIntoCanvas { canvas ->
        val nc = canvas.nativeCanvas
        nc.save()
        if (s.flipX) nc.scale(-1f, 1f, s.pivotX.toFloat(), 0f)
        nc.drawBitmap(page, s.src.toRect(), s.dst.toRect(), paint)
        nc.restore()
    }
}

private fun DrawScope.drawToken(b: BoardStack, art: StackArt) {
    val col = if (b.row.side == Hex.ATTACKER) COL_ATTACKER else COL_DEFENDER
    val radius = art.tokenRadius.toFloat()
    val link = art.tokenLinkWidth.toFloat()
    val centres = art.tokenCentres.map { Offset(it.x.toFloat(), it.y.toFloat()) }
    if (centres.size == 2) drawLine(col, centres[0], centres[1], strokeWidth = link, cap = StrokeCap.Round)
    for (p in centres) drawCircle(col, radius, p)
    drawCircle(Color.Black.copy(alpha = 0.35f), radius, centres[0], style = Stroke(width = 2f))
    val letter = Paint().apply {
        isAntiAlias = true
        textAlign = Paint.Align.CENTER
        color = android.graphics.Color.WHITE
        textSize = art.letterSize.toFloat()
        isFakeBoldText = true
    }
    drawIntoCanvas { canvas -> canvas.nativeCanvas.drawText(art.letter, art.letterX.toFloat(), art.letterBaselineY.toFloat(), letter) }
}

private fun DrawScope.drawPlate(art: StackArt) {
    val plate = art.plate ?: return
    val back = Paint().apply {
        color = android.graphics.Color.BLACK
        alpha = 170
        style = Paint.Style.FILL
    }
    val text = Paint().apply {
        isAntiAlias = true
        textAlign = Paint.Align.CENTER
        color = android.graphics.Color.YELLOW
        textSize = plate.textSize.toFloat()
        isFakeBoldText = true
    }
    drawIntoCanvas { canvas ->
        val r = plate.rect
        canvas.nativeCanvas.drawRect(r.left.toFloat(), r.top.toFloat(), r.right.toFloat(), r.bottom.toFloat(), back)
        canvas.nativeCanvas.drawText(plate.text, plate.textX.toFloat(), plate.textBaselineY.toFloat(), text)
    }
}

private fun DrawScope.drawOutline(r: ArtRect) {
    val line = Paint().apply {
        color = android.graphics.Color.WHITE
        style = Paint.Style.STROKE
        strokeWidth = 3f
    }
    drawIntoCanvas { canvas ->
        canvas.nativeCanvas.drawRect(r.left.toFloat(), r.top.toFloat(), r.right.toFloat(), r.bottom.toFloat(), line)
    }
}
