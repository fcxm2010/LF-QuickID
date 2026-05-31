from __future__ import annotations

from pathlib import Path

import numpy as np

from lf_quickid.core.face_group_state import remove_face_from_group, remove_image_from_groups
from lf_quickid.core.models import FaceGroup, FaceRecord


def test_remove_face_only_affects_current_group_record() -> None:
    image_a = Path("a.jpg")
    image_b = Path("b.jpg")
    face_a = _face(image_a, (0, 0, 10, 10))
    face_a_other_group = _face(image_a, (20, 20, 30, 30))
    face_b = _face(image_b, (0, 0, 10, 10))
    group_a = FaceGroup("张三", [face_a, face_b])
    group_b = FaceGroup("李四", [face_a_other_group])

    groups = remove_face_from_group([group_a, group_b], group_a, face_a)

    assert groups[0] is group_a
    assert groups[1] is group_b
    assert group_a.faces[0] is face_b
    assert group_b.faces[0] is face_a_other_group


def test_remove_image_removes_it_from_all_groups_and_drops_empty_groups() -> None:
    image_a = Path("a.jpg")
    image_b = Path("b.jpg")
    face_a = _face(image_a, (0, 0, 10, 10))
    face_a_other_group = _face(image_a, (20, 20, 30, 30))
    face_b = _face(image_b, (0, 0, 10, 10))
    group_a = FaceGroup("张三", [face_a, face_b])
    group_b = FaceGroup("李四", [face_a_other_group])

    groups = remove_image_from_groups([group_a, group_b], image_a)

    assert len(groups) == 1
    assert groups[0] is group_a
    assert group_a.faces[0] is face_b
    assert group_b.faces == []


def _face(path: Path, bbox: tuple[int, int, int, int]) -> FaceRecord:
    return FaceRecord(image_path=path, bbox=bbox, embedding=np.ones(4))
