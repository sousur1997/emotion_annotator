"""
Waveform mipmap — pre-generates multiple resolution levels of the
amplitude envelope so the timeline can pick the right level at any
zoom without iterating the full array every paint.
"""
import numpy as np

LEVELS = [8000, 4000, 2000, 1000, 500, 250]


class WaveformMipmap:
    def __init__(self, peaks: np.ndarray):
        """peaks: normalised float32 array from WaveformWorker."""
        self.levels: dict[int, np.ndarray] = {}
        src = peaks.astype(np.float32)
        for n in LEVELS:
            bucket = max(1, len(src) // n)
            trim   = len(src) - (len(src) % bucket) if len(src) % bucket else len(src)
            if trim <= 0 or bucket <= 0:
                self.levels[n] = src
                continue
            reshaped = src[:trim].reshape(-1, bucket)
            level    = reshaped.max(axis=1).astype(np.float32)
            mx = level.max()
            if mx > 0:
                level /= mx
            self.levels[n] = level

    def for_view(self, px_per_sec: float, duration: float, width: int) -> np.ndarray:
        """Return the most appropriate resolution level for current zoom."""
        if duration <= 0 or px_per_sec <= 0:
            return self.levels[LEVELS[0]]
        # How many peaks do we actually need to fill the visible width?
        needed = max(64, int(px_per_sec * duration))
        # Pick smallest level that is >= needed (best quality that isn't wasteful)
        chosen = self.levels[LEVELS[-1]]
        for n in LEVELS:
            if n >= needed:
                chosen = self.levels[n]
                break
        return chosen
