from __future__ import annotations

from io import BytesIO
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from lf_quickid.core.models import FaceRecord


MODEL_NAME = "buffalo_l"
MODEL_URL = f"https://github.com/deepinsight/insightface/releases/download/v0.7/{MODEL_NAME}.zip"
MODEL_DIR = Path.home() / ".insightface" / "models" / MODEL_NAME


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
        image = cv2.imdecode(np.fromfile(str(image_path), dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            return []

        faces = self._app.get(image)
        records: list[FaceRecord] = []
        for face in faces:
            embedding = getattr(face, "normed_embedding", None)
            if embedding is None:
                embedding = getattr(face, "embedding", None)
            if embedding is None:
                continue

            x1, y1, x2, y2 = [int(round(value)) for value in face.bbox]
            x1 = max(0, x1)
            y1 = max(0, y1)
            x2 = min(image.shape[1], x2)
            y2 = min(image.shape[0], y2)
            if x2 <= x1 or y2 <= y1:
                continue

            records.append(
                FaceRecord(
                    image_path=image_path,
                    bbox=(x1, y1, x2, y2),
                    embedding=np.asarray(embedding, dtype=np.float32),
                    thumbnail_jpeg=_crop_thumbnail(image, (x1, y1, x2, y2)),
                )
            )
        return records


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
