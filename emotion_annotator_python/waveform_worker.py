"""
Background thread that decodes audio and returns a downsampled
amplitude envelope for waveform display.

Decoder priority:
  1. soundfile  (fast, wav/flac/ogg/aiff)
  2. librosa    (slower, handles mp3 via audioread)
  3. ffmpeg CLI (subprocess fallback — works if ffmpeg is on PATH)
"""
import os
import tempfile
import subprocess
import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal

TARGET_SAMPLES = 6000   # envelope resolution


class WaveformWorker(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(object)   # np.ndarray or None
    error    = pyqtSignal(str)

    def __init__(self, path: str, parent=None):
        super().__init__(parent)
        self._path = path
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            peaks = self._decode()
            if not self._cancelled:
                self.finished.emit(peaks)
            else:
                self.finished.emit(None)
        except Exception as e:
            self.error.emit(str(e))
            self.finished.emit(None)

    # ── Decoder chain ─────────────────────────────────────────────────────────
    def _decode(self):
        samples = None

        # 1) soundfile
        try:
            import soundfile as sf
            data, _ = sf.read(self._path, dtype='float32', always_2d=True)
            samples = data.mean(axis=1)
            self.progress.emit(40)
        except Exception:
            pass

        # 2) librosa
        if samples is None:
            try:
                import librosa
                samples, _ = librosa.load(self._path, sr=None, mono=True)
                self.progress.emit(40)
            except Exception:
                pass

        # 3) ffmpeg subprocess → raw PCM f32le
        if samples is None:
            samples = self._ffmpeg_decode()

        if samples is None or len(samples) == 0:
            return None

        if self._cancelled:
            return None

        return self._make_peaks(samples)

    def _ffmpeg_decode(self):
        """Decode any audio/video to raw f32le mono PCM via ffmpeg CLI."""
        try:
            cmd = [
                "ffmpeg", "-hide_banner", "-loglevel", "error",
                "-i", self._path,
                "-vn",                   # drop video
                "-ac", "1",              # mono
                "-ar", "22050",          # resample to 22050 Hz
                "-f", "f32le",           # raw float32 little-endian
                "pipe:1",
            ]
            result = subprocess.run(cmd, capture_output=True, timeout=120)
            if result.returncode != 0:
                self.error.emit(f"ffmpeg error: {result.stderr.decode(errors='replace')[:200]}")
                return None
            self.progress.emit(70)
            raw = result.stdout
            if not raw:
                return None
            return np.frombuffer(raw, dtype=np.float32).copy()
        except FileNotFoundError:
            self.error.emit("ffmpeg not found — install ffmpeg and add it to PATH")
            return None
        except Exception as e:
            self.error.emit(f"ffmpeg decode failed: {e}")
            return None

    def _make_peaks(self, samples: np.ndarray) -> np.ndarray:
        n = len(samples)
        bucket = max(1, n // TARGET_SAMPLES)
        trim = n - (n % bucket) if n % bucket else n
        clipped = samples[:trim]
        peaks = np.abs(clipped.reshape(-1, bucket)).max(axis=1).astype(np.float32)
        mx = peaks.max()
        if mx > 0:
            peaks /= mx
        self.progress.emit(100)
        return peaks
