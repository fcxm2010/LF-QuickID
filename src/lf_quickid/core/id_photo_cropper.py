from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from lf_quickid.core.face_detector import DetectedFace, InsightFaceAnalyzer
from lf_quickid.core.image_io import read_image_bgr
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


EYE_LINE_RATIO = 1 / 3
NORMAL_TOP_MARGIN_MM = 3.0
MIN_TOP_MARGIN_MM = 1.5
FOREGROUND_DIFF_THRESHOLD = 35.0


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
    image = read_image_bgr(image_path)
    if image is None:
        raise ValueError("无法读取图片")

    faces = _detect_faces_for_crop(analyzer, image)
    if not faces:
        raise ValueError("未检测到人脸")

    face = max(faces, key=lambda item: _bbox_area(item.bbox))
    crop_box = _calculate_crop_box(image, face, preset)
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


def _detect_faces_for_crop(analyzer: InsightFaceAnalyzer, image_bgr: np.ndarray) -> list[DetectedFace]:
    if hasattr(analyzer, "detect_face_details"):
        return analyzer.detect_face_details(image_bgr)
    return [DetectedFace(bbox=bbox) for bbox in analyzer.detect_faces(image_bgr)]


def _calculate_crop_box(
    image_bgr: np.ndarray,
    face: DetectedFace,
    preset: CropPreset,
) -> tuple[int, int, int, int]:
    image_height, image_width = image_bgr.shape[:2]
    x1, y1, x2, y2 = face.bbox
    face_width = max(1, x2 - x1)
    face_height = max(1, y2 - y1)
    crop_width, crop_height = _base_crop_size(face_width, face_height, preset, image_width, image_height)

    eye_center = _eye_center(face)
    face_center_x = eye_center[0] if eye_center is not None else (x1 + x2) / 2
    subject_top = _estimate_subject_top(image_bgr, face.bbox, face_center_x, crop_width)

    if eye_center is not None and subject_top is not None:
        crop_width, crop_height = _expand_crop_for_eye_line(
            eye_y=eye_center[1],
            subject_top=subject_top,
            crop_width=crop_width,
            crop_height=crop_height,
            preset=preset,
            image_width=image_width,
            image_height=image_height,
        )

    left = int(round(face_center_x - crop_width / 2))
    top = _calculate_crop_top(face, eye_center, subject_top, crop_height, preset)

    left = min(max(0, left), max(0, image_width - crop_width))
    top = min(max(0, top), max(0, image_height - crop_height))
    return left, top, left + crop_width, top + crop_height


def _base_crop_size(
    face_width: int,
    face_height: int,
    preset: CropPreset,
    image_width: int,
    image_height: int,
) -> tuple[int, int]:
    crop_width = int(round(max(face_width, face_height) / preset.head_ratio))
    crop_height = int(round(crop_width * preset.height / preset.width))

    min_height_for_face = int(round(face_height / preset.head_ratio))
    if crop_height < min_height_for_face:
        crop_height = min_height_for_face
        crop_width = int(round(crop_height * preset.width / preset.height))

    return _fit_crop_size(crop_width, crop_height, preset, image_width, image_height)


def _expand_crop_for_eye_line(
    eye_y: float,
    subject_top: float,
    crop_width: int,
    crop_height: int,
    preset: CropPreset,
    image_width: int,
    image_height: int,
) -> tuple[int, int]:
    required_height = _required_crop_height_for_margin(
        eye_y - subject_top,
        mm_to_pixels(MIN_TOP_MARGIN_MM, preset.dpi),
        preset.height,
    )
    if required_height <= crop_height:
        return crop_width, crop_height

    target_height = min(required_height, image_height)
    target_width = int(round(target_height * preset.width / preset.height))
    fitted_width, fitted_height = _fit_crop_size(target_width, target_height, preset, image_width, image_height)
    if fitted_height <= crop_height:
        return crop_width, crop_height
    return fitted_width, fitted_height


def _required_crop_height_for_margin(head_to_eye_distance: float, margin_px: int, output_height: int) -> int:
    if head_to_eye_distance <= 0:
        return 0
    denominator = EYE_LINE_RATIO - margin_px / output_height
    if denominator <= 0:
        return 0
    return int(np.ceil(head_to_eye_distance / denominator))


def _fit_crop_size(
    crop_width: int,
    crop_height: int,
    preset: CropPreset,
    image_width: int,
    image_height: int,
) -> tuple[int, int]:
    crop_width = max(1, crop_width)
    crop_height = max(1, crop_height)

    if crop_width > image_width:
        crop_width = image_width
        crop_height = int(round(crop_width * preset.height / preset.width))
    if crop_height > image_height:
        crop_height = image_height
        crop_width = int(round(crop_height * preset.width / preset.height))
    if crop_width > image_width:
        crop_width = image_width
    if crop_height > image_height:
        crop_height = image_height

    return max(1, crop_width), max(1, crop_height)


def _calculate_crop_top(
    face: DetectedFace,
    eye_center: tuple[float, float] | None,
    subject_top: float | None,
    crop_height: int,
    preset: CropPreset,
) -> int:
    _, y1, _, y2 = face.bbox
    if eye_center is None:
        face_center_y = (y1 + y2) / 2
        return int(round(face_center_y - crop_height * preset.face_center_y))

    top = eye_center[1] - crop_height * EYE_LINE_RATIO
    if subject_top is not None:
        normal_margin = _output_pixels_to_source(mm_to_pixels(NORMAL_TOP_MARGIN_MM, preset.dpi), crop_height, preset)
        min_margin = _output_pixels_to_source(mm_to_pixels(MIN_TOP_MARGIN_MM, preset.dpi), crop_height, preset)
        top = max(top, subject_top - normal_margin)
        top = min(top, subject_top - min_margin)
    return int(round(top))


def _output_pixels_to_source(output_pixels: int, crop_height: int, preset: CropPreset) -> float:
    return output_pixels * crop_height / preset.height


def _eye_center(face: DetectedFace) -> tuple[float, float] | None:
    if face.left_eye is None or face.right_eye is None:
        return None
    left_x, left_y = face.left_eye
    right_x, right_y = face.right_eye
    return (left_x + right_x) / 2, (left_y + right_y) / 2


def _estimate_subject_top(
    image_bgr: np.ndarray,
    face_box: tuple[int, int, int, int],
    center_x: float,
    crop_width: int,
) -> float | None:
    x1, y1, x2, y2 = face_box
    image_height, image_width = image_bgr.shape[:2]
    half_search_width = max((x2 - x1) * 0.9, crop_width * 0.45)
    search_left = int(max(0, round(center_x - half_search_width)))
    search_right = int(min(image_width, round(center_x + half_search_width)))
    search_bottom = int(min(image_height, max(y2, y1 + (y2 - y1) * 1.2)))
    if search_right <= search_left or search_bottom <= 0:
        return _fallback_subject_top(face_box)

    background = _estimate_background_color(image_bgr)
    region = image_bgr[:search_bottom, search_left:search_right].astype(np.float32)
    diff = np.linalg.norm(region - background, axis=2)
    foreground = diff > FOREGROUND_DIFF_THRESHOLD
    row_counts = foreground.sum(axis=1)
    min_row_pixels = max(4, int((search_right - search_left) * 0.01))
    rows = np.flatnonzero(row_counts >= min_row_pixels)
    if rows.size > 0:
        return float(rows[0])
    return _fallback_subject_top(face_box)


def _estimate_background_color(image_bgr: np.ndarray) -> np.ndarray:
    image_height, image_width = image_bgr.shape[:2]
    sample_height = max(1, int(round(image_height * 0.08)))
    sample_width = max(1, int(round(image_width * 0.12)))
    samples = np.concatenate(
        (
            image_bgr[:sample_height, :sample_width].reshape(-1, 3),
            image_bgr[:sample_height, image_width - sample_width :].reshape(-1, 3),
        ),
        axis=0,
    )
    return np.median(samples.astype(np.float32), axis=0)


def _fallback_subject_top(face_box: tuple[int, int, int, int]) -> float:
    _, y1, _, y2 = face_box
    return max(0.0, y1 - (y2 - y1) * 0.18)


def _bbox_area(bbox: tuple[int, int, int, int]) -> int:
    return max(0, bbox[2] - bbox[0]) * max(0, bbox[3] - bbox[1])


def _unique_output_path(output_dir: Path, stem: str, suffix: str) -> Path:
    path = output_dir / f"{stem}_idphoto{suffix}"
    index = 2
    while path.exists():
        path = output_dir / f"{stem}_idphoto_{index}{suffix}"
        index += 1
    return path
