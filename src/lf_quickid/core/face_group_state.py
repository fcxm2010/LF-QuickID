from __future__ import annotations

from pathlib import Path

from lf_quickid.core.models import FaceGroup, FaceRecord


def remove_face_from_group(groups: list[FaceGroup], group: FaceGroup, face: FaceRecord) -> list[FaceGroup]:
    group.faces = [item for item in group.faces if not _same_face(item, face)]
    return _non_empty_groups(groups)


def remove_image_from_groups(groups: list[FaceGroup], image_path: Path) -> list[FaceGroup]:
    for group in groups:
        group.faces = [face for face in group.faces if face.image_path != image_path]
    return _non_empty_groups(groups)


def _non_empty_groups(groups: list[FaceGroup]) -> list[FaceGroup]:
    return [group for group in groups if group.faces]


def _same_face(left: FaceRecord, right: FaceRecord) -> bool:
    return left is right or (left.image_path == right.image_path and left.bbox == right.bbox)
