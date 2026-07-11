"""
Right-side emotion wheel panel — light theme, HD image rendering.
Uses Qt.SmoothTransformation and SmoothPixmapTransform render hint
to display the wheel image at maximum quality regardless of panel size.
"""
import os
import math
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QFrame,
    QSizePolicy, QFormLayout, QLineEdit,
)
from PyQt5.QtCore import Qt, QRectF, pyqtSignal, QSize
from PyQt5.QtGui import (
    QPainter, QPixmap, QColor, QPen, QBrush, QFont,
    QTransform, QPainterPath,
)

from app_state import AppState
from constants import breadcrumb, leaf_of, emotion_color

BG      = "#f7f8fb"
SURFACE = "#ffffff"
BORDER  = "#c8cdd6"
TEXT    = "#1a1d23"
TEXT2   = "#5a6072"
PRIMARY = "#3a6fd8"

FIELD_STYLE = f"""
    QLineEdit {{
        background:{SURFACE}; color:{TEXT}; border:1px solid {BORDER};
        border-radius:4px; padding:5px 8px;
        font-size:13px; font-family:Consolas,monospace;
    }}
"""


class WheelWidget(QWidget):
    """
    Displays emotion_wheel.png at full quality.

    Key quality fixes:
      - Stores original full-res QPixmap, never downscales the source
      - Uses QPainter.SmoothPixmapTransform render hint
      - Scales with Qt.SmoothTransformation only at paint time
      - Draws into exact integer-aligned rect to avoid sub-pixel blurring
    """
    emotion_picked = pyqtSignal(float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap_orig: QPixmap | None = None   # original full-res
        self._theta   = 0.0
        self._r       = 0.0
        self._has_pick = False
        self.setMouseTracking(True)
        self.setCursor(Qt.CrossCursor)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(160, 160)

    def load_image(self, path: str):
        if os.path.exists(path):
            self._pixmap_orig = QPixmap(path)   # load once at native resolution
            self.update()
        else:
            self._pixmap_orig = None
            self.update()

    def set_emotion(self, theta: float, r: float):
        self._theta    = theta
        self._r        = r
        self._has_pick = True
        self.update()

    @property
    def theta(self): return self._theta
    @property
    def r(self):     return self._r

    # ── Geometry ──────────────────────────────────────────────────────────────
    def _wheel_rect(self) -> tuple[int, int, int]:
        """Return (x, y, side) of the largest centred square in the widget."""
        side = min(self.width(), self.height()) - 4
        side = max(side, 2)
        x = (self.width()  - side) // 2
        y = (self.height() - side) // 2
        return x, y, side

    def _pos_to_polar(self, px: float, py: float):
        x, y, s = self._wheel_rect()
        cx, cy   = x + s / 2, y + s / 2
        r_px     = s / 2
        dx, dy   = px - cx, py - cy
        r        = math.sqrt(dx * dx + dy * dy) / r_px
        theta    = math.degrees(math.atan2(dy, dx)) % 360
        return (theta+90)%360, r

    def _polar_to_widget(self, theta: float, r: float):
        x, y, s = self._wheel_rect()
        cx, cy   = x + s / 2, y + s / 2
        r_px     = s / 2
        rad      = math.radians((theta-90) % 360)
        return cx + r_px * r * math.cos(rad), cy + r_px * r * math.sin(rad)

    # ── Paint ─────────────────────────────────────────────────────────────────
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHints(
            QPainter.Antialiasing |
            QPainter.SmoothPixmapTransform |
            QPainter.TextAntialiasing
        )
        p.fillRect(self.rect(), QColor(SURFACE))

        wx, wy, ws = self._wheel_rect()

        if self._pixmap_orig is not None and not self._pixmap_orig.isNull():
            # Scale only at paint time; keep original intact
            scaled = self._pixmap_orig.scaled(
                ws, ws,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            # Centre the scaled pixmap in the square
            ox = wx + (ws - scaled.width())  // 2
            oy = wy + (ws - scaled.height()) // 2
            p.drawPixmap(ox, oy, scaled)
        else:
            # Placeholder circle
            p.setPen(QPen(QColor(BORDER), 1.5))
            p.setBrush(QBrush(QColor("#f0f2f5")))
            p.drawEllipse(wx, wy, ws, ws)
            p.setPen(QColor(TEXT2))
            p.setFont(QFont("Segoe UI", 9))
            p.drawText(wx, wy, ws, ws, Qt.AlignCenter,
                       "emotion_wheel.png\nnot found")

        # ── Crosshair indicator ──────────────────────────────────────────────
        if self._has_pick:
            ix, iy = self._polar_to_widget(self._theta, self._r)
            cx, cy  = wx + ws / 2, wy + ws / 2

            # dashed radius line
            p.setPen(QPen(QColor(0, 0, 0, 70), 1, Qt.DashLine))
            p.drawLine(int(cx), int(cy), int(ix), int(iy))

            # white outer ring
            p.setPen(QPen(QColor("#ffffff"), 2.5))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(QRectF(ix - 9, iy - 9, 18, 18))

            # coloured dot
            dot_color = QColor(emotion_color(self._theta))
            p.setPen(QPen(dot_color.darker(160), 1.5))
            p.setBrush(QBrush(dot_color))
            p.drawEllipse(QRectF(ix - 5, iy - 5, 10, 10))

        p.end()

    # ── Mouse ─────────────────────────────────────────────────────────────────
    def mousePressEvent(self, ev):
        if ev.button() == Qt.LeftButton:
            theta, r = self._pos_to_polar(ev.x(), ev.y())
            r = max(0.0, min(1.0, r))
            self._theta, self._r, self._has_pick = theta, r, True
            self.update()
            self.emotion_picked.emit(theta, r)

    def mouseMoveEvent(self, ev):
        if ev.buttons() & Qt.LeftButton:
            theta, r = self._pos_to_polar(ev.x(), ev.y())
            r = max(0.0, min(1.0, r))
            self._theta, self._r, self._has_pick = theta, r, True
            self.update()
            self.emotion_picked.emit(theta, r)


# ── Info panel ────────────────────────────────────────────────────────────────

class EmotionPanel(QWidget):
    emotion_selected = pyqtSignal(float, float)

    def __init__(self, state: AppState, image_path: str, parent=None):
        super().__init__(parent)
        self.state       = state
        self._image_path = image_path
        self.setMinimumWidth(190)
        self.setStyleSheet(f"background:{BG};")
        self._build_ui()
        self._connect()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Section label
        title = QLabel("EMOTION WHEEL")
        title.setStyleSheet(
            f"color:{TEXT2}; font-size:12px; font-weight:700; letter-spacing:2px;"
        )
        layout.addWidget(title)

        # Wheel image — takes all available space
        self._wheel = WheelWidget()
        self._wheel.load_image(self._image_path)
        layout.addWidget(self._wheel, 1)

        def _divider():
            ln = QFrame()
            ln.setFrameShape(QFrame.HLine)
            ln.setStyleSheet(f"color:{BORDER}; margin:0;")
            return ln

        layout.addWidget(_divider())

        # Emotion word (coloured)
        self._lbl_word = QLabel("Neutral")
        self._lbl_word.setStyleSheet(
            f"color:{TEXT}; font-size:25px; font-weight:500;"
        )
        layout.addWidget(self._lbl_word)

        # Breadcrumb  e.g. "Anger → Hostile"
        self._lbl_bread = QLabel("—")
        self._lbl_bread.setStyleSheet(f"color:{TEXT2}; font-size:20px;")
        self._lbl_bread.setWordWrap(True)
        layout.addWidget(self._lbl_bread)

        # θ / r / intensity line
        self._lbl_meta = QLabel("θ —  ·  r —  ·  intensity —")
        self._lbl_meta.setStyleSheet(
            f"color:{TEXT2}; font-size:16px; font-family:Consolas,monospace;"
        )
        layout.addWidget(self._lbl_meta)

        layout.addWidget(_divider())

        # Start / End of selected strip
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignLeft)
        form.setSpacing(6)

        for attr, lbl_text in (("_txt_start", "Start (s)"), ("_txt_end", "End (s)")):
            lbl = QLabel(lbl_text)
            lbl.setStyleSheet(f"color:{TEXT2}; font-size:16px;")
            txt = QLineEdit("—")
            txt.setReadOnly(True)
            txt.setStyleSheet(FIELD_STYLE)
            setattr(self, attr, txt)
            form.addRow(lbl, txt)

        layout.addLayout(form)
        layout.addStretch()

    def _connect(self):
        self._wheel.emotion_picked.connect(self._on_picked)
        self.state.selection_changed.connect(self._on_selection)
        self.state.strips_changed.connect(self._on_selection)

    # ── Slots ─────────────────────────────────────────────────────────────────
    def _on_picked(self, theta: float, r: float):
        self._update_info(theta, r)
        for s in self.state.selected_strips():
            self.state.set_strip_emotion(s.id, theta, r)
            break
        self.emotion_selected.emit(theta, r)

    def _update_info(self, theta: float, r: float):
        leaf  = leaf_of(theta, r)
        color = leaf["core"]["color"]
        word  = leaf["word"]
        bread = breadcrumb(theta, r)
        pct   = int(r * 100)

        self._lbl_word.setText(word)
        self._lbl_word.setStyleSheet(
            f"color:{color}; font-size:25px; font-weight:500;"
        )
        self._lbl_bread.setText(bread)
        self._lbl_meta.setText(
            f"θ {theta:.1f}°  ·  r {r:.2f}  ·  intensity {pct}%"
        )

    def _on_selection(self):
        sel = self.state.selected_strips()
        if sel:
            s = sel[0]
            self._txt_start.setText(f"{s.start:.2f}")
            self._txt_end.setText(f"{s.end:.2f}")
            self._wheel.set_emotion(s.theta, s.r)
            self._update_info(s.theta, s.r)
        else:
            self._txt_start.setText("—")
            self._txt_end.setText("—")
