from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from lf_quickid.core.face_detector import InsightFaceAnalyzer
from lf_quickid.core.image_scanner import SUPPORTED_IMAGE_EXTENSIONS, scan_images


@dataclass(frozen=True)
class CropPreset:
    name: str
    width: int
    height: int
    head_ratio: float
    face_center_y: float
    width_mm: float | None = None
    height_mm: float | None = None
    dpi: int = 300
    quality: int = 8


@dataclass(frozen=True)
class CropResult:
    source: Path
    output: Path | None
    status: str
    message: str


def mm_to_pixels(size_mm: float, dpi: int) -> int:
    return max(1, int(round(size_mm / 25.4 * dpi)))


STANDARD_PRESETS: tuple[CropPreset, ...] = (
    CropPreset("一寸", mm_to_pixels(25, 300), mm_to_pixels(35, 300), 0.58, 0.43, 25, 35),
    CropPreset("二寸", mm_to_pixels(35, 300), mm_to_pixels(49, 300), 0.58, 0.43, 35, 49),
    CropPreset("小一寸", mm_to_pixels(22, 300), mm_to_pixels(32, 300), 0.58, 0.43, 22, 32),
    CropPreset("大一寸", mm_to_pixels(33, 300), mm_to_pixels(48, 300), 0.58, 0.43, 33, 48),
    CropPreset("小二寸", mm_to_pixels(35, 300), mm_to_pixels(45, 300), 0.58, 0.43, 35, 45),
    CropPreset("护照", mm_to_pixels(33, 300), mm_to_pixels(48, 300), 0.56, 0.43, 33, 48),
)


def collect_input_images(path: Path) -> list[Path]:
    if path.is_dir():
        return [image.path for image in scan_images(path)]
    if path.is_file() and path.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS:
        return [path]
    raise ValueError("请选择有效的图片文件或照片目录。")


def crop_id_photos(
    input_path: Path,
    output_dir: Path,
    preset: CropPreset,
    analyzer: InsightFaceAnalyzer,
) -> list[CropResult]:
    images = collect_input_images(input_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    results: list[CropResult] = []
    for image_path in images:
        try:
            output_path = crop_one_id_photo(image_path, output_dir, preset, analyzer)
        except Exception as exc:
            results.append(CropResult(image_path, None, "failed", str(exc)))
            continue
        results.append(CropResult(image_path, output_path, "ok", "已裁切"))
    return results


def crop_one_id_photo(
    image_path: Path,
    output_dir: Path,
    preset: CropPreset,
    analyzer: InsightFaceAnalyzer,
) -> Path:
    image = cv2.imdecode(np.fromfile(str(image_path), dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("无法读取图片")

    faces = analyzer.detect_faces(image)
    if not faces:
        raise ValueError("未检测到人脸")

    face = max(faces, key=lambda item: _bbox_area(item))
    crop_box = _calculate_crop_box(image.shape[1], image.shape[0], face, preset)
    x1, y1, x2, y2 = crop_box
    cropped = image[y1:y2, x1:x2]
    if cropped.size == 0:
        raise ValueError("裁切区域无效")

    resized = cv2.resize(cropped, (preset.width, preset.height), interpolation=cv2.INTER_AREA)
    output_path = _unique_output_path(output_dir, image_path.stem, image_path.suffix.lower() or ".jpg")
    _save_with_dpi(resized, output_path, preset.dpi, preset.quality)
    return output_path


def _save_with_dpi(image_bgr: np.ndarray, output_path: Path, dpi: int, quality: int) -> None:
    image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    image = Image.fromarray(image_rgb)
    save_quality = _quality_to_encoder_value(quality)
    save_kwargs = {"dpi": (dpi, dpi)}
    if output_path.suffix.lower() in {".jpg", ".jpeg"}:
        save_kwargs.update({"quality": save_quality, "subsampling": 0})
    elif output_path.suffix.lower() == ".webp":
        save_kwargs.update({"quality": save_quality})
    image.save(output_path, **save_kwargs)


def _quality_to_encoder_value(quality: int) -> int:
    quality = min(10, max(1, quality))
    return 50 + quality * 5


def _calculate_crop_box(
    image_width: int,
    image_height: int,
    face_box: tuple[int, int, int, int],
    preset: CropPreset,
) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = face_box
    face_width = max(1, x2 - x1)
    face_height = max(1, y2 - y1)
    crop_width = int(round(max(face_width, face_height) / preset.head_ratio))
    crop_height = int(round(crop_width * preset.height / preset.width))

    min_height_for_face = int(round(face_height / preset.head_ratio))
    if crop_height < min_height_for_face:
        crop_height = min_height_for_face
        crop_width = int(round(crop_height * preset.width / preset.height))

    crop_width = min(crop_width, image_width)
    crop_height = min(crop_height, image_height)

    face_center_x = (x1 + x2) / 2
    face_center_y = (y1 + y2) / 2
    left = int(round(face_center_x - crop_width / 2))
    top = int(round(face_center_y - crop_height * preset.face_center_y))

    left = min(max(0, left), max(0, image_width - crop_width))
    top = min(max(0, top), max(0, image_height - crop_height))
    return left, top, left + crop_width, top + crop_height


def _bbox_area(bbox: tuple[int, int, int, int]) -> int:
    return max(0, bbox[2] - bbox[0]) * max(0, bbox[3] - bbox[1])


def _unique_output_path(output_dir: Path, stem: str, suffix: str) -> Path:
    path = output_dir / f"{stem}_idphoto{suffix}"
    index = 2
    while path.exists():
        path = output_dir / f"{stem}_idphoto_{index}{suffix}"
        index += 1
    return path
