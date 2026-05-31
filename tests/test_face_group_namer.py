from __future__ import annotations

from pathlib import Path

import numpy as np

from lf_quickid.core import face_group_namer
from lf_quickid.core.face_group_namer import best_name_from_paths, best_name_from_texts
from lf_quickid.core.models import FaceGroup, FaceRecord


def test_extracts_chinese_name_from_noisy_filename() -> None:
    assert best_name_from_paths([Path("微信图片_20260531_李小明_001.jpg")]) == "李小明"


def test_extracts_chinese_name_after_photo_noise() -> None:
    assert best_name_from_paths([Path("2026毕业照-张三-精修.jpg")]) == "张三"


def test_extracts_english_name_from_filename() -> None:
    assert best_name_from_paths([Path("John Smith_IMG_001.jpg")]) == "John Smith"


def test_returns_none_when_filename_has_no_name() -> None:
    assert best_name_from_paths([Path("IMG_20260531_001.jpg")]) is None


def test_extracts_name_from_ocr_text() -> None:
    assert best_name_from_texts(["姓名：王小明", "班级：二班"]) == "王小明"


def test_label_groups_uses_ocr_when_filename_has_no_name(monkeypatch) -> None:
    image_path = Path("IMG_0001.jpg")
    group = FaceGroup(label="人物 1", faces=[_face(image_path)])

    monkeypatch.setattr(face_group_namer, "recognize_text_lines", lambda path: ["姓名：王小明"])

    face_group_namer.label_face_groups([group])

    assert group.label == "王小明"
    assert group.label_source == "ocr"


def _face(path: Path) -> FaceRecord:
    return FaceRecord(image_path=path, bbox=(0, 0, 10, 10), embedding=np.ones(4))
