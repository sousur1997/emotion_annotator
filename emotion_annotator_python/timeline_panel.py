"""
Timeline panel — light theme.
Fixes:
  - Flat strip colors (no gradient), black outline, blue on hover/select
  - Strip creation clamped to free space only
  - Right-click empty area → context menu with Paste at playhead
  - Shift+drag → bounding-box selection
  - Toast on blocked paste/duplicate
"""
import math
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QSizePolicy, QMenu,
)
from PyQt5.QtCore import Qt, QRect, QRectF, pyqtSignal
from PyQt5.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont,
    QLinearGradient, QPainterPath, QFontMetrics,
)
import numpy as np

from strip import Strip
from app_state import AppState

# ── Geometry ──────────────────────────────────────────────────────────────────
RULER_H      = 26
WAVEFORM_H   = 60
STRIP_AREA_Y = RULER_H + WAVEFORM_H + 6
STRIP_H      = 44
HANDLE_W     = 9
SNAP_PX      = 10
MIN_STRIP_DUR= 0.05

# ── Light palette ─────────────────────────────────────────────────────────────
BG_CANVAS   = "#f7f8fb"
BG_RULER    = "#ebeef4"
BG_WAVEFORM = "#f0f4fb"
BORDER      = "#c8cdd6"
TEXT        = "#1a1d23"
TEXT2       = "#5a6072"
PRIMARY     = "#3a6fd8"
PLAYHEAD    = "#e03040"
WAVE_C1     = "#7ab4f5"
WAVE_C2     = "#4a8de0"
GRID_LINE   = "#e0e4ee"
SURFACE     = "#ffffff"
SEL_BOX_BDR = "#3a6fd8"
STRIP_OUTLINE_DEFAULT  = "#000000"   # black border
STRIP_OUTLINE_HOVER    = "#3a6fd8"   # blue border on hover
STRIP_OUTLINE_SELECTED = "#3a6fd8"   # blue border when selected
STRIP_OUTLINE_SEL_W    = 2.5
STRIP_OUTLINE_DEF_W    = 1.2


class TimelineCanvas(QWidget):
    seek_requested  = pyqtSignal(float)
    strip_deleted   = pyqtSignal(list)
    strip_created   = pyqtSignal(object)
    strip_context   = pyqtSignal(str, object)
    canvas_context  = pyqtSignal(object)
    playback_strip  = pyqtSignal(float, float)

    def __init__(self, state: AppState, parent=None):
        super().__init__(parent)
        self.state = state
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.ClickFocus)
        self.setMinimumHeight(STRIP_AREA_Y + STRIP_H + 30)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setStyleSheet(f"background:{BG_CANVAS};")

        self._view_start  = 0.0
        self._px_per_sec  = 100.0
        self._waveform    = None

        self._drag_mode    = None
        self._drag_sid     = None
        self._drag_start_x = 0
        self._drag_start_y = 0
        self._drag_offsets = {}
        self._box_rect     = None
        self._pan_origin_x = 0
        self._pan_vs       = 0.0
        self._preview      = None   # Strip in creation
        self._drag_anchor  = 0.0
        self._hover_sid    = None   # for hover highlight

        state.strips_changed.connect(self.update)
        state.selection_changed.connect(self.update)
        state.position_changed.connect(self.update)

    # ── Public ────────────────────────────────────────────────────────────────
    def set_waveform(self, peaks):
        self._waveform = peaks
        self.update()

    def zoom_to_fit(self):
        if self.state.duration > 0:
            self._px_per_sec = max(1.0, (self.width() - 4) / self.state.duration)
            self._view_start = 0.0
            self.update()

    def set_zoom(self, pps):
        self._px_per_sec = max(1.0, min(pps, 8000.0))
        self._clamp_view()
        self.update()

    @property
    def px_per_sec(self):  return self._px_per_sec
    @property
    def view_start(self):  return self._view_start

    # ── Coords ────────────────────────────────────────────────────────────────
    def _s2p(self, t):  return (t - self._view_start) * self._px_per_sec
    def _p2s(self, x):  return x / self._px_per_sec + self._view_start

    def _clamp_view(self):
        if self.state.duration > 0:
            mx = max(0.0, self.state.duration - self.width() / self._px_per_sec)
            self._view_start = max(0.0, min(self._view_start, mx))
        else:
            self._view_start = 0.0

    # ── Snap ──────────────────────────────────────────────────────────────────
    def _snap(self, t, exclude=()):
        tgts = [0.0, self.state.position]
        if self.state.duration > 0:
            tgts.append(self.state.duration)
        for s in self.state.strips:
            if s.id not in exclude:
                tgts += [s.start, s.end]
        best, bd = t, SNAP_PX / self._px_per_sec
        for tgt in tgts:
            d = abs(tgt - t)
            if d < bd:
                bd, best = d, tgt
        return best

    # ── Free interval for creation ────────────────────────────────────────────
    def _free_interval(self, anchor, drag):
        """Return the free (lo, hi) interval around anchor toward drag."""
        lo = max(0.0, min(anchor, drag))
        hi = min(self.state.duration if self.state.duration > 0 else 1e9,
                 max(anchor, drag))
        for s in self.state.strips:
            if s.end <= lo or s.start >= hi:
                continue
            if s.start <= anchor:
                lo = max(lo, s.end)
            else:
                hi = min(hi, s.start)
        if lo >= hi:
            return anchor, anchor
        return lo, hi

    # ── Overlap clamp for move/resize ─────────────────────────────────────────
    def _clamp_move(self, sid, ns, ne):
        dur = ne - ns
        ns = max(0.0, ns)
        if self.state.duration > 0:
            ne = min(self.state.duration, ns + dur)
            ns = ne - dur
        ns = max(0.0, ns)
        ne = ns + dur
        for s in self.state.strips:
            if s.id == sid:
                continue
            if ns < s.end and ne > s.start:
                mid = (ns + ne) / 2
                if mid < s.start:
                    ne = s.start; ns = ne - dur
                else:
                    ns = s.end;   ne = ns + dur
        ns = max(0.0, ns)
        if self.state.duration > 0:
            ne = min(self.state.duration, ns + dur)
            ns = ne - dur
            ns = max(0.0, ns)
        return ns, ns + dur

    # ── Check if paste/duplicate is possible ──────────────────────────────────
    def can_paste_at(self, position: float, duration: float) -> bool:
        """Return True if a strip of given duration can be placed at position."""
        end = position + duration
        for s in self.state.strips:
            if s.start < end and s.end > position:
                return False
        if self.state.duration > 0 and end > self.state.duration:
            return False
        return True

    # ── Hit test ──────────────────────────────────────────────────────────────
    def _hit(self, x, y):
        if not (STRIP_AREA_Y <= y <= STRIP_AREA_Y + STRIP_H):
            return None, None
        for s in reversed(self.state.strips):
            x1, x2 = self._s2p(s.start), self._s2p(s.end)
            if x1 <= x <= x1 + HANDLE_W:  return s.id, 'left'
            if x2 - HANDLE_W <= x <= x2:  return s.id, 'right'
            if x1 < x < x2:               return s.id, 'body'
        return None, None

    # ── Paint ─────────────────────────────────────────────────────────────────
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(0, 0, w, h, QColor(BG_CANVAS))
        self._paint_ruler(p, w)
        self._paint_waveform(p, w)
        self._paint_strips(p, w)
        self._paint_playhead(p, h)
        if self._box_rect:
            self._paint_box(p)
        p.end()

    def _paint_ruler(self, p, w):
        p.fillRect(0, 0, w, RULER_H, QColor(BG_RULER))
        p.setPen(QPen(QColor(BORDER), 1))
        p.drawLine(0, RULER_H - 1, w, RULER_H - 1)
        dur = self.state.duration
        if dur <= 0:
            return
        vis = w / self._px_per_sec
        if vis <= 0:
            return
        raw = vis / 10
        mag = 10 ** math.floor(math.log10(max(raw, 1e-6)))
        interval = mag
        for m in (1, 2, 5, 10):
            if mag * m >= raw:
                interval = mag * m
                break
        f = QFont("Consolas", 9)
        p.setFont(f)
        t = math.floor(self._view_start / interval) * interval
        while t <= self._view_start + vis + interval:
            x = int(self._s2p(t))
            if 0 <= x <= w:
                p.setPen(QPen(QColor(BORDER), 1))
                p.drawLine(x, RULER_H - 8, x, RULER_H - 1)
                p.setPen(QColor(TEXT2))
                p.drawText(x + 3, RULER_H - 9, self._fmt(t))
            t += interval

    def _paint_waveform(self, p, w):
        top = RULER_H
        p.fillRect(0, top, w, WAVEFORM_H, QColor(BG_WAVEFORM))
        p.setPen(QPen(QColor(GRID_LINE), 1))
        p.drawLine(0, top + WAVEFORM_H - 1, w, top + WAVEFORM_H - 1)

        if self._waveform is None or self.state.duration <= 0:
            p.setPen(QColor(TEXT2))
            p.setFont(QFont("Segoe UI", 10))
            p.drawText(14, top + WAVEFORM_H // 2 + 5,
                       "Waveform will appear here after loading media")
            return

        dur, peaks, n = self.state.duration, self._waveform, len(self._waveform)
        mid  = top + WAVEFORM_H // 2
        half = WAVEFORM_H // 2 - 5

        # flat fill color (no gradient)
        wave_color = QColor(WAVE_C2)
        wave_color.setAlpha(200)
        p.setBrush(QBrush(wave_color))
        p.setPen(Qt.NoPen)

        path = QPainterPath()
        path.moveTo(0, mid)
        for x in range(w):
            t = self._p2s(x)
            if t < 0 or t > dur:
                continue
            idx = max(0, min(n - 1, int(t / dur * n)))
            amp = float(peaks[idx])
            path.lineTo(x, mid - amp * half)
        path.lineTo(w, mid)
        for x in range(w - 1, -1, -1):
            t = self._p2s(x)
            if t < 0 or t > dur:
                continue
            idx = max(0, min(n - 1, int(t / dur * n)))
            amp = float(peaks[idx])
            path.lineTo(x, mid + amp * half)
        path.closeSubpath()
        p.drawPath(path)

    def _paint_strips(self, p, w):
        y = STRIP_AREA_Y
        fm = QFontMetrics(QFont("Segoe UI", 10, QFont.Bold))

        for s in self.state.strips:
            x1 = int(self._s2p(s.start))
            x2 = int(self._s2p(s.end))
            if x2 < 0 or x1 > w:
                continue
            cx1 = max(x1, 0)
            cx2 = min(x2, w)
            if cx2 <= cx1:
                continue

            rect = QRect(cx1, y, cx2 - cx1, STRIP_H)
            sel     = s.id in self.state.selected_ids
            hovered = s.id == self._hover_sid

            # ── Flat fill ────────────────────────────────────────────────────
            base = QColor(s.color)
            # lighten slightly for readability on white bg
            fill = base.lighter(140) if not sel else base.lighter(125)
            p.setBrush(QBrush(fill))

            # ── Border: black default, blue on hover or select ────────────────
            if sel:
                pen = QPen(QColor(STRIP_OUTLINE_SELECTED), STRIP_OUTLINE_SEL_W)
            elif hovered:
                pen = QPen(QColor(STRIP_OUTLINE_HOVER), STRIP_OUTLINE_SEL_W)
            else:
                pen = QPen(QColor(STRIP_OUTLINE_DEFAULT), STRIP_OUTLINE_DEF_W)
            p.setPen(pen)
            p.drawRoundedRect(rect, 4, 4)

            # Blue top accent bar when selected
            if sel:
                p.fillRect(QRect(cx1 + 2, y + 1, cx2 - cx1 - 4, 3),
                           QColor(STRIP_OUTLINE_SELECTED))

            # ── Labels ───────────────────────────────────────────────────────
            avail = cx2 - cx1 - HANDLE_W * 2 - 8
            if avail > 16:
                lx = cx1 + HANDLE_W + 4
                text_color = base.darker(200)

                p.setFont(QFont("Segoe UI", 10, QFont.Bold))
                p.setPen(text_color)
                top_txt = fm.elidedText(s.label, Qt.ElideRight, avail)
                p.drawText(lx, y + 4, avail, STRIP_H // 2,
                           Qt.AlignLeft | Qt.AlignVCenter, top_txt)

                p.setFont(QFont("Segoe UI", 8))
                p.setPen(base.darker(160))
                sub = f"{s.core_name}  ·  {s.intensity_pct}%"
                p.drawText(lx, y + STRIP_H // 2, avail, STRIP_H // 2 - 4,
                           Qt.AlignLeft | Qt.AlignVCenter, sub)

            # ── Resize handle tint ───────────────────────────────────────────
            handle_c = QColor(0, 0, 0, 28)
            p.setBrush(QBrush(handle_c))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(QRect(x1, y, min(HANDLE_W, cx2 - x1), STRIP_H), 3, 3)
            p.drawRoundedRect(QRect(max(x1, x2 - HANDLE_W), y, HANDLE_W, STRIP_H), 3, 3)

        # Creation preview
        if self._preview:
            s = self._preview
            x1 = max(0, int(self._s2p(s.start)))
            x2 = min(w, int(self._s2p(s.end)))
            if x2 > x1:
                p.setBrush(QBrush(QColor(58, 111, 216, 55)))
                p.setPen(QPen(QColor(PRIMARY), 1.5, Qt.DashLine))
                p.drawRoundedRect(QRect(x1, y, x2 - x1, STRIP_H), 4, 4)

    def _paint_playhead(self, p, h):
        x = int(self._s2p(self.state.position))
        if 0 <= x <= self.width():
            p.setPen(QPen(QColor(PLAYHEAD), 2))
            p.drawLine(x, 0, x, h)
            tri = QPainterPath()
            tri.moveTo(x - 7, 0)
            tri.lineTo(x + 7, 0)
            tri.lineTo(x, 13)
            tri.closeSubpath()
            p.fillPath(tri, QColor(PLAYHEAD))

    def _paint_box(self, p):
        r = self._box_rect
        p.setBrush(QBrush(QColor(58, 111, 216, 30)))
        p.setPen(QPen(QColor(SEL_BOX_BDR), 1, Qt.DashLine))
        p.drawRect(int(r.x()), int(r.y()), int(r.width()), int(r.height()))

    # ── Mouse ─────────────────────────────────────────────────────────────────
    def mousePressEvent(self, ev):
        x, y  = ev.x(), ev.y()
        btn   = ev.button()
        shift = bool(ev.modifiers() & Qt.ShiftModifier)
        ctrl  = bool(ev.modifiers() & Qt.ControlModifier)

        if btn == Qt.MiddleButton:
            self._drag_mode    = 'pan'
            self._pan_origin_x = x
            self._pan_vs       = self._view_start
            self.setCursor(Qt.ClosedHandCursor)
            return

        if btn == Qt.RightButton:
            sid, _ = self._hit(x, y)
            if sid:
                if sid not in self.state.selected_ids:
                    self.state.set_selection([sid])
                self.strip_context.emit(sid, ev.globalPos())
            else:
                self.canvas_context.emit(ev.globalPos())
            return

        if btn == Qt.LeftButton:
            # Shift+drag → bounding box regardless of what's under cursor
            if shift:
                self._drag_mode    = 'box'
                self._drag_start_x = x
                self._drag_start_y = y
                self._box_rect     = QRectF(x, y, 0, 0)
                return

            sid, part = self._hit(x, y)

            if sid:
                if ctrl:
                    self.state.toggle_selection(sid)
                else:
                    if sid not in self.state.selected_ids:
                        self.state.set_selection([sid])

                self._drag_start_x = x
                self._drag_sid     = sid

                if part == 'left':
                    self._drag_mode = 'resize_l'
                elif part == 'right':
                    self._drag_mode = 'resize_r'
                else:
                    self._drag_mode = 'move'
                    anchor = self._p2s(x)
                    self._drag_offsets = {
                        s.id: (s.start - anchor, s.end - anchor)
                        for s in self.state.selected_strips()
                    }

            elif y >= STRIP_AREA_Y:
                if self.state.duration <= 0:
                    return
                self.state.clear_selection()
                t0 = self._snap(self._p2s(x))
                t0 = max(0.0, min(t0, self.state.duration))
                self._preview      = Strip(t0, t0, 0.0, 0.0)
                self._drag_mode    = 'create'
                self._drag_start_x = x
                self._drag_anchor  = t0

            else:
                # ruler/waveform → seek
                t = max(0.0, min(self._p2s(x), self.state.duration))
                self.seek_requested.emit(t)
                self._drag_mode = 'seek'
                self.state.clear_selection()

    def mouseMoveEvent(self, ev):
        x, y = ev.x(), ev.y()

        if self._drag_mode == 'pan':
            delta = (self._pan_origin_x - x) / self._px_per_sec
            self._view_start = self._pan_vs + delta
            self._clamp_view()
            self.update()
            return

        if self._drag_mode == 'seek':
            self.seek_requested.emit(max(0.0, min(self._p2s(x), self.state.duration)))
            return

        if self._drag_mode == 'create' and self._preview:
            td = self._snap(self._p2s(x))
            td = max(0.0, min(td, self.state.duration))
            lo, hi = self._free_interval(self._drag_anchor, td)
            self._preview.start = lo
            self._preview.end   = hi
            self.update()
            return

        if self._drag_mode == 'move':
            anchor = self._p2s(x)
            for sid, (os, oe) in self._drag_offsets.items():
                rs = self._snap(anchor + os, exclude=tuple(self.state.selected_ids))
                re = rs + (oe - os)
                ns, ne = self._clamp_move(sid, rs, re)
                s = self.state.strip_by_id(sid)
                if s:
                    s.start, s.end = ns, ne
            self.state.strips_changed.emit()
            return

        if self._drag_mode == 'resize_l':
            s = self.state.strip_by_id(self._drag_sid)
            if s:
                ns = self._snap(self._p2s(x), exclude=(s.id,))
                ns = max(0.0, min(ns, s.end - MIN_STRIP_DUR))
                for o in self.state.strips:
                    if o.id != s.id and o.end <= s.end and o.end > ns:
                        ns = o.end
                s.start = ns
                self.state.strips_changed.emit()
            return

        if self._drag_mode == 'resize_r':
            s = self.state.strip_by_id(self._drag_sid)
            if s:
                ne = self._snap(self._p2s(x), exclude=(s.id,))
                ne = max(s.start + MIN_STRIP_DUR, ne)
                if self.state.duration > 0:
                    ne = min(ne, self.state.duration)
                for o in self.state.strips:
                    if o.id != s.id and o.start >= s.start and o.start < ne:
                        ne = o.start
                s.end = ne
                self.state.strips_changed.emit()
            return

        if self._drag_mode == 'box':
            x0, y0 = self._drag_start_x, self._drag_start_y
            self._box_rect = QRectF(min(x, x0), min(y, y0),
                                    abs(x - x0), abs(y - y0))
            t0 = self._p2s(self._box_rect.left())
            t1 = self._p2s(self._box_rect.right())
            ids = [s.id for s in self.state.strips
                   if s.start < t1 and s.end > t0]
            self.state.set_selection(ids)
            self.update()
            return

        # Hover detection (no drag)
        sid, part = self._hit(x, y)
        if sid != self._hover_sid:
            self._hover_sid = sid
            self.update()
        if part in ('left', 'right'):
            self.setCursor(Qt.SizeHorCursor)
        elif part == 'body':
            self.setCursor(Qt.SizeAllCursor)
        elif y >= STRIP_AREA_Y:
            self.setCursor(Qt.CrossCursor)
        else:
            self.setCursor(Qt.ArrowCursor)

    def mouseReleaseEvent(self, ev):
        if self._drag_mode == 'create':
            if (self._preview and
                    self._preview.end - self._preview.start >= MIN_STRIP_DUR):
                self.strip_created.emit(self._preview)
            self._preview = None

        elif self._drag_mode in ('move', 'resize_l', 'resize_r'):
            self.state._snapshot()

        self._drag_mode = None
        self._box_rect  = None
        self.setCursor(Qt.ArrowCursor)
        self.update()

    def mouseDoubleClickEvent(self, ev):
        sid, _ = self._hit(ev.x(), ev.y())
        if not sid:
            self.state.clear_selection()

    def wheelEvent(self, ev):
        delta = ev.angleDelta().y()
        x = ev.x()
        if ev.modifiers() & Qt.ShiftModifier:
            self._view_start -= delta / self._px_per_sec * 0.5
        else:
            t = self._p2s(x)
            f = 1.15 if delta > 0 else 1 / 1.15
            self._px_per_sec = max(2.0, min(self._px_per_sec * f, 8000.0))
            self._view_start = t - x / self._px_per_sec
        self._clamp_view()
        self.update()

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key_Delete:
            self.strip_deleted.emit(list(self.state.selected_ids))
        elif ev.key() == Qt.Key_P:
            sel = self.state.selected_strips()
            if sel:
                self.playback_strip.emit(sel[0].start, sel[0].end)

    def leaveEvent(self, ev):
        if self._hover_sid:
            self._hover_sid = None
            self.update()

    def _fmt(self, t):
        t = max(0, t)
        m, s = int(t // 60), t % 60
        return f"{m:02d}:{s:05.2f}"


# ─────────────────────────────────────────────────────────────────────────────
class TimelinePanel(QWidget):
    seek_requested    = pyqtSignal(float)
    playback_strip    = pyqtSignal(float, float)
    paste_at_playhead = pyqtSignal()

    def __init__(self, state: AppState, parent=None):
        super().__init__(parent)
        self.state = state
        self._main_win = None   # set by MainWindow after creation
        self.setStyleSheet(f"background:#f0f2f5; border-top:1px solid #c8cdd6;")
        self._build_ui()
        self._connect()

    def set_main_window(self, win):
        self._main_win = win

    def _toast(self, msg, kind="warn"):
        from toast import show_toast, TYPE_WARN, TYPE_ERROR, TYPE_INFO
        kinds = {"warn": TYPE_WARN, "error": TYPE_ERROR, "info": TYPE_INFO}
        parent = self._main_win or self
        show_toast(parent, msg, kinds.get(kind, TYPE_WARN))

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        tb = QWidget()
        tb.setFixedHeight(34)
        tb.setStyleSheet(f"background:#ebeef4; border-bottom:1px solid #c8cdd6;")
        row = QHBoxLayout(tb)
        row.setContentsMargins(8, 2, 8, 2)
        row.setSpacing(6)

        def tbtn(txt, tip):
            b = QPushButton(txt)
            b.setToolTip(tip)
            b.setFixedHeight(24)
            b.setStyleSheet(f"""
                QPushButton {{
                    background:#ffffff; color:#1a1d23; border:1px solid #c8cdd6;
                    border-radius:4px; padding:0 10px; font-size:16px; font-weight:500;
                }}
                QPushButton:hover   {{ background:#dde2ec; }}
                QPushButton:pressed {{ background:#c8cfdf; }}
            """)
            return b

        self._btn_zm  = tbtn("−", "Zoom out  [Scroll]")
        self._btn_zp  = tbtn("+", "Zoom in  [Scroll]")
        self._btn_fit = tbtn("Fit", "Fit all audio into view")
        for b in (self._btn_zm, self._btn_zp, self._btn_fit):
            row.addWidget(b)
        row.addStretch()

        self._lbl_frame = QLabel("Frame 0  ·  00:00.00 / 00:00.00")
        self._lbl_frame.setStyleSheet(
            f"color:{TEXT2}; font-size:16px; font-family:Consolas,monospace;"
        )
        row.addWidget(self._lbl_frame)
        layout.addWidget(tb)

        self.canvas = TimelineCanvas(self.state)
        layout.addWidget(self.canvas, 1)

        self._btn_zm.clicked.connect(lambda: self.canvas.set_zoom(self.canvas.px_per_sec / 1.3))
        self._btn_zp.clicked.connect(lambda: self.canvas.set_zoom(self.canvas.px_per_sec * 1.3))
        self._btn_fit.clicked.connect(self.canvas.zoom_to_fit)

        self.state.position_changed.connect(self._update_label)
        self.state.duration_changed.connect(self._update_label)

    def _connect(self):
        c = self.canvas
        c.seek_requested.connect(self.seek_requested)
        c.strip_deleted.connect(self.state.delete_strips)
        c.strip_created.connect(self.state.add_strip)
        c.strip_context.connect(self._strip_menu)
        c.canvas_context.connect(self._canvas_menu)
        c.playback_strip.connect(self.playback_strip)

    def set_waveform(self, peaks):
        self.canvas.set_waveform(peaks)

    def _update_label(self):
        pos, dur = self.state.position, self.state.duration
        frame = int(pos * 25)
        m1, s1 = int(pos // 60), pos % 60
        m2, s2 = int(dur // 60), dur % 60
        self._lbl_frame.setText(
            f"Frame {frame}  ·  {m1:02d}:{s1:05.2f} / {m2:02d}:{s2:05.2f}"
        )

    # ── Strip right-click menu ────────────────────────────────────────────────
    def _strip_menu(self, sid, gpos):
        menu = self._make_menu()
        a_copy = menu.addAction("📋  Copy                Ctrl+C")
        a_dup  = menu.addAction("⧉   Duplicate          Ctrl+D")
        a_play = menu.addAction("▶   Play strip          P")
        menu.addSeparator()
        a_del  = menu.addAction("✕   Delete              Del")

        act = menu.exec_(gpos)
        if act == a_copy:
            self.state.set_selection([sid])
            self.state.copy_selected()
        elif act == a_dup:
            self.state.set_selection([sid])
            self._do_duplicate()
        elif act == a_play:
            s = self.state.strip_by_id(sid)
            if s:
                self.playback_strip.emit(s.start, s.end)
        elif act == a_del:
            self.state.delete_strips([sid])

    # ── Canvas right-click menu ───────────────────────────────────────────────
    def _canvas_menu(self, gpos):
        menu = self._make_menu()
        has_clip = self.state.clipboard is not None
        a_paste = menu.addAction("📋  Paste at playhead   Ctrl+V")
        a_paste.setEnabled(has_clip)

        act = menu.exec_(gpos)
        if act == a_paste:
            self._do_paste()

    def _make_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background:{SURFACE}; color:{TEXT};
                border:1px solid {BORDER}; border-radius:6px;
                padding:4px 0; font-size:13px;
            }}
            QMenu::item {{ padding:7px 28px 7px 14px; }}
            QMenu::item:selected {{ background:#eef2fb; color:{PRIMARY}; }}
            QMenu::item:disabled {{ color:#aab0be; }}
            QMenu::separator {{ background:{BORDER}; height:1px; margin:4px 0; }}
        """)
        return menu

    # ── Paste / Duplicate with overlap check ─────────────────────────────────
    def _do_paste(self):
        clip = self.state.clipboard
        if not clip:
            return
        pos = self.state.position
        dur = clip.end - clip.start
        if not self.canvas.can_paste_at(pos, dur):
            self._toast(
                f"Cannot paste here — another strip overlaps at {pos:.2f}s.\n"
                "Move the playhead to a free area first.",
                "warn"
            )
            return
        self.state.paste_at(pos)

    def _do_duplicate(self):
        sel = self.state.selected_strips()
        if not sel:
            return
        blocked = []
        for s in sel:
            dur = s.end - s.start
            pos = s.end  # place right after
            if not self.canvas.can_paste_at(pos, dur):
                blocked.append(s.label)
        if blocked:
            names = ", ".join(blocked)
            self._toast(
                f"Cannot duplicate — no free space after the strip.\n"
                f"Blocked: {names}",
                "warn"
            )
            return
        self.state.duplicate_selected()

    # expose for MainWindow shortcuts
    def do_paste(self):    self._do_paste()
    def do_duplicate(self): self._do_duplicate()
