from __future__ import annotations

from pathlib import Path

import cv2
from PIL import Image

from lf_quickid.core.image_io import read_image_bgr


def test_read_image_bgr_reads_standard_jpeg(tmp_path: Path) -> None:
    image_path = tmp_path / "photo.jpg"
    Image.new("RGB", (12, 8), (255, 0, 0)).save(image_path)

    image = read_image_bgr(image_path)

    assert image is not None
    assert image.shape == (8, 12, 3)


def test_read_image_bgr_falls_back_to_pillow(monkeypatch, tmp_path: Path) -> None:
    image_path = tmp_path / "photo.jpg"
    Image.new("CMYK", (10, 6), (0, 255, 255, 0)).save(image_path)
    monkeypatch.setattr(cv2, "imdecode", lambda *args, **kwargs: None)

    image = read_image_bgr(image_path)

    assert image is not None
    assert image.shape == (6, 10, 3)
