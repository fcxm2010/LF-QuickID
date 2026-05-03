from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from lf_quickid.core.image_scanner import SUPPORTED_IMAGE_EXTENSIONS, scan_images


BACKGROUND_COLORS: dict[str, tuple[str, tuple[int, int, int]]] = {
    "red": ("红底", (27, 0, 217)),
    "blue": ("蓝底", (219, 142, 67)),
    "white": ("白底", (255, 255, 255)),
}

MATTING_MODES: dict[str, tuple[str, str]] = {
    "fast": ("快速模式", "isnet-general-use"),
    "quality": ("高质量人像", "birefnet-portrait"),
}


@dataclass(frozen=True)
class BackgroundPreset:
    key: str
    name: str
    color_bgr: tuple[int, int, int]


@dataclass(frozen=True)
class BackgroundReplaceResult:
    source: Path
    output: Path | None
    status: str
    message: str


@dataclass(frozen=True)
class MattingMode:
    key: str
    name: str
    model_name: str


class MattingUnavailable(RuntimeError):
    pass


class PortraitMattingEngine:
    def __init__(self, model_name: str = "isnet-general-use") -> None:
        try:
            from rembg import new_session
        except Exception as exc:  # pragma: no cover - depends on optional runtime install
            raise MattingUnavailable("人像抠图依赖不可用，请先执行：pip install -e .") from exc

        try:
            self._session = new_session(model_name)
        except Exception as exc:  # pragma: no cover - depends on model cache/network
            raise MattingUnavailable(_model_error_message(model_name, exc)) from exc

    def alpha_mask(self, image_bgr: np.ndarray) -> np.ndarray:
        try:
            from rembg import remove
        except Exception as exc:  # pragma: no cover - depends on optional runtime install
            raise MattingUnavailable("人像抠图依赖不可用，请先执行：pip install -e .") from exc

        image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        rgba = remove(image_rgb, session=self._session, only_mask=False)
        rgba_array = np.asarray(rgba)
        if rgba_array.ndim != 3 or rgba_array.shape[2] < 4:
            raise ValueError("抠图模型未返回有效透明通道")
        return rgba_array[:, :, 3].astype(np.uint8)


def background_presets() -> tuple[BackgroundPreset, ...]:
    return tuple(BackgroundPreset(key, name, color) for key, (name, color) in BACKGROUND_COLORS.items())


def matting_modes() -> tuple[MattingMode, ...]:
    return tuple(MattingMode(key, name, model_name) for key, (name, model_name) in MATTING_MODES.items())


def collect_input_images(path: Path) -> list[Path]:
    if path.is_dir():
        return [image.path for image in scan_images(path)]
    if path.is_file() and path.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS:
        return [path]
    raise ValueError("请选择有效的图片文件或照片目录。")


def replace_background_one(
    image_path: Path,
    output_dir: Path,
    preset: BackgroundPreset,
    engine: PortraitMattingEngine,
    quality: int = 95,
) -> Path:
    image = cv2.imdecode(np.fromfile(str(image_path), dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("无法读取图片")

    alpha = engine.alpha_mask(image)
    if alpha.shape[:2] != image.shape[:2]:
        alpha = cv2.resize(alpha, (image.shape[1], image.shape[0]), interpolation=cv2.INTER_LINEAR)

    refined_alpha = _refine_alpha(alpha)
    composited = _composite_background(image, refined_alpha, preset.color_bgr)

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = _unique_output_path(output_dir, image_path.stem, preset.key, image_path.suffix.lower() or ".jpg")
    _save_image(composited, output_path, quality)
    return output_path


def replace_backgrounds(
    input_path: Path,
    output_dir: Path,
    preset: BackgroundPreset,
    engine: PortraitMattingEngine,
    quality: int = 95,
) -> list[BackgroundReplaceResult]:
    images = collect_input_images(input_path)
    results: list[BackgroundReplaceResult] = []
    for image_path in images:
        try:
            output_path = replace_background_one(image_path, output_dir, preset, engine, quality)
        except Exception as exc:
            results.append(BackgroundReplaceResult(image_path, None, "failed", str(exc)))
            continue
        results.append(BackgroundReplaceResult(image_path, output_path, "ok", "已换背景"))
    return results


def _refine_alpha(alpha: np.ndarray) -> np.ndarray:
    alpha = alpha.astype(np.uint8)
    kernel = np.ones((3, 3), np.uint8)
    alpha = cv2.morphologyEx(alpha, cv2.MORPH_CLOSE, kernel, iterations=1)
    alpha = cv2.GaussianBlur(alpha, (3, 3), 0)
    return alpha


def _composite_background(image_bgr: np.ndarray, alpha: np.ndarray, color_bgr: tuple[int, int, int]) -> np.ndarray:
    alpha_f = (alpha.astype(np.float32) / 255.0)[:, :, None]
    background = np.full_like(image_bgr, color_bgr, dtype=np.uint8)
    composited = image_bgr.astype(np.float32) * alpha_f + background.astype(np.float32) * (1.0 - alpha_f)
    return np.clip(composited, 0, 255).astype(np.uint8)


def _save_image(image_bgr: np.ndarray, output_path: Path, quality: int) -> None:
    image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    image = Image.fromarray(image_rgb)
    suffix = output_path.suffix.lower()
    save_kwargs: dict[str, int] = {}
    if suffix in {".jpg", ".jpeg"}:
        save_kwargs.update({"quality": min(100, max(1, quality)), "subsampling": 0})
    elif suffix == ".webp":
        save_kwargs.update({"quality": min(100, max(1, quality))})
    image.save(output_path, **save_kwargs)


def _unique_output_path(output_dir: Path, stem: str, background_key: str, suffix: str) -> Path:
    if suffix not in SUPPORTED_IMAGE_EXTENSIONS:
        suffix = ".jpg"
    path = output_dir / f"{stem}_bg_{background_key}{suffix}"
    index = 2
    while path.exists():
        path = output_dir / f"{stem}_bg_{background_key}_{index}{suffix}"
        index += 1
    return path


def _model_error_message(model_name: str, exc: Exception) -> str:
    return (
        f"人像抠图模型 {model_name} 加载失败。\n\n"
        "首次运行时需要下载本地模型文件，请确认网络可访问模型源。\n\n"
        f"原始错误：{exc}"
    )
