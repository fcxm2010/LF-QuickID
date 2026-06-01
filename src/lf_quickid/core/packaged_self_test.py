from __future__ import annotations

import tempfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from time import perf_counter
from traceback import format_exc
from typing import Any, Callable

import cv2
import numpy as np
from PIL import Image, ImageDraw

from lf_quickid.core.background_replacer import PortraitMattingEngine, background_presets, replace_background_one
from lf_quickid.core.face_clusterer import cluster_faces
from lf_quickid.core.face_detector import DetectedFace, InsightFaceAnalyzer
from lf_quickid.core.face_group_exporter import export_face_groups
from lf_quickid.core.id_photo_cropper import STANDARD_PRESETS, crop_one_id_photo
from lf_quickid.core.id_photo_layout import PAPER_PRESETS, layout_id_photos
from lf_quickid.core.image_io import read_image_bgr
from lf_quickid.core.models import FaceRecord


@dataclass(frozen=True)
class SelfTestStep:
    name: str
    ok: bool
    seconds: float
    details: dict[str, Any]
    error: str | None = None


class _StaticFaceAnalyzer:
    def __init__(self, face: DetectedFace) -> None:
        self._face = face

    def detect_face_details(self, image_bgr: np.ndarray) -> list[DetectedFace]:
        return [self._face]


def run_packaged_self_test(output_dir: Path | None = None) -> dict[str, Any]:
    work_dir = output_dir or Path(tempfile.mkdtemp(prefix="lf_quickid_self_test_"))
    work_dir.mkdir(parents=True, exist_ok=True)
    source_path = work_dir / "测试输入.jpg"
    _create_test_portrait(source_path)

    state: dict[str, Any] = {"work_dir": str(work_dir), "source_path": str(source_path)}
    steps = [
        _run_step("image_io", lambda: _test_image_io(source_path, state)),
        _run_step("insightface", lambda: _test_insightface(source_path, state)),
        _run_step("rembg_background", lambda: _test_background_replace(source_path, work_dir, state)),
        _run_step("id_photo_crop", lambda: _test_id_photo_crop(source_path, work_dir, state)),
        _run_step("id_photo_layout", lambda: _test_id_photo_layout(work_dir, state)),
        _run_step("face_group_export", lambda: _test_face_group_export(source_path, work_dir, state)),
    ]

    return {
        "ok": all(step.ok for step in steps),
        "work_dir": str(work_dir),
        "steps": [_step_to_dict(step) for step in steps],
    }


def _run_step(name: str, func: Callable[[], dict[str, Any]]) -> SelfTestStep:
    started = perf_counter()
    try:
        details = func()
    except Exception as exc:
        return SelfTestStep(
            name=name,
            ok=False,
            seconds=round(perf_counter() - started, 3),
            details={},
            error=f"{exc}\n{format_exc()}",
        )
    return SelfTestStep(name=name, ok=True, seconds=round(perf_counter() - started, 3), details=details)


def _step_to_dict(step: SelfTestStep) -> dict[str, Any]:
    return {
        "name": step.name,
        "ok": step.ok,
        "seconds": step.seconds,
        "details": step.details,
        "error": step.error,
    }


def _create_test_portrait(path: Path) -> None:
    image = Image.new("RGB", (720, 960), (218, 142, 66))
    draw = ImageDraw.Draw(image)
    draw.ellipse((260, 130, 460, 340), fill=(78, 52, 42))
    draw.ellipse((285, 165, 435, 335), fill=(226, 181, 148))
    draw.ellipse((315, 225, 328, 238), fill=(20, 24, 28))
    draw.ellipse((392, 225, 405, 238), fill=(20, 24, 28))
    draw.arc((325, 245, 395, 300), 15, 165, fill=(150, 74, 69), width=4)
    draw.rounded_rectangle((250, 360, 470, 820), radius=42, fill=(42, 75, 120))
    draw.rectangle((335, 330, 385, 410), fill=(226, 181, 148))
    image.save(path, quality=95, subsampling=0, dpi=(300, 300))


def _test_image_io(source_path: Path, state: dict[str, Any]) -> dict[str, Any]:
    image = read_image_bgr(source_path)
    if image is None:
        raise RuntimeError("read_image_bgr returned None")
    state["image_shape"] = image.shape
    return {"shape": list(image.shape)}


def _test_insightface(source_path: Path, state: dict[str, Any]) -> dict[str, Any]:
    analyzer = InsightFaceAnalyzer()
    image = read_image_bgr(source_path)
    if image is None:
        raise RuntimeError("self-test image disappeared")
    faces = analyzer.detect_face_details(image)
    state["detected_face_count"] = len(faces)
    return {"detected_face_count": len(faces)}


def _test_background_replace(source_path: Path, work_dir: Path, state: dict[str, Any]) -> dict[str, Any]:
    engine = PortraitMattingEngine()
    state["matting_engine"] = engine
    output_dir = work_dir / "background"
    output_path = replace_background_one(source_path, output_dir, background_presets()[0], engine)
    with Image.open(output_path) as image:
        size = image.size
    return {"output": str(output_path), "size": list(size)}


def _test_id_photo_crop(source_path: Path, work_dir: Path, state: dict[str, Any]) -> dict[str, Any]:
    engine = state.get("matting_engine")
    if engine is None:
        engine = PortraitMattingEngine()
    preset = STANDARD_PRESETS[0]
    face = DetectedFace(bbox=(260, 130, 460, 340), left_eye=(321, 232), right_eye=(399, 232))
    output_dir = work_dir / "crop"
    output_path = crop_one_id_photo(source_path, output_dir, preset, _StaticFaceAnalyzer(face), engine)
    with Image.open(output_path) as image:
        size = image.size
        dpi = image.info.get("dpi")
    state["crop_output"] = str(output_path)
    return {"output": str(output_path), "size": list(size), "dpi": list(dpi or ())}


def _test_id_photo_layout(work_dir: Path, state: dict[str, Any]) -> dict[str, Any]:
    crop_output = state.get("crop_output")
    if not crop_output:
        raise RuntimeError("crop output is missing")
    output_dir = work_dir / "layout"
    preset = STANDARD_PRESETS[0]
    results = layout_id_photos(Path(crop_output), output_dir, preset, PAPER_PRESETS[0], preset.dpi, add_border=True)
    if not results:
        raise RuntimeError("layout_id_photos returned no output")
    with Image.open(results[0].output) as image:
        size = image.size
    return {"output": str(results[0].output), "placed_count": results[0].placed_count, "size": list(size)}


def _test_face_group_export(source_path: Path, work_dir: Path, state: dict[str, Any]) -> dict[str, Any]:
    thumbnail = _thumbnail_bytes(source_path)
    records = [
        FaceRecord(source_path, (260, 130, 460, 340), np.array([1.0, 0.0, 0.0], dtype=np.float32), thumbnail),
        FaceRecord(source_path, (262, 132, 462, 342), np.array([0.98, 0.02, 0.0], dtype=np.float32), thumbnail),
    ]
    groups = cluster_faces(records)
    summary = export_face_groups(groups, work_dir / "groups")
    if summary.copied_count != 1:
        raise RuntimeError(f"expected one unique copied image, got {summary.copied_count}")
    return {"group_count": summary.group_count, "copied_count": summary.copied_count}


def _thumbnail_bytes(source_path: Path) -> bytes:
    with Image.open(source_path) as image:
        image.thumbnail((180, 180))
        buffer = BytesIO()
        image.save(buffer, format="JPEG", quality=85)
        return buffer.getvalue()
