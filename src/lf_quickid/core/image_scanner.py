from __future__ import annotations

from pathlib import Path

from lf_quickid.core.models import ImageFile


SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}


def scan_images(directory: Path) -> list[ImageFile]:
    if not directory.exists() or not directory.is_dir():
        raise ValueError(f"Not a directory: {directory}")

    images: list[ImageFile] = []
    for path in directory.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_IMAGE_EXTENSIONS:
            continue
        try:
            stat = path.stat()
        except OSError:
            continue
        images.append(ImageFile(path=path, size=stat.st_size, mtime_ns=stat.st_mtime_ns))

    return sorted(images, key=lambda item: str(item.path).lower())
