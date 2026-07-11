"""
FFmpegPlayer — optimized video/audio playback via ffmpeg.

Architecture:
  ┌─────────────────────────────────────────────────────┐
  │  FFmpegPlayer (QObject)                             │
  │   ├─ AudioExtractor (QThread) → temp 16kHz WAV     │
  │   ├─ QMediaPlayer  → plays WAV (audio clock)        │
  │   ├─ VideoDecoder  (QThread) → frame ring buffer    │
  │   └─ QTimer 30ms   → pulls frames, syncs to audio  │
  └─────────────────────────────────────────────────────┘

Sync strategy:
  - Audio position is the master clock.
  - VideoDecoder runs slightly ahead, writing into a ring buffer.
  - Display timer reads the ring buffer and picks the frame whose
    pts is closest to the current audio clock, dropping stale frames.
  - If video drifts > RESYNC_THRESHOLD behind audio, the decoder
    is restarted from the current audio position.
"""
import os
import time
import tempfile
import subprocess
import threading
import struct
import queue

import numpy as np
from PyQt5.QtCore import (
    Qt, QThread, pyqtSignal, QObject, QTimer, QMutex, QMutexLocker,
)
from PyQt5.QtGui import QImage, QPainter, QColor
from PyQt5.QtWidgets import QWidget, QSizePolicy

# ── Tuning constants ──────────────────────────────────────────────────────────
RING_SIZE        = 8      # max frames buffered ahead
DISPLAY_INTERVAL = 30     # ms between display ticks (~33 fps cap)
RESYNC_THRESHOLD = 0.5    # seconds of drift before hard resync
MAX_FRAME_W      = 1280   # never decode wider than this (saves CPU)
MAX_FRAME_H      = 720


# ── ffprobe ───────────────────────────────────────────────────────────────────
def _probe(path: str) -> dict:
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height,r_frame_rate,duration",
        "-of", "default=noprint_wrappers=1",
        path,
    ]
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL,
                                      timeout=15).decode()
    except Exception:
        out = ""
    info = {}
    for line in out.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            info[k.strip()] = v.strip()

    # fallback duration from container
    if not info.get("duration") or info["duration"] == "N/A":
        try:
            out2 = subprocess.check_output(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1", path],
                stderr=subprocess.DEVNULL, timeout=15,
            ).decode()
            for line in out2.splitlines():
                if line.startswith("duration="):
                    info["duration"] = line.split("=", 1)[1].strip()
        except Exception:
            pass

    has_video = bool(info.get("width") and info["width"] not in ("0", "N/A"))
    fps = 25.0
    if "r_frame_rate" in info:
        try:
            n, d = info["r_frame_rate"].split("/")
            fps = float(n) / max(1, float(d))
            if fps > 120 or fps <= 0:
                fps = 25.0
        except Exception:
            pass
    try:
        dur = float(info.get("duration") or 0)
    except Exception:
        dur = 0.0

    w = int(info.get("width",  0) or 0)
    h = int(info.get("height", 0) or 0)
    return dict(duration=dur, width=w, height=h, fps=fps, has_video=has_video)


# ── Audio extractor ───────────────────────────────────────────────────────────
class AudioExtractor(QThread):
    finished = pyqtSignal(str)
    failed   = pyqtSignal(str)

    def __init__(self, src: str, parent=None):
        super().__init__(parent)
        self._src = src
        self._tmp = None

    @property
    def tmp_path(self): return self._tmp

    def run(self):
        fd, tmp = tempfile.mkstemp(suffix=".wav", prefix="emo_audio_")
        os.close(fd)
        self._tmp = tmp
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", self._src,
            "-vn", "-ac", "1", "-ar", "16000", "-f", "wav", tmp,
        ]
        try:
            r = subprocess.run(cmd, capture_output=True, timeout=600)
            if r.returncode == 0:
                self.finished.emit(tmp)
            else:
                self.failed.emit(r.stderr.decode(errors="replace")[:300])
        except FileNotFoundError:
            self.failed.emit("ffmpeg not found — install ffmpeg and add to PATH")
        except Exception as e:
            self.failed.emit(str(e))


# ── Video decoder thread ──────────────────────────────────────────────────────
class VideoDecoder(QThread):
    """
    Decodes video frames from ffmpeg pipe into a thread-safe ring buffer.
    Each item in the buffer is (pts_seconds: float, QImage).

    The decoder runs as fast as ffmpeg can supply frames (no artificial
    sleep). The display timer on the main thread pulls frames at the right
    wall-clock time and drops stale ones.
    """
    decoder_error = pyqtSignal(str)

    def __init__(self, path: str, w: int, h: int, fps: float,
                 start_sec: float = 0.0, parent=None):
        super().__init__(parent)
        self._path   = path
        self._w      = w
        self._h      = h
        self._fps    = max(1.0, fps)
        self._start  = start_sec
        self._stop   = False
        self._proc   = None

        # Ring buffer: queue of (pts, QImage), bounded
        self.buf: queue.Queue = queue.Queue(maxsize=RING_SIZE)

    def request_stop(self):
        self._stop = True
        self.buf.put(None)   # unblock any waiting get()
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.kill()
            except Exception:
                pass

    def run(self):
        frame_bytes = self._w * self._h * 3
        pts         = self._start
        frame_dur   = 1.0 / self._fps

        cmd = [
            "ffmpeg",
            "-hide_banner", "-loglevel", "error",
            "-ss", f"{self._start:.6f}",
            "-i", self._path,
            "-an",
            "-vf", f"scale={self._w}:{self._h}:flags=fast_bilinear",
            "-f", "rawvideo",
            "-pix_fmt", "rgb24",
            "-vsync", "0",       # pass through frames without duplication
            "pipe:1",
        ]
        try:
            self._proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                bufsize=frame_bytes * RING_SIZE,
            )
        except Exception as e:
            self.decoder_error.emit(str(e))
            return

        while not self._stop:
            raw = self._proc.stdout.read(frame_bytes)
            if len(raw) < frame_bytes:
                break   # EOF

            # Build QImage — copy() detaches from the raw bytes buffer
            img = QImage(raw, self._w, self._h,
                         self._w * 3, QImage.Format_RGB888).copy()

            # Put into ring buffer; block if full (natural back-pressure)
            try:
                self.buf.put((pts, img), timeout=1.0)
            except queue.Full:
                pass   # display is too slow; just drop frame

            pts += frame_dur

        # Signal EOF with sentinel
        try:
            self.buf.put(None, timeout=0.5)
        except queue.Full:
            pass

        if self._proc.poll() is None:
            self._proc.kill()


# ── Video display widget ──────────────────────────────────────────────────────
class VideoDisplay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._frame: QImage | None = None
        self.setStyleSheet("background:#111111;")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._mutex = QMutex()

    def set_frame(self, img: QImage):
        with QMutexLocker(self._mutex):
            self._frame = img
        self.update()

    def clear(self):
        with QMutexLocker(self._mutex):
            self._frame = None
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.fillRect(self.rect(), QColor("#111111"))
        with QMutexLocker(self._mutex):
            frame = self._frame
        if frame:
            scaled = frame.scaled(
                self.width(), self.height(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            x = (self.width()  - scaled.width())  // 2
            y = (self.height() - scaled.height()) // 2
            p.drawImage(x, y, scaled)
        p.end()


# ── Main player ───────────────────────────────────────────────────────────────
class FFmpegPlayer(QObject):
    """
    Orchestrates AudioExtractor + QMediaPlayer (audio) + VideoDecoder.

    Public API mirrors the subset used by MediaPanel:
      load(path), play(), pause(), seek(seconds), set_volume(int)
      .is_playing  .position  .duration

    Signals:
      duration_ready(float), position_changed(float),
      state_changed(str), video_available(bool),
      error(str), audio_ready(str)
    """
    duration_ready  = pyqtSignal(float)
    position_changed= pyqtSignal(float)
    state_changed   = pyqtSignal(str)
    video_available = pyqtSignal(bool)
    error           = pyqtSignal(str)
    audio_ready     = pyqtSignal(str)   # temp WAV path

    def __init__(self, video_display: VideoDisplay, parent=None):
        super().__init__(parent)
        self._display   = video_display
        self._src       = ""
        self._tmp_wav   = ""
        self._info      = {}
        self._state     = "stopped"
        self._position  = 0.0
        self._volume    = 80
        self._has_video = False

        # Decode dimensions (capped for performance)
        self._dec_w = 0
        self._dec_h = 0

        # Audio via QMediaPlayer (WAV — universally supported)
        from PyQt5.QtMultimedia import QMediaPlayer as QMP, QMediaContent
        from PyQt5.QtCore import QUrl
        self._QMP            = QMP
        self._QMediaContent  = QMediaContent
        self._QUrl           = QUrl
        self._audio          = QMP(self)
        self._audio.stateChanged.connect(self._on_audio_state)
        self._audio.durationChanged.connect(self._on_audio_dur)
        self._audio.error.connect(
            lambda: self.error.emit(self._audio.errorString())
        )

        # Video decoder thread
        self._decoder: VideoDecoder | None = None

        # Display / sync timer
        self._disp_timer = QTimer(self)
        self._disp_timer.setInterval(DISPLAY_INTERVAL)
        self._disp_timer.timeout.connect(self._display_tick)

        # Audio extractor
        self._extractor: AudioExtractor | None = None

        # Resync state
        self._last_resync = 0.0

    # ── Load ──────────────────────────────────────────────────────────────────
    def load(self, path: str):
        self._cleanup_decoder()
        self._audio.stop()
        self._src      = path
        self._position = 0.0
        self._display.clear()

        self._info      = _probe(path)
        self._has_video = self._info.get("has_video", False)
        self.video_available.emit(self._has_video)

        # Compute decode dimensions (cap for performance)
        sw, sh = self._info.get("width", 0), self._info.get("height", 0)
        if sw > 0 and sh > 0:
            scale = min(1.0, MAX_FRAME_W / sw, MAX_FRAME_H / sh)
            self._dec_w = max(2, int(sw * scale) & ~1)   # even numbers
            self._dec_h = max(2, int(sh * scale) & ~1)
        else:
            self._dec_w = self._dec_h = 0

        # Extract audio to WAV in background
        if self._extractor and self._extractor.isRunning():
            self._extractor.wait(3000)
        self._extractor = AudioExtractor(path)
        self._extractor.finished.connect(self._on_audio_extracted)
        self._extractor.failed.connect(lambda m: self.error.emit(m))
        self._extractor.start()

    def _on_audio_extracted(self, wav: str):
        self._tmp_wav = wav
        self._audio.setMedia(
            self._QMediaContent(self._QUrl.fromLocalFile(wav))
        )
        self._audio.setVolume(self._volume)
        self.audio_ready.emit(wav)

    def _on_audio_dur(self, ms: int):
        dur = self._info.get("duration") or ms / 1000.0
        self._info["duration"] = float(dur)
        self.duration_ready.emit(float(dur))

    def _on_audio_state(self, state):
        if state == self._QMP.StoppedState and self._state == "playing":
            self._set_state("paused")

    # ── Controls ──────────────────────────────────────────────────────────────
    def play(self):
        if not self._tmp_wav:
            return
        self._audio.play()
        if self._has_video and self._dec_w > 0:
            self._start_decoder(self._position)
        self._disp_timer.start()
        self._set_state("playing")

    def pause(self):
        self._audio.pause()
        self._disp_timer.stop()
        self._cleanup_decoder()
        self._set_state("paused")

    def seek(self, seconds: float):
        dur = self._info.get("duration", 0.0)
        self._position = max(0.0, min(float(seconds), float(dur)))
        self._audio.setPosition(int(self._position * 1000))
        self.position_changed.emit(self._position)
        if self._state == "playing" and self._has_video:
            self._restart_decoder(self._position)

    def set_volume(self, v: int):
        self._volume = v
        self._audio.setVolume(v)

    @property
    def duration(self) -> float:
        return float(self._info.get("duration") or 0.0)

    @property
    def position(self) -> float:
        return self._position

    @property
    def is_playing(self) -> bool:
        return self._state == "playing"

    # ── Display tick (main thread, every 30 ms) ───────────────────────────────
    def _display_tick(self):
        # Audio is master clock
        audio_pos = self._audio.position() / 1000.0
        self._position = audio_pos
        self.position_changed.emit(audio_pos)

        if not self._has_video or self._decoder is None:
            return

        buf = self._decoder.buf

        # Drain stale frames (pts < audio_pos - one frame)
        frame_dur  = 1.0 / max(1.0, self._info.get("fps", 25.0))
        best_img   = None
        best_pts   = -1.0

        # Non-blocking drain: pull all available frames, keep newest ≤ audio_pos
        while True:
            try:
                item = buf.get_nowait()
            except queue.Empty:
                break
            if item is None:
                # EOF sentinel — decoder finished
                self._cleanup_decoder()
                break
            pts, img = item
            if pts <= audio_pos + frame_dur:
                # This frame is on time or already past — candidate
                best_pts = pts
                best_img = img
            else:
                # Frame is in the future — put it back and stop draining
                try:
                    buf.put_nowait((pts, img))
                except queue.Full:
                    pass
                break

        if best_img is not None:
            self._display.set_frame(best_img)

        # Hard resync if video is severely behind audio
        if (self._decoder is not None and
                audio_pos - self._last_resync > RESYNC_THRESHOLD and
                buf.empty()):
            self._last_resync = audio_pos
            self._restart_decoder(audio_pos)

    # ── Decoder management ────────────────────────────────────────────────────
    def _start_decoder(self, start: float):
        self._last_resync = start
        d = VideoDecoder(
            self._src,
            self._dec_w, self._dec_h,
            self._info.get("fps", 25.0),
            start,
        )
        d.decoder_error.connect(lambda m: self.error.emit(m))
        self._decoder = d
        d.start()

    def _restart_decoder(self, start: float):
        self._cleanup_decoder()
        self._start_decoder(start)

    def _cleanup_decoder(self):
        if self._decoder:
            self._decoder.request_stop()
            self._decoder.wait(800)
            self._decoder = None

    # ── State ─────────────────────────────────────────────────────────────────
    def _set_state(self, state: str):
        self._state = state
        self.state_changed.emit(state)

    # ── Cleanup ───────────────────────────────────────────────────────────────
    def cleanup(self):
        self._disp_timer.stop()
        self._audio.stop()
        self._cleanup_decoder()
        if self._extractor and self._extractor.isRunning():
            self._extractor.wait(3000)
        self._audio.setMedia(self._QMediaContent())
        if self._tmp_wav and os.path.exists(self._tmp_wav):
            try:
                os.remove(self._tmp_wav)
            except Exception:
                pass
        self._tmp_wav = ""
