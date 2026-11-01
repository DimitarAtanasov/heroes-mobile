package h3.app

import android.graphics.Paint
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
import h3.presenter.BoardGeometry
import h3.presenter.TapState
import h3.presenter.footprints
import h3.sim.BattleStack
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

/** Placeholder glyph: first letter of the creature name, skipping the "Test " prefix of the roster. */
fun glyph(name: String): String {
    val n = name.removePrefix("Test ").trim()
    return if (n.isEmpty()) "?" else n.substring(0, 1).uppercase()
}

/**
 * The 17x11 hex board on a Compose Canvas. All geometry comes from BoardGeometry (Double math,
 * UI only); the only thing sent back to the engine side is an Int [HexCell].
 */
@Composable
fun BoardView(ui: GameUi, onTapHex: (HexCell) -> Unit, modifier: Modifier = Modifier) {
    var boxSize by remember { mutableStateOf(IntSize.Zero) }
    val latestUi by rememberUpdatedState(ui)
    val latestTap by rememberUpdatedState(onTapHex)
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
        if (boxSize.width > 0 && boxSize.height > 0) drawBoard(ui, BoardGeometry(boxSize.width, boxSize.height, ui.state.policy.rowOffset))
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

private fun DrawScope.drawBoard(ui: GameUi, geo: BoardGeometry) {
    val st = ui.state
    val obstacles = st.obstacles.map { HexCell(it.first, it.second) }.toSet()
    val alive = st.stacks.filter { it.alive }
    val targetCells = HashSet<HexCell>()
    for (s in alive) if (s.id in ui.targetIds) targetCells.addAll(Hex.cellsAt(HexCell(s.pos.first, s.pos.second), s.side, s.creature.doubleWide))
    val activeCells = HashSet<HexCell>()
    val activeId = st.active
    if (st.winner == null && activeId != null) {
        val a = st.stacks[activeId]
        activeCells.addAll(Hex.cellsAt(HexCell(a.pos.first, a.pos.second), a.side, a.creature.doubleWide))
    }
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

    val radius = (geo.scale * BoardGeometry.CELL_W * 0.36).toFloat()
    val letter = Paint().apply {
        isAntiAlias = true
        textAlign = Paint.Align.CENTER
        color = android.graphics.Color.WHITE
        textSize = radius * 1.1f
        isFakeBoldText = true
    }
    val countPaint = Paint().apply {
        isAntiAlias = true
        textAlign = Paint.Align.CENTER
        color = android.graphics.Color.YELLOW
        textSize = radius * 0.75f
        isFakeBoldText = true
    }
    for (s in alive) drawToken(s, geo, radius, letter, countPaint)
}

private fun DrawScope.drawToken(s: BattleStack, geo: BoardGeometry, radius: Float, letter: Paint, countPaint: Paint) {
    val col = if (s.side == Hex.ATTACKER) COL_ATTACKER else COL_DEFENDER
    val cells = Hex.cellsAt(HexCell(s.pos.first, s.pos.second), s.side, s.creature.doubleWide)
    val centres = cells.map { geo.center(it) }
    if (centres.size == 2) {
        val a = Offset(centres[0].x.toFloat(), centres[0].y.toFloat())
        val b = Offset(centres[1].x.toFloat(), centres[1].y.toFloat())
        drawLine(col, a, b, strokeWidth = radius * 2f, cap = StrokeCap.Round)
    }
    for (p in centres) drawCircle(col, radius, Offset(p.x.toFloat(), p.y.toFloat()))
    val head = Offset(centres[0].x.toFloat(), centres[0].y.toFloat())
    drawCircle(Color.Black.copy(alpha = 0.35f), radius, head, style = Stroke(width = 2f))
    drawIntoCanvas { canvas ->
        canvas.nativeCanvas.drawText(glyph(s.creature.name), head.x, head.y + radius * 0.2f, letter)
        canvas.nativeCanvas.drawText(s.count.toString(), head.x, head.y + radius * 0.95f, countPaint)
    }
}
