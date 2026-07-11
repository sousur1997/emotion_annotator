"""
LRU frame cache — stores recently decoded QImages keyed by PTS (seconds).
Scrubbing reuses cached frames without re-launching ffmpeg.
Thread-safe via QMutex.
"""
import collections
from PyQt5.QtCore import QMutex, QMutexLocker
from PyQt5.QtGui import QImage


class FrameCache:
    def __init__(self, max_frames: int = 120):
        """
        max_frames: how many frames to keep in RAM.
        120 frames @ 720p RGB24 ≈ 120 × 1280×720×3 ≈ 330 MB worst case.
        Default 120 is safe; reduce if RAM is tight.
        """
        self._cache: collections.OrderedDict[float, QImage] = collections.OrderedDict()
        self._max   = max_frames
        self._mutex = QMutex()
        self._hits  = 0
        self._miss  = 0

    def get(self, pts: float, tolerance: float = 0.025) -> QImage | None:
        """Return cached frame within tolerance seconds of pts, or None."""
        with QMutexLocker(self._mutex):
            for k in reversed(list(self._cache.keys())):
                if abs(k - pts) <= tolerance:
                    self._cache.move_to_end(k)
                    self._hits += 1
                    return self._cache[k]
            self._miss += 1
            return None

    def put(self, pts: float, img: QImage):
        """Store a frame. Evicts oldest if over capacity."""
        with QMutexLocker(self._mutex):
            if pts in self._cache:
                self._cache.move_to_end(pts)
                self._cache[pts] = img
                return
            self._cache[pts] = img
            self._cache.move_to_end(pts)
            while len(self._cache) > self._max:
                self._cache.popitem(last=False)

    def invalidate(self):
        """Clear all cached frames (call on seek or media change)."""
        with QMutexLocker(self._mutex):
            self._cache.clear()
            self._hits = self._miss = 0

    def has_range(self, t_start: float, t_end: float,
                  fps: float, threshold: float = 0.8) -> bool:
        """
        Return True if cache covers at least `threshold` fraction of
        frames in [t_start, t_end] at given fps.
        Used to decide whether to launch a new decoder.
        """
        if fps <= 0 or t_end <= t_start:
            return False
        needed = max(1, int((t_end - t_start) * fps))
        found  = 0
        step   = 1.0 / fps
        t = t_start
        with QMutexLocker(self._mutex):
            keys = list(self._cache.keys())
        for _ in range(needed):
            if any(abs(k - t) <= step * 0.6 for k in keys):
                found += 1
            t += step
        return (found / needed) >= threshold

    @property
    def hit_rate(self) -> float:
        total = self._hits + self._miss
        return self._hits / total if total else 0.0

    def __len__(self):
        return len(self._cache)
