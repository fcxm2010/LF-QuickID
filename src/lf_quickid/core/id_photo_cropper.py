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


@dataclass(frozen=True)
class SubjectBounds:
    top: float
    left: float
    right: float

    @property
    def width(self) -> float:
        return max(1.0, self.right - self.left)

    @property
    def center_x(self) -> float:
        return (self.left + self.right) / 2


def mm_to_pixels(size_mm: float, dpi: int) -> int:
    return max(1, int(round(size_mm / 25.4 * dpi)))


EYE_LINE_RATIO = 1 / 3
NORMAL_TOP_MARGIN_MM = 3.0
MIN_TOP_MARGIN_MM = 1.5
FOREGROUND_DIFF_THRESHOLD = 35.0
MAX_HEAD_WIDTH_FROM_FACE = 1.45


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
    matting_engine: object | None = None,
) -> list[CropResult]:
    images = collect_input_images(input_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    results: list[CropResult] = []
    for image_path in images:
        try:
            output_path = crop_one_id_photo(image_path, output_dir, preset, analyzer, matting_engine)
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
    matting_engine: object | None = None,
) -> Path:
    image = read_image_bgr(image_path)
    if image is None:
        raise ValueError("无法读取图片")

    faces = _detect_faces_for_crop(analyzer, image)
    if not faces:
        raise ValueError("未检测到人脸")

    face = max(faces, key=lambda item: _bbox_area(item.bbox))
    if matting_engine is not None:
        cropped = _crop_with_hivision_strategy(image, face, preset, matting_engine)
    else:
        crop_box = _calculate_crop_box(image, face, preset)
        x1, y1, x2, y2 = crop_box
        cropped = image[y1:y2, x1:x2]
        if cropped.size == 0:
            raise ValueError("裁切区域无效")

    resized = cv2.resize(cropped, (preset.width, preset.height), interpolation=cv2.INTER_AREA)
    output_dir.mkdir(parents=True, exist_ok=True)
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


def _crop_with_hivision_strategy(
    image_bgr: np.ndarray,
    face: DetectedFace,
    preset: CropPreset,
    matting_engine: object,
) -> np.ndarray:
    alpha = matting_engine.alpha_mask(image_bgr)
    if alpha.shape[:2] != image_bgr.shape[:2]:
        alpha = cv2.resize(alpha, (image_bgr.shape[1], image_bgr.shape[0]), interpolation=cv2.INTER_LINEAR)

    rgba = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2BGRA)
    rgba[:, :, 3] = _refine_crop_alpha(alpha)
    cropped_rgba = _hivision_adjust_rgba(rgba, face, preset)
    return _composite_rgba_on_background(cropped_rgba, _estimate_background_color(image_bgr))


def _hivision_adjust_rgba(image_rgba: np.ndarray, face: DetectedFace, preset: CropPreset) -> np.ndarray:
    # Adapted from HivisionIDPhotos' alpha-mask-based crop adjustment, with
    # LF QuickID's head-width ratio kept as the primary scale constraint.
    crop_width, crop_height, left, top = _hivision_crop_box(image_rgba, face, preset)
    return _crop_rgba_with_padding(left, top, left + crop_width, top + crop_height, image_rgba)


def _hivision_crop_box(
    image_rgba: np.ndarray,
    face: DetectedFace,
    preset: CropPreset,
) -> tuple[int, int, int, int]:
    image_height, image_width = image_rgba.shape[:2]
    x1, y1, x2, y2 = face.bbox
    face_width = max(1, x2 - x1)
    face_center_x = (x1 + x2) / 2
    eye_center = _eye_center(face)
    if eye_center is not None:
        face_center_x = eye_center[0]

    subject_bounds = _alpha_subject_bounds(image_rgba, face.bbox)
    head_width = _estimated_head_width(face_width, subject_bounds)
    crop_width = int(round(head_width / preset.head_ratio))
    crop_height = int(round(crop_width * preset.height / preset.width))
    crop_width = max(1, crop_width)
    crop_height = max(1, crop_height)

    left = int(round(face_center_x - crop_width / 2))
    if subject_bounds is not None:
        left = _shift_left_to_include_subject(left, crop_width, subject_bounds, image_width)
    else:
        left = _clamp_crop_origin(left, crop_width, image_width)

    top = _calculate_crop_top(face, eye_center, subject_bounds, crop_height, preset)
    top = _clamp_crop_origin(top, crop_height, image_height)

    return max(1, crop_width), max(1, crop_height), int(left), int(top)


def _alpha_subject_bounds(
    image_rgba: np.ndarray,
    face_box: tuple[int, int, int, int],
    threshold: int = 24,
) -> SubjectBounds | None:
    rect = _largest_alpha_rect(image_rgba, threshold)
    if rect is None:
        return None

    x, y, width, height = rect
    _, face_y1, _, face_y2 = face_box
    image_height = image_rgba.shape[0]
    face_height = max(1, face_y2 - face_y1)
    head_region_top = max(0, min(y, int(round(face_y1 - face_height * 0.45))))
    head_region_bottom = min(image_height, max(face_y2, int(round(face_y1 + face_height * 0.95))))
    if head_region_bottom <= head_region_top:
        return SubjectBounds(top=float(y), left=float(x), right=float(x + width))

    alpha = image_rgba[:, :, 3]
    head_mask = alpha[head_region_top:head_region_bottom] > threshold
    column_counts = head_mask.sum(axis=0)
    min_column_pixels = max(3, int(round((head_region_bottom - head_region_top) * 0.035)))
    columns = np.flatnonzero(column_counts >= min_column_pixels)
    if columns.size == 0:
        return SubjectBounds(top=float(y), left=float(x), right=float(x + width))

    face_x1, _, face_x2, _ = face_box
    left = min(float(columns[0]), float(face_x1))
    right = max(float(columns[-1] + 1), float(face_x2))
    return SubjectBounds(top=float(y), left=left, right=right)


def _largest_alpha_rect(image_rgba: np.ndarray, threshold: int) -> tuple[int, int, int, int] | None:
    if image_rgba.ndim != 3 or image_rgba.shape[2] != 4:
        raise ValueError("裁切区域缺少透明通道")

    alpha = image_rgba[:, :, 3]
    _, mask = cv2.threshold(alpha, threshold, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    contour = max(contours, key=cv2.contourArea)
    return cv2.boundingRect(contour)


def _shift_left_to_include_subject(
    left: int,
    crop_width: int,
    subject_bounds: SubjectBounds,
    image_width: int,
) -> int:
    min_left = int(round(subject_bounds.right - crop_width))
    max_left = int(round(subject_bounds.left))
    left = min(max(left, min_left), max_left)
    return _clamp_crop_origin(left, crop_width, image_width)


def _clamp_crop_origin(origin: int, crop_size: int, image_size: int) -> int:
    min_origin = min(0, image_size - crop_size)
    max_origin = max(0, image_size - crop_size)
    return int(min(max_origin, max(min_origin, origin)))


def _crop_rgba_with_padding(x1: int, y1: int, x2: int, y2: int, image_rgba: np.ndarray) -> np.ndarray:
    crop_width = max(1, x2 - x1)
    crop_height = max(1, y2 - y1)
    result = np.zeros((crop_height, crop_width, 4), dtype=np.uint8)

    source_x1 = max(0, x1)
    source_y1 = max(0, y1)
    source_x2 = min(image_rgba.shape[1], x2)
    source_y2 = min(image_rgba.shape[0], y2)
    if source_x2 <= source_x1 or source_y2 <= source_y1:
        return result

    target_x1 = source_x1 - x1
    target_y1 = source_y1 - y1
    target_x2 = target_x1 + (source_x2 - source_x1)
    target_y2 = target_y1 + (source_y2 - source_y1)
    result[target_y1:target_y2, target_x1:target_x2] = image_rgba[source_y1:source_y2, source_x1:source_x2]
    return result


def _refine_crop_alpha(alpha: np.ndarray) -> np.ndarray:
    alpha = alpha.astype(np.uint8)
    kernel = np.ones((3, 3), np.uint8)
    alpha = cv2.morphologyEx(alpha, cv2.MORPH_CLOSE, kernel, iterations=1)
    return cv2.GaussianBlur(alpha, (3, 3), 0)


def _composite_rgba_on_background(image_rgba: np.ndarray, color_bgr: np.ndarray) -> np.ndarray:
    bgr = image_rgba[:, :, :3].astype(np.float32)
    alpha = (image_rgba[:, :, 3].astype(np.float32) / 255.0)[:, :, None]
    background = np.full_like(bgr, color_bgr, dtype=np.float32)
    return np.clip(bgr * alpha + background * (1.0 - alpha), 0, 255).astype(np.uint8)


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

    eye_center = _eye_center(face)
    face_center_x = eye_center[0] if eye_center is not None else (x1 + x2) / 2
    subject_bounds = _estimate_subject_bounds(image_bgr, face.bbox, face_center_x)
    head_width = _estimated_head_width(face_width, subject_bounds)
    crop_width, crop_height = _base_crop_size(head_width, preset, image_width, image_height)

    crop_center_x = subject_bounds.center_x if subject_bounds is not None else face_center_x
    left = int(round(crop_center_x - crop_width / 2))
    top = _calculate_crop_top(face, eye_center, subject_bounds, crop_height, preset)

    left = min(max(0, left), max(0, image_width - crop_width))
    top = min(max(0, top), max(0, image_height - crop_height))
    return left, top, left + crop_width, top + crop_height


def _base_crop_size(
    head_width: float,
    preset: CropPreset,
    image_width: int,
    image_height: int,
) -> tuple[int, int]:
    crop_width = int(round(head_width / preset.head_ratio))
    crop_height = int(round(crop_width * preset.height / preset.width))

    return _fit_crop_size(crop_width, crop_height, preset, image_width, image_height)


def _estimated_head_width(face_width: int, subject_bounds: SubjectBounds | None) -> float:
    if subject_bounds is None:
        return float(face_width)
    return min(max(float(face_width), subject_bounds.width), face_width * MAX_HEAD_WIDTH_FROM_FACE)


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
    subject_bounds: SubjectBounds | None,
    crop_height: int,
    preset: CropPreset,
) -> int:
    _, y1, _, y2 = face.bbox
    if eye_center is None:
        face_center_y = (y1 + y2) / 2
        return int(round(face_center_y - crop_height * preset.face_center_y))

    top = eye_center[1] - crop_height * EYE_LINE_RATIO
    if subject_bounds is not None:
        normal_margin = _output_pixels_to_source(mm_to_pixels(NORMAL_TOP_MARGIN_MM, preset.dpi), crop_height, preset)
        min_margin = _output_pixels_to_source(mm_to_pixels(MIN_TOP_MARGIN_MM, preset.dpi), crop_height, preset)
        top = max(top, subject_bounds.top - normal_margin)
        top = min(top, subject_bounds.top - min_margin)
    return int(round(top))


def _output_pixels_to_source(output_pixels: int, crop_height: int, preset: CropPreset) -> float:
    return output_pixels * crop_height / preset.height


def _eye_center(face: DetectedFace) -> tuple[float, float] | None:
    if face.left_eye is None or face.right_eye is None:
        return None
    left_x, left_y = face.left_eye
    right_x, right_y = face.right_eye
    return (left_x + right_x) / 2, (left_y + right_y) / 2


def _estimate_subject_bounds(
    image_bgr: np.ndarray,
    face_box: tuple[int, int, int, int],
    center_x: float,
) -> SubjectBounds | None:
    x1, y1, x2, y2 = face_box
    image_height, image_width = image_bgr.shape[:2]
    face_width = max(1, x2 - x1)
    face_height = max(1, y2 - y1)
    half_search_width = face_width * 1.05
    search_left = int(max(0, round(center_x - half_search_width)))
    search_right = int(min(image_width, round(center_x + half_search_width)))
    search_bottom = int(min(image_height, max(y2, y1 + face_height * 1.1)))
    if search_right <= search_left or search_bottom <= 0:
        return _fallback_subject_bounds(face_box)

    background = _estimate_background_color(image_bgr)
    region = image_bgr[:search_bottom, search_left:search_right].astype(np.float32)
    diff = np.linalg.norm(region - background, axis=2)
    foreground = diff > FOREGROUND_DIFF_THRESHOLD
    row_counts = foreground.sum(axis=1)
    min_row_pixels = max(4, int((search_right - search_left) * 0.01))
    rows = np.flatnonzero(row_counts >= min_row_pixels)
    if rows.size == 0:
        return _fallback_subject_bounds(face_box)

    top = float(rows[0])
    head_top = int(max(0, min(top, y1 - face_height * 0.25)))
    head_bottom = int(min(search_bottom, y2))
    if head_bottom <= head_top:
        return _fallback_subject_bounds(face_box)

    head_foreground = foreground[head_top:head_bottom]
    column_counts = head_foreground.sum(axis=0)
    min_column_pixels = max(3, int((head_bottom - head_top) * 0.05))
    columns = np.flatnonzero(column_counts >= min_column_pixels)
    if columns.size == 0:
        return _fallback_subject_bounds(face_box)

    left = float(search_left + columns[0])
    right = float(search_left + columns[-1] + 1)
    return SubjectBounds(top=top, left=min(left, float(x1)), right=max(right, float(x2)))


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


def _fallback_subject_bounds(face_box: tuple[int, int, int, int]) -> SubjectBounds:
    x1, y1, x2, y2 = face_box
    face_height = y2 - y1
    return SubjectBounds(top=max(0.0, y1 - face_height * 0.18), left=float(x1), right=float(x2))


def _bbox_area(bbox: tuple[int, int, int, int]) -> int:
    return max(0, bbox[2] - bbox[0]) * max(0, bbox[3] - bbox[1])


def _unique_output_path(output_dir: Path, stem: str, suffix: str) -> Path:
    path = output_dir / f"{stem}_idphoto{suffix}"
    index = 2
    while path.exists():
        path = output_dir / f"{stem}_idphoto_{index}{suffix}"
        index += 1
    return path
