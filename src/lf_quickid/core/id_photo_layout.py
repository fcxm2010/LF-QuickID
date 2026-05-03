from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageOps

from lf_quickid.core.id_photo_cropper import CropPreset, collect_input_images, mm_to_pixels


DEFAULT_SPACING_PX = 25
OUTPUT_QUALITY = 100
SUPPORTED_LAYOUT_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}


@dataclass(frozen=True)
class PaperPreset:
    name: str
    width_mm: float
    height_mm: float


@dataclass(frozen=True)
class LayoutPlan:
    paper_width_px: int
    paper_height_px: int
    columns: int
    rows: int
    count: int
    start_x: int
    start_y: int
    placed_width_px: int
    placed_height_px: int
    orientation: str


@dataclass(frozen=True)
class LayoutResult:
    source: Path
    output: Path
    placed_count: int
    message: str


class LayoutValidationError(ValueError):
    pass


PAPER_PRESETS: tuple[PaperPreset, ...] = (
    PaperPreset("5寸", 127, 89),
    PaperPreset("6寸", 152, 102),
    PaperPreset("A3", 297, 420),
    PaperPreset("A4", 210, 297),
)


def layout_id_photos(
    input_path: Path,
    output_dir: Path,
    photo_preset: CropPreset,
    paper: PaperPreset,
    dpi: int,
    add_border: bool,
    spacing_px: int = DEFAULT_SPACING_PX,
) -> list[LayoutResult]:
    images = collect_input_images(input_path)
    if not images:
        return []

    expected_size = (photo_preset.width, photo_preset.height)
    validate_layout_inputs(images, expected_size, dpi)
    output_dir.mkdir(parents=True, exist_ok=True)

    results: list[LayoutResult] = []
    for image_path in images:
        output_path, plan = layout_one_id_photo(image_path, output_dir, paper, dpi, add_border, spacing_px)
        results.append(LayoutResult(image_path, output_path, plan.count, f"已排版 {plan.count} 张"))
    return results


def layout_one_id_photo(
    image_path: Path,
    output_dir: Path,
    paper: PaperPreset,
    dpi: int,
    add_border: bool,
    spacing_px: int = DEFAULT_SPACING_PX,
) -> tuple[Path, LayoutPlan]:
    with Image.open(image_path) as opened:
        photo = ImageOps.exif_transpose(opened).convert("RGB")

    if add_border:
        photo = ImageOps.expand(photo, border=1, fill="black")

    plan = calculate_best_layout(photo.size[0], photo.size[1], paper, dpi, spacing_px)
    canvas = Image.new("RGB", (plan.paper_width_px, plan.paper_height_px), "white")

    for row in range(plan.rows):
        for column in range(plan.columns):
            x = plan.start_x + column * (plan.placed_width_px + spacing_px)
            y = plan.start_y + row * (plan.placed_height_px + spacing_px)
            canvas.paste(photo, (x, y))

    output_path = _unique_output_path(output_dir, image_path.stem)
    canvas.save(output_path, quality=OUTPUT_QUALITY, subsampling=0, dpi=(dpi, dpi))
    return output_path, plan


def calculate_best_layout(photo_width: int, photo_height: int, paper: PaperPreset, dpi: int, spacing_px: int) -> LayoutPlan:
    candidates = (
        _calculate_layout(photo_width, photo_height, paper.width_mm, paper.height_mm, dpi, spacing_px, "竖版"),
        _calculate_layout(photo_width, photo_height, paper.height_mm, paper.width_mm, dpi, spacing_px, "横版"),
    )
    best = max(candidates, key=lambda item: (item.count, item.paper_width_px * item.paper_height_px))
    if best.count <= 0:
        raise LayoutValidationError("所选证件照规格无法放入当前纸张尺寸，请调整纸张或证件照规格。")
    return best


def validate_layout_inputs(images: list[Path], expected_size: tuple[int, int], dpi: int) -> None:
    mismatched: list[str] = []
    dpi_updates: list[Path] = []
    for image_path in images:
        try:
            with Image.open(image_path) as image:
                size = image.size
                source_dpi = _read_dpi(image)
        except Exception as exc:
            mismatched.append(f"{image_path.name}: 无法读取图片（{exc}）")
            continue

        if size != expected_size:
            mismatched.append(f"{image_path.name}: {size[0]}x{size[1]} px")
            continue

        if source_dpi != dpi:
            dpi_updates.append(image_path)

    if mismatched:
        expected = f"期望尺寸：{expected_size[0]}x{expected_size[1]} px"
        details = "\n".join(mismatched[:20])
        remaining = len(mismatched) - 20
        if remaining > 0:
            details += f"\n... 另有 {remaining} 张尺寸不一致"
        raise LayoutValidationError(f"输入图片尺寸与所选证件照规格不一致，请先使用证件照裁切处理。\n{expected}\n{details}")

    for image_path in dpi_updates:
        _rewrite_dpi(image_path, dpi)


def _calculate_layout(
    photo_width: int,
    photo_height: int,
    paper_width_mm: float,
    paper_height_mm: float,
    dpi: int,
    spacing_px: int,
    orientation: str,
) -> LayoutPlan:
    paper_width_px = mm_to_pixels(paper_width_mm, dpi)
    paper_height_px = mm_to_pixels(paper_height_mm, dpi)
    columns = max(0, (paper_width_px + spacing_px) // (photo_width + spacing_px))
    rows = max(0, (paper_height_px + spacing_px) // (photo_height + spacing_px))
    used_width = columns * photo_width + max(0, columns - 1) * spacing_px
    used_height = rows * photo_height + max(0, rows - 1) * spacing_px
    return LayoutPlan(
        paper_width_px=paper_width_px,
        paper_height_px=paper_height_px,
        columns=columns,
        rows=rows,
        count=columns * rows,
        start_x=max(0, (paper_width_px - used_width) // 2),
        start_y=max(0, (paper_height_px - used_height) // 2),
        placed_width_px=photo_width,
        placed_height_px=photo_height,
        orientation=orientation,
    )


def _read_dpi(image: Image.Image) -> int | None:
    dpi_info = image.info.get("dpi")
    if not dpi_info or len(dpi_info) < 2:
        return None
    x_dpi, y_dpi = dpi_info[:2]
    if not x_dpi or not y_dpi:
        return None
    if abs(float(x_dpi) - float(y_dpi)) > 1:
        return None
    return int(round(float(x_dpi)))


def _rewrite_dpi(image_path: Path, dpi: int) -> None:
    suffix = image_path.suffix.lower()
    if suffix not in SUPPORTED_LAYOUT_SUFFIXES:
        return
    with Image.open(image_path) as opened:
        image = ImageOps.exif_transpose(opened)
        image.load()
        save_kwargs = {"dpi": (dpi, dpi)}
        if suffix in {".jpg", ".jpeg"}:
            image = image.convert("RGB")
            save_kwargs.update({"quality": OUTPUT_QUALITY, "subsampling": 0})
        image.save(image_path, **save_kwargs)


def _unique_output_path(output_dir: Path, stem: str) -> Path:
    path = output_dir / f"{stem}_layout.jpg"
    index = 2
    while path.exists():
        path = output_dir / f"{stem}_layout_{index}.jpg"
        index += 1
    return path
