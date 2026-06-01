from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from PIL import Image


def read_image_bgr(image_path: Path) -> np.ndarray | None:
    try:
        data = np.fromfile(str(image_path), dtype=np.uint8)
    except OSError:
        data = np.array([], dtype=np.uint8)

    if data.size:
        image = cv2.imdecode(data, cv2.IMREAD_COLOR)
        if image is not None:
            return image

    try:
        with Image.open(image_path) as pil_image:
            rgb = pil_image.convert("RGB")
            return cv2.cvtColor(np.asarray(rgb), cv2.COLOR_RGB2BGR)
    except Exception:
        return None
