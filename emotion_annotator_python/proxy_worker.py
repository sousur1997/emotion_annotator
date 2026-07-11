"""
Proxy transcoder — generates a low-res fast-decode proxy of the
original media file in a background QThread.

Proxy spec:
  - Resolution: max 854×480 (480p), preserving aspect ratio
  - Codec: libx264, preset ultrafast, crf 28 (small + fast)
  - Audio: aac 128k (for re-extraction later if needed)
  - Container: .mp4

The proxy is stored in the same directory as the source with
suffix _proxy.mp4.  If a valid proxy already exists it is reused.
"""
import os
import subprocess
from PyQt5.QtCore import QThread, pyqtSignal


PROXY_SUFFIX  = "_emo_proxy.mp4"
PROXY_MAX_W   = 854
PROXY_MAX_H   = 480


def proxy_path_for(src: str) -> str:
    base = os.path.splitext(src)[0]
    return base + PROXY_SUFFIX


def proxy_exists(src: str) -> bool:
    p = proxy_path_for(src)
    return os.path.exists(p) and os.path.getsize(p) > 1024


class ProxyWorker(QThread):
    """
    Transcodes src to a 480p proxy in background.
    Emits finished(proxy_path) on success, failed(msg) on error.
    progress(0-100) is emitted periodically.
    """
    progress = pyqtSignal(int)
    finished = pyqtSignal(str)   # proxy path
    failed   = pyqtSignal(str)

    def __init__(self, src: str, duration: float = 0.0, parent=None):
        super().__init__(parent)
        self._src      = src
        self._duration = duration
        self._cancelled = False
        self._proc = None

    def cancel(self):
        self._cancelled = True
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.terminate()
            except Exception:
                pass

    def run(self):
        if self._cancelled:
            return

        # Reuse existing proxy
        if proxy_exists(self._src):
            self.progress.emit(100)
            self.finished.emit(proxy_path_for(self._src))
            return

        out = proxy_path_for(self._src)
        # scale filter: fit within PROXY_MAX_W x PROXY_MAX_H, keep aspect,
        # ensure dimensions are divisible by 2 (libx264 requirement)
        vf = (
            f"scale='if(gt(iw,ih),min({PROXY_MAX_W},iw),-2)':"
            f"'if(gt(iw,ih),-2,min({PROXY_MAX_H},ih))',"
            f"scale=trunc(iw/2)*2:trunc(ih/2)*2"
        )
        cmd = [
            "ffmpeg", "-y",
            "-hide_banner", "-loglevel", "error",
            "-stats",
            "-i", self._src,
            "-vf", vf,
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "28",
            "-c:a", "aac",
            "-b:a", "128k",
            "-movflags", "+faststart",
            out,
        ]
        try:
            self._proc = subprocess.Popen(
                cmd,
                stderr=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                universal_newlines=True,
                bufsize=1,
            )
            # Parse ffmpeg progress from stderr
            for line in self._proc.stderr:
                if self._cancelled:
                    self._proc.terminate()
                    break
                # "frame=  123 fps= 45 ... time=00:00:05.12 ..."
                if "time=" in line and self._duration > 0:
                    try:
                        t_str = line.split("time=")[1].split()[0]
                        h, m, s = t_str.split(":")
                        elapsed = int(h)*3600 + int(m)*60 + float(s)
                        pct = min(99, int(elapsed / self._duration * 100))
                        self.progress.emit(pct)
                    except Exception:
                        pass

            self._proc.wait()
            if self._cancelled:
                if os.path.exists(out):
                    os.remove(out)
                return
            if self._proc.returncode == 0:
                self.progress.emit(100)
                self.finished.emit(out)
            else:
                self.failed.emit("Proxy transcode failed (ffmpeg error)")
        except FileNotFoundError:
            self.failed.emit("ffmpeg not found — install ffmpeg and add to PATH")
        except Exception as e:
            self.failed.emit(str(e))
