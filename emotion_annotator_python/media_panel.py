"""
Media panel — uses FFmpegPlayer for universal video/audio support.
Audio is extracted to a 16 kHz mono WAV temp file via ffmpeg.
Video frames are decoded and displayed via ffmpeg pipe.
"""
import os
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSlider, QSizePolicy,
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont

from app_state import AppState
from ffmpeg_player import FFmpegPlayer, VideoDisplay

# ── Theme ─────────────────────────────────────────────────────────────────────
BG      = "#f0f2f5"
SURFACE = "#ffffff"
BORDER  = "#c8cdd6"
PRIMARY = "#3a6fd8"
TEXT    = "#1a1d23"
TEXT2   = "#5a6072"
ACCENT  = "#eef2fb"

SLIDER_QSS = f"""
    QSlider::groove:horizontal {{
        height:5px; background:{BORDER}; border-radius:3px;
    }}
    QSlider::handle:horizontal {{
        width:14px; height:14px; margin:-5px 0;
        background:{PRIMARY}; border-radius:7px;
    }}
    QSlider::sub-page:horizontal {{
        background:{PRIMARY}; border-radius:3px;
    }}
"""


def _tbtn(text, tip, accent=False):
    b = QPushButton(text)
    b.setToolTip(tip)
    if accent:
        b.setStyleSheet(f"""
            QPushButton {{
                background:{PRIMARY}; color:#fff; border:1px solid {PRIMARY};
                border-radius:7px; font-size:20px; min-width:48px; min-height:36px; padding:0 10px;
            }}
            QPushButton:hover   {{ background:#2a5bc8; }}
            QPushButton:pressed {{ background:#1e4aaa; }}
        """)
    else:
        b.setStyleSheet(f"""
            QPushButton {{
                background:{SURFACE}; color:{TEXT}; border:1px solid {BORDER};
                border-radius:6px; font-size:17px; min-width:38px; min-height:36px; padding:0 8px;
            }}
            QPushButton:hover   {{ background:#dde2ec; }}
            QPushButton:pressed {{ background:#c8cfdf; }}
        """)
    return b


class AudioBanner(QWidget):
    """Shown when an audio-only file is loaded."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background:{ACCENT};")
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignCenter)
        lay.setSpacing(12)

        self._icon = QLabel("🎵")
        self._icon.setAlignment(Qt.AlignCenter)
        self._icon.setStyleSheet(
            f"font-size:56px; background:transparent; color:{PRIMARY};"
        )
        lay.addWidget(self._icon)

        self._lbl_name = QLabel("No file loaded")
        self._lbl_name.setAlignment(Qt.AlignCenter)
        self._lbl_name.setStyleSheet(
            f"color:{TEXT}; font-size:15px; font-weight:700; background:transparent;"
        )
        lay.addWidget(self._lbl_name)

        self._lbl_sub = QLabel("")
        self._lbl_sub.setAlignment(Qt.AlignCenter)
        self._lbl_sub.setStyleSheet(
            f"color:{TEXT2}; font-size:11px; font-family:Consolas,monospace; "
            "background:transparent;"
        )
        lay.addWidget(self._lbl_sub)

        self._lbl_status = QLabel("")
        self._lbl_status.setAlignment(Qt.AlignCenter)
        self._lbl_status.setStyleSheet(
            f"color:{PRIMARY}; font-size:11px; font-style:italic; background:transparent;"
        )
        lay.addWidget(self._lbl_status)

    def set_file(self, path: str):
        name = os.path.basename(path)
        ext  = os.path.splitext(path)[1].upper().lstrip(".")
        icons = {
            "MP3": "🎵", "WAV": "🎶", "FLAC": "🎼",
            "OGG": "🎵", "AAC": "🎵", "M4A":  "🎵",
        }
        self._icon.setText(icons.get(ext, "🎵"))
        self._lbl_name.setText(name)
        try:
            size = os.path.getsize(path)
            self._lbl_sub.setText(f"{ext}  ·  {size / 1024 / 1024:.1f} MB")
        except Exception:
            self._lbl_sub.setText(ext)
        self._lbl_status.setText("Extracting audio…")

    def set_status(self, msg: str):
        self._lbl_status.setText(msg)


class MediaPanel(QWidget):
    duration_ready    = pyqtSignal(float)
    playback_finished = pyqtSignal()
    # emitted with temp WAV path so main window can pass to waveform worker
    audio_wav_ready   = pyqtSignal(str)

    def __init__(self, state: AppState, parent=None):
        super().__init__(parent)
        self.state = state
        self._fps          = 25
        self._loop_start   = None
        self._loop_end     = None
        self._loop_enabled = False
        self._has_video    = False
        self._current_path = ""

        self.setStyleSheet(f"background:{SURFACE};")
        self._build_ui()
        self._build_player()

    # ── UI ───────────────────────────────────────────────────────────────────
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Video display (custom widget painted via ffmpeg frames)
        self._video = VideoDisplay()
        layout.addWidget(self._video, 1)

        # Audio banner (shown when no video track)
        self._banner = AudioBanner()
        self._banner.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._banner.hide()
        layout.addWidget(self._banner, 1)

        # ── Controls bar ─────────────────────────────────────────────────────
        ctrl = QWidget()
        ctrl.setStyleSheet(f"background:{BG}; border-top:1px solid {BORDER};")
        cv = QVBoxLayout(ctrl)
        cv.setContentsMargins(10, 8, 10, 8)
        cv.setSpacing(8)

        self._seek = QSlider(Qt.Horizontal)
        self._seek.setRange(0, 100000)
        self._seek.setTracking(True)
        self._seek.setStyleSheet(SLIDER_QSS)
        cv.addWidget(self._seek)

        row = QHBoxLayout()
        row.setSpacing(6)

        self._btn_start = _tbtn("⏮", "Jump to start  [Shift+←]")
        self._btn_prev  = _tbtn("⏪", "Previous frame  [←]")
        self._btn_play  = _tbtn("▶", "Play / Pause  [Space]", accent=True)
        self._btn_next  = _tbtn("⏩", "Next frame  [→]")
        self._btn_end   = _tbtn("⏭", "Jump to end  [Shift+→]")

        for b in (self._btn_start, self._btn_prev, self._btn_play,
                  self._btn_next, self._btn_end):
            row.addWidget(b)

        row.addStretch()

        self._lbl_time = QLabel("00:00.00  /  00:00.00")
        self._lbl_time.setStyleSheet(
            f"color:{TEXT2}; font-size:16px; font-family:Consolas,monospace; min-width:165px;"
        )
        row.addWidget(self._lbl_time)

        row.addWidget(QLabel("🔊"))
        self._vol = QSlider(Qt.Horizontal)
        self._vol.setRange(0, 100)
        self._vol.setValue(80)
        self._vol.setFixedWidth(88)
        self._vol.setStyleSheet(SLIDER_QSS)
        row.addWidget(self._vol)

        cv.addLayout(row)
        layout.addWidget(ctrl)

    # ── Player ───────────────────────────────────────────────────────────────
    def _build_player(self):
        self._player = FFmpegPlayer(self._video, self)
        self._player.duration_ready.connect(self._on_duration)
        self._player.position_changed.connect(self._on_position)
        self._player.state_changed.connect(self._on_state)
        self._player.video_available.connect(self._on_video_available)
        self._player.error.connect(self._on_error)
        self._player.audio_ready.connect(self._on_audio_ready)

        self._btn_start.clicked.connect(self.jump_to_start)
        self._btn_prev.clicked.connect(self.prev_frame)
        self._btn_play.clicked.connect(self.toggle_play)
        self._btn_next.clicked.connect(self.next_frame)
        self._btn_end.clicked.connect(self.jump_to_end)

        self._seek.sliderPressed.connect(self._seek_start)
        self._seek.sliderMoved.connect(self._seek_moved)
        self._seek.sliderReleased.connect(self._seek_end)
        self._seeking = False

        self._vol.valueChanged.connect(self._player.set_volume)
        self.state.position_changed.connect(self._sync_seek)

    # ── Public API ───────────────────────────────────────────────────────────
    def load_media(self, path: str):
        self._current_path = path
        ext = os.path.splitext(path)[1].lower()
        is_audio = ext in ('.mp3', '.wav', '.flac', '.ogg', '.aac', '.m4a')

        # Show banner immediately for known audio types
        if is_audio:
            self._video.hide()
            self._banner.set_file(path)
            self._banner.show()
        else:
            self._banner.hide()
            self._video.show()

        self._player.load(path)

    def toggle_play(self):
        if self._player.is_playing:
            self._player.pause()
        else:
            self._player.play()

    def play(self):
        self._player.play()

    def pause(self):
        self._player.pause()

    def seek(self, seconds: float):
        self._player.seek(seconds)
        self.state.set_position(seconds)

    def play_range(self, start: float, end: float):
        self._loop_start = start
        self._loop_end   = end
        self.seek(start)
        self.play()

    def jump_to_start(self): self.seek(0.0)
    def jump_to_end(self):   self.seek(self.state.duration)
    def prev_frame(self):    self.seek(max(0.0, self.state.position - 1 / self._fps))
    def next_frame(self):    self.seek(min(self.state.duration, self.state.position + 1 / self._fps))
    def set_loop(self, v):   self._loop_enabled = v

    def cleanup(self):
        self._player.cleanup()

    # ── Slots ────────────────────────────────────────────────────────────────
    def _on_duration(self, dur: float):
        self.state.set_duration(dur)
        self.duration_ready.emit(dur)
        self._lbl_time.setText(f"{self._fmt(0)}  /  {self._fmt(dur)}")

    def _on_position(self, pos: float):
        self.state.set_position(pos)
        dur = self.state.duration
        self._lbl_time.setText(f"{self._fmt(pos)}  /  {self._fmt(dur)}")

        # update seek slider (don't fight user dragging)
        if not self._seeking and dur > 0:
            self._seek.setValue(int(pos / dur * 100000))

        # loop / range check
        if self._loop_end is not None and pos >= self._loop_end:
            if self._loop_enabled:
                self.seek(self._loop_start or 0.0)
            else:
                self._player.pause()
                self._loop_start = self._loop_end = None
                self.playback_finished.emit()

    def _on_state(self, state: str):
        self._btn_play.setText("⏸" if state == "playing" else "▶")

    def _on_video_available(self, available: bool):
        self._has_video = available
        if available:
            self._banner.hide()
            self._video.show()
        else:
            self._video.hide()
            if self._current_path:
                self._banner.set_file(self._current_path)
            self._banner.show()

    def _on_audio_ready(self, wav_path: str):
        self._banner.set_status("Ready ✓")
        # Forward to main window so waveform worker uses the extracted WAV
        self.audio_wav_ready.emit(wav_path)

    def _on_error(self, msg: str):
        print(f"[MediaPanel] {msg}")
        self._banner.set_status(f"⚠ {msg[:80]}")

    def _seek_start(self):
        self._seeking = True

    def _seek_moved(self, val: int):
        dur = self.state.duration
        if dur > 0:
            pos = val / 100000.0 * dur
            self._lbl_time.setText(f"{self._fmt(pos)}  /  {self._fmt(dur)}")

    def _seek_end(self):
        self._seeking = False
        dur = self.state.duration
        if dur > 0:
            pos = self._seek.value() / 100000.0 * dur
            self.seek(pos)

    def _sync_seek(self, pos: float):
        # Timeline → player sync (when user clicks timeline)
        if abs(self._player.position - pos) > 0.1:
            self._player.seek(pos)

    def _fmt(self, t: float) -> str:
        t = max(0, t)
        m, s = int(t // 60), t % 60
        return f"{m:02d}:{s:05.2f}"
