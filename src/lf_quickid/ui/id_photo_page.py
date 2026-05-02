from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Qt, Signal, Slot
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QDoubleSpinBox,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from lf_quickid.core.face_detector import FaceAnalyzerUnavailable, InsightFaceAnalyzer
from lf_quickid.core.id_photo_cropper import CropPreset, STANDARD_PRESETS, collect_input_images, crop_one_id_photo, mm_to_pixels


class CropWorkerSignals(QObject):
    progress = Signal(int, int, str)
    finished = Signal(int, int, str)
    failed = Signal(str)
    log = Signal(str)


class IdPhotoCropWorker(QRunnable):
    def __init__(self, input_path: Path, output_dir: Path, preset: CropPreset) -> None:
        super().__init__()
        self.input_path = input_path
        self.output_dir = output_dir
        self.preset = preset
        self.signals = CropWorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            images = collect_input_images(self.input_path)
            if not images:
                self.signals.finished.emit(0, 0, str(self.output_dir))
                return

            self.output_dir.mkdir(parents=True, exist_ok=True)
            self.signals.log.emit(f"找到 {len(images)} 张图片，正在加载本地人脸模型...")
            analyzer = InsightFaceAnalyzer()
            total = len(images)
            success_count = 0
            failed_count = 0

            for index, image_path in enumerate(images, start=1):
                self.signals.progress.emit(index, total, image_path.name)
                try:
                    output_path = crop_one_id_photo(image_path, self.output_dir, self.preset, analyzer)
                except Exception as exc:
                    failed_count += 1
                    self.signals.log.emit(f"失败 {image_path.name}: {exc}")
                    continue
                success_count += 1
                self.signals.log.emit(f"完成 {image_path.name} -> {output_path.name}")

            self.signals.finished.emit(success_count, failed_count, str(self.output_dir))
        except FaceAnalyzerUnavailable as exc:
            self.signals.failed.emit(str(exc))
        except Exception as exc:
            self.signals.failed.emit(f"处理失败: {exc}")


class IdPhotoPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._thread_pool = QThreadPool.globalInstance()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 26, 28, 26)
        layout.setSpacing(18)

        header = QLabel("证件照裁切")
        header.setObjectName("pageTitle")
        description = QLabel("选择图片或目录后，程序会在本机识别人脸位置，并按标准或自定义尺寸批量裁切。")
        description.setObjectName("pageDescription")

        input_row = QHBoxLayout()
        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText("请选择图片文件或照片目录")
        self.file_button = QPushButton("选择图片")
        self.folder_button = QPushButton("选择目录")
        input_row.addWidget(self.input_edit, 1)
        input_row.addWidget(self.file_button)
        input_row.addWidget(self.folder_button)

        output_row = QHBoxLayout()
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("默认输出到所选目录下的 idphoto_output")
        self.output_button = QPushButton("输出位置")
        output_row.addWidget(self.output_edit, 1)
        output_row.addWidget(self.output_button)

        settings_card = QFrame()
        settings_card.setObjectName("settingsCard")
        settings_layout = QVBoxLayout(settings_card)
        settings_layout.setContentsMargins(16, 14, 16, 16)
        settings_layout.setSpacing(10)

        settings_title = QLabel("裁切参数")
        settings_title.setObjectName("sectionTitle")
        settings_layout.addWidget(settings_title)

        self.preset_combo = QComboBox()
        for preset in STANDARD_PRESETS:
            self.preset_combo.addItem(_preset_label(preset), preset)
        self.preset_combo.addItem("自定义尺寸", None)
        self.preset_combo.setMinimumHeight(36)

        self.width_mm_spin = QDoubleSpinBox()
        self.width_mm_spin.setRange(5, 300)
        self.width_mm_spin.setDecimals(1)
        self.width_mm_spin.setSuffix(" mm")
        self.width_mm_spin.setMinimumHeight(36)
        self.width_mm_spin.setMinimumWidth(120)
        self.height_mm_spin = QDoubleSpinBox()
        self.height_mm_spin.setRange(5, 300)
        self.height_mm_spin.setDecimals(1)
        self.height_mm_spin.setSuffix(" mm")
        self.height_mm_spin.setMinimumHeight(36)
        self.height_mm_spin.setMinimumWidth(120)
        self.dpi_spin = QSpinBox()
        self.dpi_spin.setRange(72, 1200)
        self.dpi_spin.setValue(300)
        self.dpi_spin.setSuffix(" DPI")
        self.dpi_spin.setMinimumHeight(36)
        self.dpi_spin.setMinimumWidth(118)
        self.pixel_label = QLabel()
        self.pixel_label.setObjectName("pixelPreview")
        self.head_ratio_spin = QSpinBox()
        self.head_ratio_spin.setRange(35, 80)
        self.head_ratio_spin.setSuffix("%")
        self.head_ratio_spin.setMinimumHeight(36)
        self.head_ratio_spin.setMinimumWidth(118)
        self.quality_spin = QSpinBox()
        self.quality_spin.setRange(1, 10)
        self.quality_spin.setValue(8)
        self.quality_spin.setMinimumHeight(36)
        self.quality_spin.setMinimumWidth(96)

        preset_group = QFrame()
        preset_group.setObjectName("settingGroup")
        preset_layout = QVBoxLayout(preset_group)
        preset_layout.setContentsMargins(12, 9, 12, 12)
        preset_layout.setSpacing(6)
        preset_layout.addWidget(_field_label("证件照规格"))
        preset_layout.addWidget(self.preset_combo)

        size_group = QFrame()
        size_group.setObjectName("settingGroup")
        size_layout = QVBoxLayout(size_group)
        size_layout.setContentsMargins(12, 9, 12, 12)
        size_layout.setSpacing(7)
        size_layout.addWidget(_field_label("输出尺寸"))

        mm_size_row = QHBoxLayout()
        mm_size_row.setSpacing(8)
        mm_size_row.addWidget(self.width_mm_spin)
        multiply_label = QLabel("x")
        multiply_label.setObjectName("fieldHint")
        multiply_label.setAlignment(Qt.AlignCenter)
        mm_size_row.addWidget(multiply_label)
        mm_size_row.addWidget(self.height_mm_spin)
        mm_size_row.addStretch()
        size_layout.addLayout(mm_size_row)

        size_dpi_row = QHBoxLayout()
        size_dpi_row.setSpacing(10)

        dpi_group = QFrame()
        dpi_group.setObjectName("settingGroup")
        dpi_layout = QVBoxLayout(dpi_group)
        dpi_layout.setContentsMargins(12, 9, 12, 12)
        dpi_layout.setSpacing(7)
        dpi_layout.addWidget(_field_label("输出 DPI"))
        dpi_row = QHBoxLayout()
        dpi_row.setSpacing(8)
        dpi_row.addWidget(self.dpi_spin)
        dpi_row.addWidget(self.pixel_label, 1)
        dpi_layout.addLayout(dpi_row)

        quick_dpi_row = QHBoxLayout()
        quick_dpi_row.setSpacing(8)
        for dpi in (300, 350, 600):
            button = QPushButton(f"{dpi} DPI")
            button.setObjectName("secondaryButton")
            button.setMinimumHeight(32)
            button.clicked.connect(lambda checked=False, value=dpi: self.dpi_spin.setValue(value))
            quick_dpi_row.addWidget(button)
        dpi_layout.addLayout(quick_dpi_row)

        quality_group = QFrame()
        quality_group.setObjectName("settingGroup")
        quality_layout = QVBoxLayout(quality_group)
        quality_layout.setContentsMargins(12, 9, 12, 12)
        quality_layout.setSpacing(7)
        quality_layout.addWidget(_field_label("输出质量"))
        quality_row = QHBoxLayout()
        quality_row.setSpacing(8)
        quality_row.addWidget(self.quality_spin)
        quality_hint = QLabel("1 最小文件，10 最高画质，默认 8")
        quality_hint.setObjectName("fieldHint")
        quality_row.addWidget(quality_hint, 1)
        quality_layout.addLayout(quality_row)

        size_dpi_row.addWidget(size_group, 1)
        size_dpi_row.addWidget(dpi_group, 1)

        quality_composition_row = QHBoxLayout()
        quality_composition_row.setSpacing(10)

        composition_group = QFrame()
        composition_group.setObjectName("settingGroup")
        composition_layout = QVBoxLayout(composition_group)
        composition_layout.setContentsMargins(12, 9, 12, 12)
        composition_layout.setSpacing(7)
        composition_layout.addWidget(_field_label("构图控制"))
        ratio_row = QHBoxLayout()
        ratio_row.setSpacing(8)
        ratio_row.addWidget(self.head_ratio_spin)
        ratio_hint = QLabel("头部约占画面宽度，默认适合常见证件照")
        ratio_hint.setObjectName("fieldHint")
        ratio_row.addWidget(ratio_hint, 1)
        composition_layout.addLayout(ratio_row)

        quality_composition_row.addWidget(quality_group, 1)
        quality_composition_row.addWidget(composition_group, 1)

        settings_layout.addWidget(preset_group)
        settings_layout.addLayout(size_dpi_row)
        settings_layout.addLayout(quality_composition_row)

        action_row = QHBoxLayout()
        self.start_button = QPushButton("开始裁切")
        self.start_button.setEnabled(False)
        self.start_button.setMinimumHeight(40)
        self.start_button.setMinimumWidth(136)
        action_row.addStretch()
        action_row.addWidget(self.start_button)

        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.status = QLabel("等待选择图片或目录")
        self.status.setObjectName("statusText")
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setPlaceholderText("处理日志")

        layout.addWidget(header)
        layout.addWidget(description)
        layout.addLayout(input_row)
        layout.addLayout(output_row)
        layout.addWidget(settings_card)
        layout.addLayout(action_row)
        layout.addWidget(self.progress)
        layout.addWidget(self.status)
        layout.addWidget(self.log, 1)

        self.file_button.clicked.connect(self._choose_file)
        self.folder_button.clicked.connect(self._choose_folder)
        self.output_button.clicked.connect(self._choose_output)
        self.start_button.clicked.connect(self._start)
        self.input_edit.textChanged.connect(self._update_start_state)
        self.preset_combo.currentIndexChanged.connect(self._apply_preset)
        self.width_mm_spin.valueChanged.connect(self._update_pixel_preview)
        self.height_mm_spin.valueChanged.connect(self._update_pixel_preview)
        self.dpi_spin.valueChanged.connect(self._update_pixel_preview)
        self._apply_preset()
        self.setStyleSheet(_stylesheet())

    def _choose_file(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(self, "选择图片", "", "Images (*.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff)")
        if file_path:
            self.input_edit.setText(file_path)
            self._set_default_output(Path(file_path))

    def _choose_folder(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "选择照片目录")
        if directory:
            self.input_edit.setText(directory)
            self._set_default_output(Path(directory))

    def _choose_output(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if directory:
            self.output_edit.setText(directory)

    def _set_default_output(self, input_path: Path) -> None:
        if self.output_edit.text().strip():
            return
        base = input_path if input_path.is_dir() else input_path.parent
        self.output_edit.setText(str(base / "idphoto_output"))

    def _apply_preset(self) -> None:
        preset = self.preset_combo.currentData()
        custom = preset is None
        if preset is not None:
            self.width_mm_spin.setValue(preset.width_mm or 25)
            self.height_mm_spin.setValue(preset.height_mm or 35)
            self.head_ratio_spin.setValue(int(round(preset.head_ratio * 100)))
        self.width_mm_spin.setEnabled(custom)
        self.height_mm_spin.setEnabled(custom)
        self._update_pixel_preview()

    def _update_pixel_preview(self) -> None:
        width, height = self._calculated_pixels()
        self.pixel_label.setText(f"自动计算：{width} x {height} px")

    def _update_start_state(self) -> None:
        self.start_button.setEnabled(bool(self.input_edit.text().strip()))

    def _start(self) -> None:
        input_path = Path(self.input_edit.text()).expanduser()
        if not input_path.exists():
            QMessageBox.warning(self, "路径无效", "请选择有效的图片文件或照片目录。")
            return

        output_text = self.output_edit.text().strip()
        output_dir = Path(output_text).expanduser() if output_text else self._default_output_for(input_path)
        width, height = self._calculated_pixels()
        preset = CropPreset(
            "自定义",
            width,
            height,
            self.head_ratio_spin.value() / 100,
            0.43,
            self.width_mm_spin.value(),
            self.height_mm_spin.value(),
            self.dpi_spin.value(),
            self.quality_spin.value(),
        )

        self.log.clear()
        self.progress.setValue(0)
        self.status.setText("准备裁切...")
        self._set_controls_enabled(False)

        worker = IdPhotoCropWorker(input_path, output_dir, preset)
        worker.signals.progress.connect(self._on_progress)
        worker.signals.log.connect(self._append_log)
        worker.signals.finished.connect(self._on_finished)
        worker.signals.failed.connect(self._on_failed)
        self._thread_pool.start(worker)

    def _default_output_for(self, input_path: Path) -> Path:
        base = input_path if input_path.is_dir() else input_path.parent
        return base / "idphoto_output"

    def _calculated_pixels(self) -> tuple[int, int]:
        dpi = self.dpi_spin.value()
        return mm_to_pixels(self.width_mm_spin.value(), dpi), mm_to_pixels(self.height_mm_spin.value(), dpi)

    def _set_controls_enabled(self, enabled: bool) -> None:
        self.file_button.setEnabled(enabled)
        self.folder_button.setEnabled(enabled)
        self.output_button.setEnabled(enabled)
        self.start_button.setEnabled(enabled and bool(self.input_edit.text().strip()))

    def _on_progress(self, index: int, total: int, filename: str) -> None:
        self.progress.setMaximum(total)
        self.progress.setValue(index)
        self.status.setText(f"正在裁切 {index}/{total}: {filename}")

    def _append_log(self, message: str) -> None:
        self.log.append(message)

    def _on_finished(self, success_count: int, failed_count: int, output_dir: str) -> None:
        self._set_controls_enabled(True)
        self.status.setText(f"完成：成功 {success_count} 张，失败 {failed_count} 张。输出目录：{output_dir}")

    def _on_failed(self, message: str) -> None:
        self._set_controls_enabled(True)
        self.status.setText("处理失败")
        self._append_log(message)
        QMessageBox.critical(self, "处理失败", message)


def _stylesheet() -> str:
    return """
        #pageTitle {
            font-size: 28px;
            font-weight: 800;
            color: #101828;
        }
        #pageDescription, #statusText {
            color: #667085;
        }
        #settingsCard {
            background: #ffffff;
            border: 1px solid #e4e7ec;
            border-radius: 16px;
        }
        #sectionTitle {
            font-size: 17px;
            font-weight: 800;
            color: #101828;
        }
        #settingGroup {
            background: #f8fafc;
            border: 1px solid #edf2f7;
            border-radius: 14px;
        }
        QComboBox, QSpinBox, QDoubleSpinBox {
            background: #ffffff;
            border: 1px solid #d0d5dd;
            border-radius: 10px;
            padding: 4px 9px;
            font-size: 14px;
        }
        QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {
            background: #f2f4f7;
            color: #667085;
        }
        #fieldLabel {
            color: #344054;
            font-weight: 700;
            font-size: 13px;
        }
        #fieldHint {
            color: #667085;
            font-size: 13px;
        }
        #pixelPreview {
            color: #2563eb;
            font-weight: 700;
            background: #eff6ff;
            border-radius: 10px;
            padding: 7px 10px;
        }
        #secondaryButton {
            background: #eef4ff;
            color: #2563eb;
            padding: 6px 11px;
        }
        #secondaryButton:hover {
            background: #dbeafe;
        }
    """


def _preset_label(preset: CropPreset) -> str:
    if preset.width_mm is None or preset.height_mm is None:
        return f"{preset.name} - {preset.width}x{preset.height}px"
    return f"{preset.name} - {preset.width_mm:g}x{preset.height_mm:g} mm"


def _field_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("fieldLabel")
    return label
