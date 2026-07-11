"""
Main application window — Light theme.
Wires FFmpegPlayer-based MediaPanel with waveform worker.
audio_wav_ready signal from MediaPanel is used to feed the waveform
worker the extracted 16 kHz WAV instead of the original media file.
"""
import os
import json
import sys

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout,
    QSplitter, QPushButton, QLabel, QLineEdit,
    QFileDialog, QMessageBox,
    QStatusBar, QCheckBox, QShortcut, QToolBar,
)
from PyQt5.QtCore import Qt, QSize, QTimer
from PyQt5.QtGui import QKeySequence, QColor, QPalette

from app_state import AppState
from media_panel import MediaPanel
from timeline_panel import TimelinePanel
from emotion_panel import EmotionPanel
from waveform_worker import WaveformWorker

SUPPORTED_MEDIA = (
    "Media files (*.mp4 *.avi *.mkv *.mov *.webm "
    "*.mp3 *.wav *.flac *.ogg *.aac *.m4a);;"
    "All files (*)"
)
SUPPORTED_JSON = "JSON files (*.json);;All files (*)"

# ── Palette ───────────────────────────────────────────────────────────────────
BG      = "#f0f2f5"
BG2     = "#e4e7ec"
SURFACE = "#ffffff"
BORDER  = "#c8cdd6"
PRIMARY = "#3a6fd8"
TEXT    = "#1a1d23"
TEXT2   = "#5a6072"

TOOLBAR_STYLE = f"""
QToolBar {{
    background: {BG2};
    border-bottom: 1px solid {BORDER};
    spacing: 5px;
    padding: 4px 8px;
}}
QToolBar::separator {{
    background: {BORDER};
    width: 1px;
    margin: 4px 5px;
}}
"""


def get_asset_path(relative_path):
    """Resolve assets in both development and PyInstaller builds."""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(os.path.dirname(__file__))
    return os.path.join(base_path, relative_path)


def _btn(text, tooltip, accent=False, danger=False):
    b = QPushButton(text)
    b.setToolTip(tooltip)
    if accent:
        b.setStyleSheet(f"""
            QPushButton {{
                background:{PRIMARY}; color:#fff; border:1px solid {PRIMARY};
                border-radius:5px; padding:5px 13px;
                font-size:16px; font-weight:600;
            }}
            QPushButton:hover   {{ background:#2a5bc8; }}
            QPushButton:pressed {{ background:#1e4aaa; }}
            QPushButton:disabled {{
                background:#a0b8e8; border-color:#a0b8e8; color:#e0e8ff;
            }}
        """)
    elif danger:
        b.setStyleSheet(f"""
            QPushButton {{
                background:#ffeaea; color:#d63040; border:1px solid #f0b0b0;
                border-radius:5px; padding:5px 13px;
                font-size:16px; font-weight:500;
            }}
            QPushButton:hover   {{ background:#ffd0d0; }}
            QPushButton:pressed {{ background:#ffbbbb; }}
            QPushButton:disabled {{
                color:#aab0be; background:{BG2}; border-color:{BORDER};
            }}
        """)
    else:
        b.setStyleSheet(f"""
            QPushButton {{
                background:{SURFACE}; color:{TEXT}; border:1px solid {BORDER};
                border-radius:5px; padding:5px 13px;
                font-size:16px; font-weight:500;
            }}
            QPushButton:hover   {{ background:{BG}; }}
            QPushButton:pressed {{ background:{BG2}; }}
            QPushButton:disabled {{
                color:#aab0be; background:{BG2}; border-color:{BORDER};
            }}
        """)
    return b


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Emotion Annotator")
        self.setMinimumSize(1100, 680)
        self.resize(1440, 860)

        # Light palette
        pal = QPalette()
        pal.setColor(QPalette.Window,        QColor(BG))
        pal.setColor(QPalette.WindowText,    QColor(TEXT))
        pal.setColor(QPalette.Base,          QColor(SURFACE))
        pal.setColor(QPalette.AlternateBase, QColor(BG2))
        pal.setColor(QPalette.Text,          QColor(TEXT))
        pal.setColor(QPalette.Button,        QColor(BG2))
        pal.setColor(QPalette.ButtonText,    QColor(TEXT))
        self.setPalette(pal)
        self.setStyleSheet(
            f"background:{BG}; color:{TEXT}; "
            "font-family:'Segoe UI',Arial,sans-serif;"
        )

        self.state = AppState(self)
        self._waveform_worker: WaveformWorker | None = None
        self._wheel_image = get_asset_path("emotion_wheel.png")

        self._build_toolbar()
        self._build_central()
        self._build_statusbar()
        self._connect_signals()
        self._setup_shortcuts()

        # Give timeline panel a ref for toast positioning
        self.timeline_panel.set_main_window(self)

    # ── Toolbar ───────────────────────────────────────────────────────────────
    def _build_toolbar(self):
        tb = QToolBar("Main")
        tb.setMovable(False)
        tb.setStyleSheet(TOOLBAR_STYLE)
        tb.setIconSize(QSize(20, 20))
        self.addToolBar(tb)

        def add(w): tb.addWidget(w)
        def sep():  tb.addSeparator()

        self._btn_load   = _btn("📂  Load Media",  "Load audio or video  [Ctrl+O]", accent=True)
        add(self._btn_load); sep()

        self._btn_undo   = _btn("↩  Undo",   "Undo  [Ctrl+Z]")
        self._btn_redo   = _btn("↪  Redo",   "Redo  [Ctrl+Shift+Z]")
        add(self._btn_undo); add(self._btn_redo); sep()

        self._btn_clean  = _btn("🗑  Clean",  "Remove all strips  [Ctrl+L]")
        self._btn_new    = _btn("✦  New",     "New project  [Ctrl+N]")
        self._btn_delete = _btn("✕  Delete",  "Delete selected  [Del]", danger=True)
        add(self._btn_clean); add(self._btn_new); add(self._btn_delete); sep()

        self._chk_loop = QCheckBox("🔁  Loop")
        self._chk_loop.setStyleSheet(
            f"color:{TEXT}; font-size:16px; padding:0 4px; spacing:5px;"
        )
        add(self._chk_loop); sep()

        self._lbl_media = QLabel("No media loaded")
        self._lbl_media.setStyleSheet(
            f"color:{TEXT2}; font-size:16px; padding:0 4px;"
        )
        add(self._lbl_media)

        self._txt_json = QLineEdit()
        self._txt_json.setPlaceholderText("Save path (.json)…")
        self._txt_json.setFixedWidth(240)
        self._txt_json.setStyleSheet(f"""
            QLineEdit {{
                background:{SURFACE}; color:{TEXT}; border:1px solid {BORDER};
                border-radius:4px; padding:4px 8px;
                font-size:12px; font-family:Consolas,monospace;
            }}
            QLineEdit:focus {{ border-color:{PRIMARY}; }}
        """)
        add(self._txt_json)

        self._btn_save   = _btn("💾  Save",        "Save JSON  [Ctrl+S]", accent=True)
        self._btn_import = _btn("📥  Import JSON", "Import JSON annotations")
        add(self._btn_save); add(self._btn_import)

        # Wire toolbar buttons
        self._btn_load.clicked.connect(self._load_media)
        self._btn_undo.clicked.connect(self._undo)
        self._btn_redo.clicked.connect(self._redo)
        self._btn_clean.clicked.connect(self._clean_strips)
        self._btn_new.clicked.connect(self._new_project)
        self._btn_delete.clicked.connect(self._delete_selected)
        self._btn_save.clicked.connect(self._save_json)
        self._btn_import.clicked.connect(self._import_json)
        self._txt_json.editingFinished.connect(
            lambda: setattr(self.state, 'json_path', self._txt_json.text())
        )

        self._update_undo_redo()

    # ── Central layout ────────────────────────────────────────────────────────
    def _build_central(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        splitter_style = f"""
            QSplitter::handle       {{ background:{BORDER}; }}
            QSplitter::handle:hover {{ background:{PRIMARY}; }}
        """
        h_split = QSplitter(Qt.Horizontal)
        h_split.setStyleSheet(splitter_style + "QSplitter::handle { width:3px; }")

        v_split = QSplitter(Qt.Vertical)
        v_split.setStyleSheet(splitter_style + "QSplitter::handle { height:3px; }")

        self.media_panel    = MediaPanel(self.state)
        self.timeline_panel = TimelinePanel(self.state)
        self.emotion_panel  = EmotionPanel(self.state, self._wheel_image)

        v_split.addWidget(self.media_panel)
        v_split.addWidget(self.timeline_panel)
        v_split.setSizes([400, 260])
        v_split.setCollapsible(0, False)
        v_split.setCollapsible(1, False)

        h_split.addWidget(v_split)
        h_split.addWidget(self.emotion_panel)
        h_split.setSizes([1060, 500])
        h_split.setCollapsible(1, False)

        root.addWidget(h_split, 1)

    # ── Status bar ────────────────────────────────────────────────────────────
    def _build_statusbar(self):
        sb = QStatusBar()
        sb.setStyleSheet(
            f"background:{BG2}; color:{TEXT2}; font-size:16px; "
            f"border-top:1px solid {BORDER};"
        )
        self.setStatusBar(sb)
        self._status = sb
        self._status.showMessage("Ready  ·  Ctrl+O to load media")

    # ── Signals ───────────────────────────────────────────────────────────────
    def _connect_signals(self):
        self.timeline_panel.seek_requested.connect(self.media_panel.seek)
        self.timeline_panel.playback_strip.connect(self.media_panel.play_range)
        self._chk_loop.toggled.connect(self.media_panel.set_loop)

        self.state.strips_changed.connect(self._update_undo_redo)
        self.state.save_state_changed.connect(self._update_title)
        self.state.media_changed.connect(self._on_media_changed)
        self.state.duration_changed.connect(self._on_duration_changed)

        # Use extracted WAV for waveform (works for mp3/mp4/all formats)
        self.media_panel.audio_wav_ready.connect(self._start_waveform)

        # Paste / duplicate routed through timeline panel (overlap-checked)
        self.timeline_panel.paste_at_playhead.connect(
            self.timeline_panel.do_paste
        )

    def _setup_shortcuts(self):
        def sc(key, fn):
            QShortcut(QKeySequence(key), self, fn)

        sc("Ctrl+O",       self._load_media)
        sc("Ctrl+Z",       self._undo)
        sc("Ctrl+Shift+Z", self._redo)
        sc("Ctrl+S",       self._save_json)
        sc("Ctrl+N",       self._new_project)
        sc("Ctrl+L",       self._clean_strips)
        sc("Delete",       self._delete_selected)
        sc("Ctrl+C",       self.state.copy_selected)
        sc("Ctrl+D",       self.timeline_panel.do_duplicate)
        sc("Ctrl+V",       self.timeline_panel.do_paste)
        sc("Space",        self.media_panel.toggle_play)
        sc("Left",         self.media_panel.prev_frame)
        sc("Right",        self.media_panel.next_frame)
        sc("Shift+Left",   self.media_panel.jump_to_start)
        sc("Shift+Right",  self.media_panel.jump_to_end)

    # ── File actions ──────────────────────────────────────────────────────────
    def _load_media(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Media", "", SUPPORTED_MEDIA
        )
        if not path:
            return
        base      = os.path.splitext(path)[0]
        json_path = base + ".json"

        self.state.set_media(path, json_path)
        self._lbl_media.setText(f"📄 {os.path.basename(path)}")
        self._txt_json.setText(json_path)

        # Load into player — waveform will start once audio WAV is extracted
        self.media_panel.load_media(path)
        self._status.showMessage(
            f"Loading: {os.path.basename(path)}  ·  Extracting audio…"
        )

    def _start_waveform(self, wav_path: str):
        """Called with the extracted temp WAV path — always decodable."""
        if self._waveform_worker and self._waveform_worker.isRunning():
            self._waveform_worker.cancel()
            self._waveform_worker.wait(500)

        self.timeline_panel.set_waveform(None)
        self._status.showMessage("Generating waveform…")

        worker = WaveformWorker(wav_path)
        worker.finished.connect(self._on_waveform_ready)
        worker.error.connect(
            lambda e: self._status.showMessage(f"Waveform error: {e}")
        )
        self._waveform_worker = worker
        worker.start()

    def _on_waveform_ready(self, peaks):
        if peaks is not None:
            self.timeline_panel.set_waveform(peaks)
            self._status.showMessage(
                f"Ready  ·  {os.path.basename(self.state.media_path)}"
            )
        else:
            self._status.showMessage(
                "Waveform unavailable — check ffmpeg is installed"
            )

    def _on_media_changed(self, path):
        self._update_title()

    def _on_duration_changed(self, dur):
        QTimer.singleShot(200, self.timeline_panel.canvas.zoom_to_fit)

    # ── JSON ──────────────────────────────────────────────────────────────────
    def _save_json(self):
        path = self.state.json_path
        if not path:
            path, _ = QFileDialog.getSaveFileName(
                self, "Save JSON", "", SUPPORTED_JSON
            )
            if not path:
                return
            self.state.json_path = path
            self._txt_json.setText(path)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.state.to_dict(), f, indent=2)
            self.state.mark_saved()
            self._status.showMessage(f"Saved: {path}")
        except Exception as e:
            QMessageBox.critical(self, "Save error", str(e))

    def _import_json(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import JSON", "", SUPPORTED_JSON
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.state.load_dict(data)
            self.state.json_path = path
            self._txt_json.setText(path)
            self._status.showMessage(f"Imported: {path}")
        except Exception as e:
            QMessageBox.critical(self, "Import error", str(e))

    # ── Edit actions ──────────────────────────────────────────────────────────
    def _undo(self):
        self.state.undo()
        self._update_undo_redo()

    def _redo(self):
        self.state.redo()
        self._update_undo_redo()

    def _clean_strips(self):
        if self.state.strips:
            if QMessageBox.question(
                self, "Clean strips",
                "Remove all annotation strips? Media will remain.",
                QMessageBox.Yes | QMessageBox.No,
            ) == QMessageBox.Yes:
                self.state.clear_strips()

    def _new_project(self):
        if not self.state.is_saved and self.state.strips:
            r = QMessageBox.question(
                self, "Unsaved changes",
                "Save before starting a new project?",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
            )
            if r == QMessageBox.Cancel:
                return
            if r == QMessageBox.Yes:
                self._save_json()
        self.state.clear_strips()
        self.state.set_media("", "")
        self.state.set_duration(0.0)
        self.timeline_panel.set_waveform(None)
        self._lbl_media.setText("No media loaded")
        self._txt_json.setText("")
        self._status.showMessage("New project  ·  Ctrl+O to load media")

    def _delete_selected(self):
        self.state.delete_strips(list(self.state.selected_ids))

    # ── UI state ──────────────────────────────────────────────────────────────
    def _update_undo_redo(self):
        self._btn_undo.setEnabled(self.state.can_undo())
        self._btn_redo.setEnabled(self.state.can_redo())

    def _update_title(self, *_):
        dirty = " •" if not self.state.is_saved else ""
        media = (
            os.path.basename(self.state.media_path)
            if self.state.media_path else "untitled"
        )
        self.setWindowTitle(f"Emotion Annotator  ·  {media}{dirty}")

    # ── Close ─────────────────────────────────────────────────────────────────
    def closeEvent(self, event):
        if not self.state.is_saved and self.state.strips:
            r = QMessageBox.question(
                self, "Unsaved annotations",
                "Save before closing?",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
            )
            if r == QMessageBox.Cancel:
                event.ignore()
                return
            if r == QMessageBox.Yes:
                self._save_json()

        # Clean up player (removes temp WAV file)
        self.media_panel.cleanup()

        if self._waveform_worker and self._waveform_worker.isRunning():
            self._waveform_worker.cancel()
            self._waveform_worker.wait(1000)

        event.accept()
