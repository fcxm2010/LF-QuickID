from __future__ import annotations

import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from lf_quickid.core.models import FaceGroup


ProgressCallback = Callable[[int, int, Path], None]


@dataclass(frozen=True)
class ExportFailure:
    source: Path
    message: str


@dataclass
class ExportSummary:
    output_dir: Path
    group_count: int = 0
    copied_count: int = 0
    failures: list[ExportFailure] = field(default_factory=list)

    @property
    def failed_count(self) -> int:
        return len(self.failures)


def export_face_groups(groups: list[FaceGroup], output_dir: Path, progress: ProgressCallback | None = None) -> ExportSummary:
    output_dir.mkdir(parents=True, exist_ok=True)
    exportable_groups = [group for group in groups if group.faces]
    total = sum(len(_unique_group_image_paths(group)) for group in exportable_groups)
    summary = ExportSummary(output_dir=output_dir, group_count=len(exportable_groups))
    used_folder_names: set[str] = set()
    copied_index = 0

    for group_index, group in enumerate(exportable_groups, start=1):
        folder_name = unique_folder_name(safe_folder_name(group.label, f"人物 {group_index}"), used_folder_names)
        group_dir = output_dir / folder_name
        group_dir.mkdir(parents=True, exist_ok=True)
        used_file_names: set[str] = set()

        for source in _unique_group_image_paths(group):
            copied_index += 1
            if progress is not None:
                progress(copied_index, total, source)
            target = group_dir / unique_file_name(source.name, used_file_names)
            try:
                shutil.copy2(source, target)
            except Exception as exc:
                summary.failures.append(ExportFailure(source=source, message=str(exc)))
                continue
            summary.copied_count += 1

    return summary


def safe_folder_name(label: str, fallback: str) -> str:
    value = label.strip() or fallback
    value = re.sub(r'[\\/:*?"<>|]+', " ", value)
    value = re.sub(r"\s+", " ", value).strip(" .")
    return value or fallback


def unique_folder_name(base_name: str, used_names: set[str]) -> str:
    return _unique_name(base_name, "", used_names, separator="-")


def unique_file_name(file_name: str, used_names: set[str]) -> str:
    path = Path(file_name)
    return _unique_name(path.stem, path.suffix, used_names, separator="_")


def _unique_group_image_paths(group: FaceGroup) -> list[Path]:
    paths: list[Path] = []
    seen: set[Path] = set()
    for face in group.faces:
        if face.image_path in seen:
            continue
        paths.append(face.image_path)
        seen.add(face.image_path)
    return paths


def _unique_name(stem: str, suffix: str, used_names: set[str], separator: str) -> str:
    candidate = f"{stem}{suffix}"
    if candidate not in used_names:
        used_names.add(candidate)
        return candidate

    index = 2
    while True:
        candidate = f"{stem}{separator}{index}{suffix}"
        if candidate not in used_names:
            used_names.add(candidate)
            return candidate
        index += 1
