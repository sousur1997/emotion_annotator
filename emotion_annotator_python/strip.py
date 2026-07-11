"""
Strip data model.
"""
import uuid
from constants import breadcrumb, emotion_color, leaf_of


class Strip:
    """Represents one annotated emotion segment on the timeline."""

    def __init__(self, start: float, end: float, theta: float = 0.0, r: float = 0.0):
        self.id = str(uuid.uuid4())
        self.start = start      # seconds
        self.end = end          # seconds
        self.theta = theta      # degrees 0-360
        self.r = r              # 0.0 - 1.0 intensity

    # ------------------------------------------------------------------ #
    #  Derived properties                                                  #
    # ------------------------------------------------------------------ #
    @property
    def duration(self):
        return self.end - self.start

    @property
    def color(self):
        return emotion_color(self.theta)

    @property
    def label(self):
        leaf = leaf_of(self.theta, self.r)
        return leaf["mid"]["label"]

    @property
    def core_name(self):
        leaf = leaf_of(self.theta, self.r)
        return leaf["core"]["name"]

    @property
    def intensity_pct(self):
        return int(self.r * 100)

    @property
    def breadcrumb(self):
        return breadcrumb(self.theta, self.r)

    # ------------------------------------------------------------------ #
    #  Serialisation                                                       #
    # ------------------------------------------------------------------ #
    def to_dict(self):
        return {
            "start": self.start,
            "end": self.end,
            "theta": self.theta,
            "r": self.r,
        }

    @classmethod
    def from_dict(cls, d):
        return cls(
            start=d["start"],
            end=d["end"],
            theta=d.get("theta", 0.0),
            r=d.get("r", 0.0),
        )

    def copy(self):
        s = Strip(self.start, self.end, self.theta, self.r)
        return s

    def __repr__(self):
        return f"Strip({self.start:.2f}-{self.end:.2f} {self.breadcrumb} {self.intensity_pct}%)"
