"""
Keyframe index — probes all I-frame timestamps so seeks always land
on a keyframe instantly instead of decoding backward from a GOP start.

Built in a background QThread so it doesn't block the UI.
"""
import subprocess
from PyQt5.QtCore import QThread, pyqtSignal
import bisect


class KeyframeIndexer(QThread):
    """Runs ffprobe to collect all keyframe PTS values."""
    finished = pyqtSignal(list)   # sorted list of float seconds
    failed   = pyqtSignal(str)

    def __init__(self, path: str, parent=None):
        super().__init__(parent)
        self._path = path

    def run(self):
        cmd = [
            "ffprobe",
            "-v", "error",
            "-select_streams", "v:0",
            "-skip_frame", "noref",
            "-show_frames",
            "-show_entries", "frame=key_frame,best_effort_timestamp_time",
            "-of", "csv",
            self._path,
        ]
        try:
            out = subprocess.check_output(
                cmd, stderr=subprocess.DEVNULL, timeout=120
            ).decode(errors="replace")
        except FileNotFoundError:
            self.failed.emit("ffprobe not found")
            return
        except subprocess.TimeoutExpired:
            self.failed.emit("ffprobe timed out building keyframe index")
            return
        except Exception as e:
            self.failed.emit(str(e))
            return

        keyframes = []
        for line in out.splitlines():
            parts = line.strip().split(",")
            # format: frame,<key_frame>,<timestamp>
            if len(parts) >= 3 and parts[1] == "1":
                try:
                    keyframes.append(float(parts[2]))
                except ValueError:
                    pass

        keyframes.sort()
        self.finished.emit(keyframes)


class KeyframeIndex:
    """
    Wraps a sorted list of keyframe timestamps.
    Use snap_to_keyframe() before seeking to avoid long GOP decode waits.
    """
    def __init__(self):
        self._kf: list[float] = []
        self._ready = False

    def load(self, keyframes: list[float]):
        self._kf   = sorted(keyframes)
        self._ready = True

    def clear(self):
        self._kf    = []
        self._ready = False

    @property
    def ready(self) -> bool:
        return self._ready

    def snap_to_keyframe(self, t: float) -> float:
        """
        Return the nearest keyframe at or before t.
        Falls back to t if index is empty or not ready.
        """
        if not self._kf:
            return t
        idx = bisect.bisect_right(self._kf, t)
        if idx == 0:
            return self._kf[0]
        return self._kf[idx - 1]

    def nearest(self, t: float) -> float:
        """Return the absolutely nearest keyframe (before or after)."""
        if not self._kf:
            return t
        idx = bisect.bisect_left(self._kf, t)
        candidates = []
        if idx < len(self._kf):
            candidates.append(self._kf[idx])
        if idx > 0:
            candidates.append(self._kf[idx - 1])
        return min(candidates, key=lambda k: abs(k - t))

    def distance_to_keyframe(self, t: float) -> float:
        """How far is t from the nearest preceding keyframe? (seconds)"""
        kf = self.snap_to_keyframe(t)
        return abs(t - kf)

    def __len__(self):
        return len(self._kf)
