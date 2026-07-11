"""
Central application state with full undo/redo support.
All mutations to strips must go through AppState so they are tracked.
"""
import copy
from typing import List, Optional
from PyQt5.QtCore import QObject, pyqtSignal
from strip import Strip


class AppState(QObject):
    # Signals emitted after state changes
    strips_changed   = pyqtSignal()
    selection_changed = pyqtSignal()
    media_changed    = pyqtSignal(str)       # path
    position_changed = pyqtSignal(float)     # seconds
    duration_changed = pyqtSignal(float)     # seconds
    save_state_changed = pyqtSignal(bool)    # is_saved

    MAX_UNDO = 200

    def __init__(self, parent=None):
        super().__init__(parent)
        self._strips: List[Strip] = []
        self._selected_ids: set = set()
        self._clipboard: Optional[Strip] = None

        self._media_path: str = ""
        self._json_path: str = ""
        self._duration: float = 0.0
        self._position: float = 0.0
        self._is_saved: bool = True

        self._undo_stack: list = []   # list of serialised strip lists
        self._redo_stack: list = []

    # ------------------------------------------------------------------ #
    #  Media / project                                                     #
    # ------------------------------------------------------------------ #
    @property
    def media_path(self): return self._media_path

    @property
    def json_path(self): return self._json_path

    @json_path.setter
    def json_path(self, v): self._json_path = v

    @property
    def duration(self): return self._duration

    @property
    def position(self): return self._position

    @property
    def is_saved(self): return self._is_saved

    def set_media(self, media_path: str, json_path: str):
        self._media_path = media_path
        self._json_path = json_path
        self.media_changed.emit(media_path)

    def set_duration(self, d: float):
        self._duration = d
        self.duration_changed.emit(d)

    def set_position(self, p: float):
        self._position = p
        self.position_changed.emit(p)

    # ------------------------------------------------------------------ #
    #  Strips – read access                                                #
    # ------------------------------------------------------------------ #
    @property
    def strips(self) -> List[Strip]:
        return self._strips

    @property
    def selected_ids(self) -> set:
        return self._selected_ids

    def selected_strips(self) -> List[Strip]:
        return [s for s in self._strips if s.id in self._selected_ids]

    def strip_by_id(self, sid: str) -> Optional[Strip]:
        for s in self._strips:
            if s.id == sid:
                return s
        return None

    @property
    def clipboard(self): return self._clipboard

    # ------------------------------------------------------------------ #
    #  Strips – mutating (all record undo)                                 #
    # ------------------------------------------------------------------ #
    def _snapshot(self):
        """Push current strip list onto undo stack."""
        snap = [s.to_dict() for s in self._strips]
        # avoid duplicates
        if self._undo_stack and self._undo_stack[-1] == snap:
            return
        self._undo_stack.append(snap)
        if len(self._undo_stack) > self.MAX_UNDO:
            self._undo_stack.pop(0)
        self._redo_stack.clear()
        self._mark_unsaved()

    def _restore(self, snap):
        self._strips = [Strip.from_dict(d) for d in snap]
        self._selected_ids.clear()
        self.strips_changed.emit()
        self.selection_changed.emit()
        self._mark_unsaved()

    def _mark_unsaved(self):
        if self._is_saved:
            self._is_saved = False
            self.save_state_changed.emit(False)

    def mark_saved(self):
        self._is_saved = True
        self.save_state_changed.emit(True)

    # --- public mutators ----------------------------------------------- #

    def add_strip(self, strip: Strip):
        self._snapshot()
        self._strips.append(strip)
        self._strips.sort(key=lambda s: s.start)
        self.strips_changed.emit()

    def delete_strips(self, ids):
        if not ids:
            return
        self._snapshot()
        self._strips = [s for s in self._strips if s.id not in ids]
        self._selected_ids -= set(ids)
        self.strips_changed.emit()
        self.selection_changed.emit()

    def update_strip(self, strip: Strip, record=True):
        """Replace strip data in-place (strip object already mutated)."""
        if record:
            self._snapshot()
        self.strips_changed.emit()

    def move_strip(self, sid: str, new_start: float, new_end: float, record=True):
        s = self.strip_by_id(sid)
        if s is None:
            return
        if record:
            self._snapshot()
        s.start = new_start
        s.end = new_end
        self._strips.sort(key=lambda x: x.start)
        self.strips_changed.emit()

    def set_strip_emotion(self, sid: str, theta: float, r: float):
        s = self.strip_by_id(sid)
        if s is None:
            return
        self._snapshot()
        s.theta = theta
        s.r = r
        self.strips_changed.emit()

    def clear_strips(self):
        if not self._strips:
            return
        self._snapshot()
        self._strips.clear()
        self._selected_ids.clear()
        self.strips_changed.emit()
        self.selection_changed.emit()

    def set_strips(self, strips: List[Strip]):
        """Replace all strips (used on JSON import)."""
        self._snapshot()
        self._strips = strips
        self._selected_ids.clear()
        self.strips_changed.emit()
        self.selection_changed.emit()

    # --- selection ----------------------------------------------------- #

    def set_selection(self, ids):
        self._selected_ids = set(ids)
        self.selection_changed.emit()

    def toggle_selection(self, sid: str):
        if sid in self._selected_ids:
            self._selected_ids.discard(sid)
        else:
            self._selected_ids.add(sid)
        self.selection_changed.emit()

    def clear_selection(self):
        if self._selected_ids:
            self._selected_ids.clear()
            self.selection_changed.emit()

    # --- clipboard ----------------------------------------------------- #

    def copy_selected(self):
        sel = self.selected_strips()
        if sel:
            self._clipboard = sel[0].copy()

    def duplicate_selected(self):
        sel = self.selected_strips()
        if not sel:
            return
        self._snapshot()
        new_strips = []
        for s in sel:
            ns = s.copy()
            # place right after original
            gap = 0.0
            ns.start = s.end + gap
            ns.end = ns.start + s.duration
            new_strips.append(ns)
        for ns in new_strips:
            self._strips.append(ns)
        self._strips.sort(key=lambda x: x.start)
        self._selected_ids = {ns.id for ns in new_strips}
        self.strips_changed.emit()
        self.selection_changed.emit()

    def paste_at(self, position: float):
        if self._clipboard is None:
            return
        self._snapshot()
        ns = self._clipboard.copy()
        dur = ns.end - ns.start
        ns.start = position
        ns.end = position + dur
        self._strips.append(ns)
        self._strips.sort(key=lambda x: x.start)
        self._selected_ids = {ns.id}
        self.strips_changed.emit()
        self.selection_changed.emit()

    # --- undo / redo --------------------------------------------------- #

    def can_undo(self): return len(self._undo_stack) > 0
    def can_redo(self): return len(self._redo_stack) > 0

    def undo(self):
        if not self._undo_stack:
            return
        # save current to redo
        self._redo_stack.append([s.to_dict() for s in self._strips])
        snap = self._undo_stack.pop()
        self._restore(snap)

    def redo(self):
        if not self._redo_stack:
            return
        self._undo_stack.append([s.to_dict() for s in self._strips])
        snap = self._redo_stack.pop()
        self._restore(snap)

    # --- serialisation ------------------------------------------------- #

    def to_dict(self):
        return {
            "duration": self._duration,
            "strips": [s.to_dict() for s in self._strips],
        }

    def load_dict(self, d):
        strips = [Strip.from_dict(sd) for sd in d.get("strips", [])]
        self._strips = strips
        self._selected_ids.clear()
        self._undo_stack.clear()
        self._redo_stack.clear()
        self.strips_changed.emit()
        self.selection_changed.emit()
        self.mark_saved()
