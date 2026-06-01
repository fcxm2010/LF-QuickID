from __future__ import annotations

import numpy as np
from PIL import Image

from lf_quickid.core.face_detector import DetectedFace, InsightFaceAnalyzer
from lf_quickid.core.id_photo_cropper import (
    MAX_HEAD_WIDTH_FROM_FACE,
    MIN_TOP_MARGIN_MM,
    NORMAL_TOP_MARGIN_MM,
    CropPreset,
    _calculate_crop_box,
    _hivision_crop_box,
    crop_one_id_photo,
    mm_to_pixels,
)


SUBJECT_WIDTH = 260


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
    face = DetectedFace(bbox=(400, 220, 600, 570), left_eye=(455, 305), right_eye=(545, 305))

    crop_box = _calculate_crop_box(image, face, preset)

    eye_y, top_margin = _output_measurements(crop_box, face, subject_top, preset)
    assert abs(eye_y - preset.height / 3) <= 8
    assert abs(top_margin - mm_to_pixels(NORMAL_TOP_MARGIN_MM, preset.dpi)) <= 3
    assert abs(_output_subject_width(crop_box, SUBJECT_WIDTH, preset) - preset.width * preset.head_ratio) <= 3


def test_crop_box_keeps_head_width_for_tall_hair_and_avoids_cutting_top() -> None:
    preset = _preset()
    subject_top = 60
    image = _test_image(subject_top=subject_top, height=1600)
    face = DetectedFace(bbox=(400, 220, 600, 570), left_eye=(455, 305), right_eye=(545, 305))

    crop_box = _calculate_crop_box(image, face, preset)

    eye_y, top_margin = _output_measurements(crop_box, face, subject_top, preset)
    assert eye_y > preset.height / 3
    assert top_margin >= mm_to_pixels(MIN_TOP_MARGIN_MM, preset.dpi) - 1
    assert crop_box[1] <= subject_top
    assert abs(_output_subject_width(crop_box, SUBJECT_WIDTH, preset) - preset.width * preset.head_ratio) <= 3


def test_crop_box_size_stays_stable_when_face_box_height_changes() -> None:
    preset = _preset()
    image = _test_image(subject_top=140, height=1800)
    normal_face = DetectedFace(bbox=(400, 220, 600, 570), left_eye=(455, 305), right_eye=(545, 305))
    tall_face = DetectedFace(bbox=(400, 220, 600, 990), left_eye=(455, 305), right_eye=(545, 305))

    normal_crop = _calculate_crop_box(image, normal_face, preset)
    tall_crop = _calculate_crop_box(image, tall_face, preset)

    assert _crop_width(normal_crop) == _crop_width(tall_crop)
    assert abs(_output_subject_width(tall_crop, SUBJECT_WIDTH, preset) - preset.width * preset.head_ratio) <= 3


def test_crop_box_caps_noisy_foreground_width() -> None:
    preset = _preset()
    image = _test_image(subject_top=140, width=1400)
    image[160:620, 200:1200] = (30, 30, 30)
    face = DetectedFace(bbox=(600, 220, 800, 570), left_eye=(655, 305), right_eye=(745, 305))

    crop_box = _calculate_crop_box(image, face, preset)

    assert _crop_width(crop_box) == round(200 * MAX_HEAD_WIDTH_FROM_FACE / preset.head_ratio)


def test_crop_box_falls_back_to_face_center_without_eye_keypoints() -> None:
    preset = _preset()
    image = _test_image(subject_top=150)
    face = DetectedFace(bbox=(400, 220, 600, 570))

    crop_box = _calculate_crop_box(image, face, preset)

    assert crop_box[1] == 125


def test_hivision_crop_uses_alpha_bounds_without_losing_head_width_control() -> None:
    preset = _preset()
    image = _test_image(subject_top=140, height=1400, width=1000)
    rgba = _rgba_with_alpha_subject(image, subject_top=140)
    face = DetectedFace(bbox=(400, 220, 600, 570), left_eye=(455, 305), right_eye=(545, 305))

    crop_width, crop_height, left, top = _hivision_crop_box(rgba, face, preset)

    output_subject_width = SUBJECT_WIDTH * preset.width / crop_width
    output_eye_y = (305 - top) * preset.height / crop_height
    output_top_margin = (140 - top) * preset.height / crop_height
    assert abs(output_subject_width - preset.width * preset.head_ratio) <= 3
    assert abs(output_eye_y - preset.height / 3) <= 8
    assert abs(output_top_margin - mm_to_pixels(NORMAL_TOP_MARGIN_MM, preset.dpi)) <= 4
    assert left <= 500 - SUBJECT_WIDTH // 2


def test_crop_one_id_photo_uses_hivision_path_with_fake_matting(tmp_path) -> None:
    preset = _preset()
    image = _test_image(subject_top=140, height=1400, width=1000)
    input_path = tmp_path / "input.jpg"
    Image.fromarray(image[:, :, ::-1]).save(input_path)
    output_dir = tmp_path / "out"
    face = DetectedFace(bbox=(400, 220, 600, 570), left_eye=(455, 305), right_eye=(545, 305))

    output_path = crop_one_id_photo(input_path, output_dir, preset, _FakeAnalyzer(face), _FakeMatting(subject_top=140))

    with Image.open(output_path) as saved:
        assert saved.size == (preset.width, preset.height)
        assert saved.info["dpi"][0] == preset.dpi


def test_crop_one_id_photo_hivision_path_handles_missing_keypoints(tmp_path) -> None:
    preset = _preset()
    image = _test_image(subject_top=140, height=1400, width=1000)
    input_path = tmp_path / "input.jpg"
    Image.fromarray(image[:, :, ::-1]).save(input_path)
    face = DetectedFace(bbox=(400, 220, 600, 570))

    output_path = crop_one_id_photo(input_path, tmp_path / "out", preset, _FakeAnalyzer(face), _FakeMatting(subject_top=140))

    assert output_path.exists()


def _preset() -> CropPreset:
    return CropPreset("test", 344, 482, 0.58, 0.43, dpi=300)


def _test_image(subject_top: int, height: int = 1400, width: int = 1000) -> np.ndarray:
    image = np.full((height, width, 3), (218, 142, 66), dtype=np.uint8)
    center_x = width // 2
    half_width = SUBJECT_WIDTH // 2
    image[subject_top:1050, center_x - half_width : center_x + half_width] = (30, 30, 30)
    return image


def _rgba_with_alpha_subject(image_bgr: np.ndarray, subject_top: int) -> np.ndarray:
    rgba = np.dstack((image_bgr, np.zeros(image_bgr.shape[:2], dtype=np.uint8)))
    center_x = image_bgr.shape[1] // 2
    half_width = SUBJECT_WIDTH // 2
    rgba[subject_top:1050, center_x - half_width : center_x + half_width, 3] = 255
    return rgba


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


def _output_subject_width(crop_box: tuple[int, int, int, int], subject_width: int, preset: CropPreset) -> float:
    left, _, right, _ = crop_box
    crop_width = right - left
    return subject_width * preset.width / crop_width


def _crop_width(crop_box: tuple[int, int, int, int]) -> int:
    return crop_box[2] - crop_box[0]


class _FakeAnalyzer:
    def __init__(self, face: DetectedFace) -> None:
        self.face = face

    def detect_face_details(self, image_bgr: np.ndarray) -> list[DetectedFace]:
        return [self.face]


class _FakeMatting:
    def __init__(self, subject_top: int) -> None:
        self.subject_top = subject_top

    def alpha_mask(self, image_bgr: np.ndarray) -> np.ndarray:
        return _rgba_with_alpha_subject(image_bgr, self.subject_top)[:, :, 3]
