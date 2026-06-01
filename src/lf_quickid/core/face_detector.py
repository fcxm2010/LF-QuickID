from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from lf_quickid.core.image_io import read_image_bgr
from lf_quickid.core.models import FaceRecord


MODEL_NAME = "buffalo_l"
MODEL_URL = f"https://github.com/deepinsight/insightface/releases/download/v0.7/{MODEL_NAME}.zip"
MODEL_DIR = Path.home() / ".insightface" / "models" / MODEL_NAME


@dataclass(frozen=True)
class DetectedFace:
    bbox: tuple[int, int, int, int]
    left_eye: tuple[float, float] | None = None
    right_eye: tuple[float, float] | None = None


class FaceAnalyzerUnavailable(RuntimeError):
    pass


class InsightFaceAnalyzer:
    def __init__(self) -> None:
        try:
            from insightface.app import FaceAnalysis
        except Exception as exc:  # pragma: no cover - depends on optional runtime install
            raise FaceAnalyzerUnavailable(
                "InsightFace is not available. Install dependencies with: pip install -e ."
            ) from exc

        try:
            self._app = FaceAnalysis(name=MODEL_NAME, providers=["CPUExecutionProvider"])
            self._app.prepare(ctx_id=-1, det_size=(640, 640))
        except Exception as exc:  # pragma: no cover - depends on network/model cache
            raise FaceAnalyzerUnavailable(_model_error_message(exc)) from exc

    def analyze_image(self, image_path: Path) -> list[FaceRecord]:
        image = read_image_bgr(image_path)
        if image is None:
            return []

        faces = self._get_faces(image)
        records: list[FaceRecord] = []
        for face in faces:
            embedding = getattr(face, "normed_embedding", None)
            if embedding is None:
                embedding = getattr(face, "embedding", None)
            if embedding is None:
                continue

            bbox = _face_bbox(face, image.shape[1], image.shape[0])
            if bbox is None:
                continue

            records.append(
                FaceRecord(
                    image_path=image_path,
                    bbox=bbox,
                    embedding=np.asarray(embedding, dtype=np.float32),
                    thumbnail_jpeg=_crop_thumbnail(image, bbox),
                )
            )
        return records

    def detect_faces(self, image_bgr: np.ndarray) -> list[tuple[int, int, int, int]]:
        return [face.bbox for face in self.detect_face_details(image_bgr)]

    def detect_face_details(self, image_bgr: np.ndarray) -> list[DetectedFace]:
        if image_bgr is None or image_bgr.ndim != 3:
            return []

        faces = self._get_faces(image_bgr)
        detected: list[DetectedFace] = []
        for face in faces:
            bbox = _face_bbox(face, image_bgr.shape[1], image_bgr.shape[0])
            if bbox is not None:
                left_eye, right_eye = _face_eye_points(face, image_bgr.shape[1], image_bgr.shape[0])
                detected.append(DetectedFace(bbox=bbox, left_eye=left_eye, right_eye=right_eye))
        return detected

    def _get_faces(self, image_bgr: np.ndarray) -> list[object]:
        try:
            faces = self._app.get(image_bgr)
        except AttributeError as exc:
            if "'NoneType' object has no attribute 'shape'" in str(exc):
                return []
            raise
        return list(faces or [])


def _face_bbox(face: object, image_width: int, image_height: int) -> tuple[int, int, int, int] | None:
    x1, y1, x2, y2 = [int(round(value)) for value in face.bbox]
    x1 = max(0, x1)
    y1 = max(0, y1)
    x2 = min(image_width, x2)
    y2 = min(image_height, y2)
    if x2 <= x1 or y2 <= y1:
        return None
    return x1, y1, x2, y2


def _face_eye_points(
    face: object,
    image_width: int,
    image_height: int,
) -> tuple[tuple[float, float] | None, tuple[float, float] | None]:
    keypoints = getattr(face, "kps", None)
    if keypoints is None:
        return None, None

    points = np.asarray(keypoints, dtype=np.float32)
    if points.ndim != 2 or points.shape[0] < 2 or points.shape[1] < 2:
        return None, None

    left_eye = _bounded_point(points[0], image_width, image_height)
    right_eye = _bounded_point(points[1], image_width, image_height)
    return left_eye, right_eye


def _bounded_point(point: np.ndarray, image_width: int, image_height: int) -> tuple[float, float] | None:
    x = float(point[0])
    y = float(point[1])
    if not np.isfinite(x) or not np.isfinite(y):
        return None
    return min(max(0.0, x), float(image_width)), min(max(0.0, y), float(image_height))


def _crop_thumbnail(image_bgr: np.ndarray, bbox: tuple[int, int, int, int]) -> bytes | None:
    x1, y1, x2, y2 = bbox
    crop = image_bgr[y1:y2, x1:x2]
    if crop.size == 0:
        return None

    rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
    pil = Image.fromarray(rgb)
    pil.thumbnail((180, 180))

    buffer = BytesIO()
    pil.save(buffer, format="JPEG", quality=88)
    return buffer.getvalue()


def _model_error_message(exc: Exception) -> str:
    return (
        f"本地人脸模型 {MODEL_NAME} 加载失败。\n\n"
        "这通常是首次运行时从 GitHub 下载模型中断导致的，不是照片处理失败。\n\n"
        "可以先在终端手动下载模型：\n"
        f"mkdir -p \"$HOME/.insightface/models\"\n"
        f"curl --http1.1 -L --retry 8 --retry-all-errors --continue-at - "
        f"-o \"$HOME/.insightface/models/{MODEL_NAME}.zip\" \"{MODEL_URL}\"\n"
        f"unzip -o \"$HOME/.insightface/models/{MODEL_NAME}.zip\" -d \"$HOME/.insightface/models\"\n\n"
        f"模型目录应为：{MODEL_DIR}\n\n"
        f"原始错误：{exc}"
    )
