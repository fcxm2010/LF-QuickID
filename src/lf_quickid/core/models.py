from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class ImageFile:
    path: Path
    size: int
    mtime_ns: int


@dataclass
class FaceRecord:
    image_path: Path
    bbox: tuple[int, int, int, int]
    embedding: np.ndarray
    thumbnail_jpeg: bytes | None = None


@dataclass
class FaceGroup:
    label: str
    faces: list[FaceRecord] = field(default_factory=list)
    label_source: str = "fallback"

    @property
    def image_count(self) -> int:
        return len({face.image_path for face in self.faces})
