"""
Toast notification — floats in the bottom-right corner of the main window.
Uses no parent widget so it is never clipped inside a child panel.
Position is calculated from the anchor widget's global screen coordinates.
"""
from PyQt5.QtWidgets import QLabel, QWidget, QHBoxLayout, QGraphicsOpacityEffect
from PyQt5.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QPoint
from PyQt5.QtGui import QColor

TYPE_INFO  = "info"
TYPE_WARN  = "warn"
TYPE_ERROR = "error"

_STYLES = {
    TYPE_INFO:  "background:#3a6fd8; color:#fff; border-left:5px solid #1e4aaa;",
    TYPE_WARN:  "background:#e07820; color:#fff; border-left:5px solid #b05810;",
    TYPE_ERROR: "background:#d63040; color:#fff; border-left:5px solid #a02030;",
}

_ICONS = {
    TYPE_INFO:  "ℹ",
    TYPE_WARN:  "⚠",
    TYPE_ERROR: "✕",
}


class Toast(QWidget):
    """
    Frameless top-level popup — never a child of any panel widget.
    anchor_widget: the QMainWindow (or any widget) used only for positioning.
    """
    def __init__(self, anchor_widget, message: str,
                 kind: str = TYPE_WARN, duration_ms: int = 3500):
        # No parent → true top-level, not clipped by any parent widget
        super().__init__(None)
        self._anchor = anchor_widget

        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool                 # no taskbar entry
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_DeleteOnClose)

        # ── Layout ────────────────────────────────────────────────────────────
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(12)

        icon_lbl = QLabel(_ICONS.get(kind, "ℹ"))
        icon_lbl.setStyleSheet(
            "font-size:20px; background:transparent; color:#ffffff;"
        )
        icon_lbl.setFixedWidth(22)
        lay.addWidget(icon_lbl, 0, Qt.AlignTop)

        msg_lbl = QLabel(message)
        msg_lbl.setWordWrap(True)
        msg_lbl.setMaximumWidth(300)
        msg_lbl.setStyleSheet(
            "font-size:13px; font-weight:500; "
            "background:transparent; color:#ffffff; line-height:1.4;"
        )
        lay.addWidget(msg_lbl, 1)

        # ── Styling ───────────────────────────────────────────────────────────
        style = _STYLES.get(kind, _STYLES[TYPE_WARN])
        self.setStyleSheet(
            f"QWidget {{ {style} border-radius:8px; }}"
        )

        # ── Opacity effect for fade-out ───────────────────────────────────────
        self._effect = QGraphicsOpacityEffect(self)
        self._effect.setOpacity(1.0)
        self.setGraphicsEffect(self._effect)

        # ── Size & position ───────────────────────────────────────────────────
        self.setFixedWidth(360)
        self.adjustSize()
        self._reposition()

        # ── Auto-dismiss ──────────────────────────────────────────────────────
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._fade_out)
        self._timer.start(duration_ms)

        self.show()
        self.raise_()

    def _reposition(self):
        """Place toast at bottom-right of anchor widget in screen coordinates."""
        anchor = self._anchor
        if anchor is None:
            return
        # Get the anchor's bottom-right in global screen space
        top_left_global = anchor.mapToGlobal(QPoint(0, 0))
        anchor_right  = top_left_global.x() + anchor.width()
        anchor_bottom = top_left_global.y() + anchor.height()

        x = anchor_right  - self.width()  - 24
        y = anchor_bottom - self.height() - 54   # above status bar
        self.move(x, y)

    def _fade_out(self):
        self._anim = QPropertyAnimation(self._effect, b"opacity")
        self._anim.setDuration(450)
        self._anim.setStartValue(1.0)
        self._anim.setEndValue(0.0)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.finished.connect(self.close)
        self._anim.start()

    def mousePressEvent(self, _):
        """Click toast to dismiss immediately."""
        self._timer.stop()
        self._fade_out()


def show_toast(anchor_widget, message: str,
               kind: str = TYPE_WARN, duration_ms: int = 3500) -> Toast:
    """
    Show a floating toast near the bottom-right of anchor_widget.
    anchor_widget should be the QMainWindow for best results.
    """
    t = Toast(anchor_widget, message, kind, duration_ms)
    return t
