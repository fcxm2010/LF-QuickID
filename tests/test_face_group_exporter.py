from __future__ import annotations

from pathlib import Path

import numpy as np

from lf_quickid.core.face_group_exporter import export_face_groups, safe_folder_name, unique_folder_name
from lf_quickid.core.models import FaceGroup, FaceRecord


def test_safe_folder_name_removes_invalid_characters() -> None:
    assert safe_folder_name('张/三:*?"<>|', "人物 1") == "张 三"
    assert safe_folder_name("   ", "人物 1") == "人物 1"


def test_unique_folder_name_appends_suffix() -> None:
    used = {"张三"}
    assert unique_folder_name("张三", used) == "张三-2"
    assert unique_folder_name("张三", used) == "张三-3"


def test_export_groups_copies_unique_images_and_duplicate_group_names(tmp_path: Path) -> None:
    source_a = tmp_path / "a.jpg"
    source_b = tmp_path / "b.jpg"
    source_a.write_bytes(b"a")
    source_b.write_bytes(b"b")
    output = tmp_path / "export"
    groups = [
        FaceGroup("张三", [_face(source_a), _face(source_a)]),
        FaceGroup("张三", [_face(source_b), _face(source_a)]),
    ]

    summary = export_face_groups(groups, output)

    assert summary.group_count == 2
    assert summary.copied_count == 3
    assert summary.failed_count == 0
    assert (output / "张三" / "a.jpg").read_bytes() == b"a"
    assert (output / "张三-2" / "b.jpg").read_bytes() == b"b"
    assert (output / "张三-2" / "a.jpg").read_bytes() == b"a"


def test_export_groups_renames_duplicate_file_names_inside_group(tmp_path: Path) -> None:
    source_dir_a = tmp_path / "a"
    source_dir_b = tmp_path / "b"
    source_dir_a.mkdir()
    source_dir_b.mkdir()
    first = source_dir_a / "same.jpg"
    second = source_dir_b / "same.jpg"
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    output = tmp_path / "export"

    summary = export_face_groups([FaceGroup("", [_face(first), _face(second)])], output)

    assert summary.copied_count == 2
    assert (output / "人物 1" / "same.jpg").read_bytes() == b"first"
    assert (output / "人物 1" / "same_2.jpg").read_bytes() == b"second"


def _face(path: Path) -> FaceRecord:
    return FaceRecord(image_path=path, bbox=(0, 0, 10, 10), embedding=np.ones(4))
