from __future__ import annotations

import numpy as np

from lf_quickid.core.face_detector import DetectedFace, InsightFaceAnalyzer
from lf_quickid.core.id_photo_cropper import (
    MIN_TOP_MARGIN_MM,
    NORMAL_TOP_MARGIN_MM,
    CropPreset,
    _calculate_crop_box,
    mm_to_pixels,
)


def test_detect_face_details_keeps_eye_keypoints_and_bbox_compatibility() -> None:
    class RawFace:
        bbox = np.array([10.2, 20.2, 40.6, 80.8], dtype=np.float32)
        kps = np.array(
            [
                [15.5, 30.5],
                [35.5, 31.5],
                [25.0, 45.0],
                [18.0, 65.0],
                [32.0, 65.0],
            ],
            dtype=np.float32,
        )

    class App:
        def get(self, image_bgr: np.ndarray) -> list[RawFace]:
            return [RawFace()]

    analyzer = InsightFaceAnalyzer.__new__(InsightFaceAnalyzer)
    analyzer._app = App()
    image = np.zeros((100, 80, 3), dtype=np.uint8)

    details = analyzer.detect_face_details(image)

    assert details == [DetectedFace(bbox=(10, 20, 41, 81), left_eye=(15.5, 30.5), right_eye=(35.5, 31.5))]
    assert analyzer.detect_faces(image) == [(10, 20, 41, 81)]


def test_crop_box_places_eyes_near_first_third_with_normal_top_margin() -> None:
    preset = _preset()
    subject_top = 150
    image = _test_image(subject_top=subject_top)
    face = DetectedFace(bbox=(400, 250, 600, 610), left_eye=(455, 380), right_eye=(545, 380))

    crop_box = _calculate_crop_box(image, face, preset)

    eye_y, top_margin = _output_measurements(crop_box, face, subject_top, preset)
    assert abs(eye_y - preset.height / 3) <= 3
    assert abs(top_margin - mm_to_pixels(NORMAL_TOP_MARGIN_MM, preset.dpi)) <= 3
    assert abs(_output_head_width(crop_box, preset) - preset.width * preset.head_ratio) <= 3


def test_crop_box_keeps_head_width_for_tall_hair_and_avoids_cutting_top() -> None:
    preset = _preset()
    subject_top = 60
    image = _test_image(subject_top=subject_top, height=1600)
    face = DetectedFace(bbox=(400, 250, 600, 610), left_eye=(455, 380), right_eye=(545, 380))

    crop_box = _calculate_crop_box(image, face, preset)

    eye_y, top_margin = _output_measurements(crop_box, face, subject_top, preset)
    assert eye_y > preset.height / 3
    assert top_margin >= mm_to_pixels(MIN_TOP_MARGIN_MM, preset.dpi) - 1
    assert crop_box[1] <= subject_top
    assert abs(_output_head_width(crop_box, preset) - preset.width * preset.head_ratio) <= 3


def test_crop_box_falls_back_to_face_center_without_eye_keypoints() -> None:
    preset = _preset()
    image = _test_image(subject_top=150)
    face = DetectedFace(bbox=(400, 250, 600, 610))

    crop_box = _calculate_crop_box(image, face, preset)

    assert crop_box[1] == 56


def _preset() -> CropPreset:
    return CropPreset("test", 344, 482, 0.58, 0.43, dpi=300)


def _test_image(subject_top: int, height: int = 1400, width: int = 1000) -> np.ndarray:
    image = np.full((height, width, 3), (218, 142, 66), dtype=np.uint8)
    image[subject_top:1050, 320:680] = (30, 30, 30)
    return image


def _output_measurements(
    crop_box: tuple[int, int, int, int],
    face: DetectedFace,
    subject_top: int,
    preset: CropPreset,
) -> tuple[float, float]:
    _, top, _, bottom = crop_box
    crop_height = bottom - top
    scale = preset.height / crop_height
    assert face.left_eye is not None
    assert face.right_eye is not None
    eye_y = ((face.left_eye[1] + face.right_eye[1]) / 2 - top) * scale
    top_margin = (subject_top - top) * scale
    return eye_y, top_margin


def _output_head_width(crop_box: tuple[int, int, int, int], preset: CropPreset) -> float:
    left, _, right, _ = crop_box
    crop_width = right - left
    return 360 * preset.width / crop_width
