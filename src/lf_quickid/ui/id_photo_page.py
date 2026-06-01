from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Qt, Signal, Slot
from PySide6.QtGui import QPixmap
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

from lf_quickid.core.background_replacer import MattingUnavailable, PortraitMattingEngine
from lf_quickid.core.face_detector import FaceAnalyzerUnavailable, InsightFaceAnalyzer
from lf_quickid.core.id_photo_cropper import CropPreset, STANDARD_PRESETS, collect_input_images, crop_one_id_photo, mm_to_pixels
from lf_quickid.ui.theme import build_hero, field_label, section_title


class CropWorkerSignals(QObject):
    progress = Signal(int, int, str)
    preview = Signal(str)
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
            self.signals.log.emit(f"找到 {len(images)} 张图片，正在加载本地人脸模型和人像抠图模型...")
            analyzer = InsightFaceAnalyzer()
            matting_engine = PortraitMattingEngine()
            total = len(images)
            success_count = 0
            failed_count = 0

            for index, image_path in enumerate(images, start=1):
                self.signals.progress.emit(index, total, image_path.name)
                try:
                    output_path = crop_one_id_photo(
                        image_path,
                        self.output_dir,
                        self.preset,
                        analyzer,
                        matting_engine,
                    )
                except Exception as exc:
                    failed_count += 1
                    self.signals.log.emit(f"失败 {image_path.name}: {exc}")
                    continue
                success_count += 1
                self.signals.log.emit(f"完成 {image_path.name} -> {output_path.name}")
                self.signals.preview.emit(str(output_path))

            self.signals.finished.emit(success_count, failed_count, str(self.output_dir))
        except (FaceAnalyzerUnavailable, MattingUnavailable) as exc:
            self.signals.failed.emit(str(exc))
        except Exception as exc:
            self.signals.failed.emit(f"处理失败: {exc}")


class IdPhotoPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._thread_pool = QThreadPool.globalInstance()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 22, 26, 22)
        layout.setSpacing(12)

        hero = build_hero("证件照裁切", "选择图片或目录后，程序会在本机识别人脸位置，并按标准规格或自定义尺寸批量裁切、写入 DPI。")

        input_card = QFrame()
        input_card.setObjectName("inputCard")
        input_layout = QVBoxLayout(input_card)
        input_layout.setContentsMargins(14, 12, 14, 14)
        input_layout.setSpacing(8)
        input_layout.addWidget(section_title("选择输入与输出"))

        input_row = QHBoxLayout()
        input_row.setSpacing(10)
        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText("请选择图片文件或照片目录")
        self.file_button = QPushButton("选择图片")
        self.folder_button = QPushButton("选择目录")
        input_row.addWidget(self.input_edit, 1)
        input_row.addWidget(self.file_button)
        input_row.addWidget(self.folder_button)

        output_row = QHBoxLayout()
        output_row.setSpacing(10)
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("默认输出到所选目录下的 idphoto_output")
        self.output_button = QPushButton("输出位置")
        output_row.addWidget(self.output_edit, 1)
        output_row.addWidget(self.output_button)
        input_layout.addLayout(input_row)
        input_layout.addLayout(output_row)

        settings_card = QFrame()
        settings_card.setObjectName("settingsCard")
        settings_layout = QVBoxLayout(settings_card)
        settings_layout.setContentsMargins(14, 12, 14, 14)
        settings_layout.setSpacing(8)

        settings_layout.addWidget(section_title("裁切参数"))

        self.preset_combo = QComboBox()
        for preset in STANDARD_PRESETS:
            self.preset_combo.addItem(_preset_label(preset), preset)
        self.preset_combo.addItem("自定义尺寸", None)
        self.preset_combo.setMinimumHeight(30)

        self.width_mm_spin = QDoubleSpinBox()
        self.width_mm_spin.setRange(5, 300)
        self.width_mm_spin.setDecimals(1)
        self.width_mm_spin.setSuffix(" mm")
        self.width_mm_spin.setMinimumHeight(30)
        self.width_mm_spin.setMinimumWidth(120)
        self.height_mm_spin = QDoubleSpinBox()
        self.height_mm_spin.setRange(5, 300)
        self.height_mm_spin.setDecimals(1)
        self.height_mm_spin.setSuffix(" mm")
        self.height_mm_spin.setMinimumHeight(30)
        self.height_mm_spin.setMinimumWidth(120)
        self.dpi_spin = QSpinBox()
        self.dpi_spin.setRange(72, 1200)
        self.dpi_spin.setValue(300)
        self.dpi_spin.setSuffix(" DPI")
        self.dpi_spin.setMinimumHeight(30)
        self.dpi_spin.setMinimumWidth(118)
        self.pixel_label = QLabel()
        self.pixel_label.setObjectName("pixelPreview")
        self.head_ratio_spin = QSpinBox()
        self.head_ratio_spin.setRange(35, 80)
        self.head_ratio_spin.setSuffix("%")
        self.head_ratio_spin.setMinimumHeight(30)
        self.head_ratio_spin.setMinimumWidth(118)
        self.quality_spin = QSpinBox()
        self.quality_spin.setRange(1, 10)
        self.quality_spin.setValue(8)
        self.quality_spin.setMinimumHeight(30)
        self.quality_spin.setMinimumWidth(96)

        preset_group = QFrame()
        preset_group.setObjectName("settingGroup")
        preset_layout = QVBoxLayout(preset_group)
        preset_layout.setContentsMargins(10, 8, 10, 10)
        preset_layout.setSpacing(5)
        preset_layout.addWidget(field_label("证件照规格"))
        preset_layout.addWidget(self.preset_combo)

        size_group = QFrame()
        size_group.setObjectName("settingGroup")
        size_layout = QVBoxLayout(size_group)
        size_layout.setContentsMargins(10, 8, 10, 10)
        size_layout.setSpacing(5)
        size_layout.addWidget(field_label("输出尺寸"))

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

        preset_size_row = QHBoxLayout()
        preset_size_row.setSpacing(10)

        dpi_group = QFrame()
        dpi_group.setObjectName("settingGroup")
        dpi_layout = QVBoxLayout(dpi_group)
        dpi_layout.setContentsMargins(10, 8, 10, 10)
        dpi_layout.setSpacing(5)
        dpi_layout.addWidget(field_label("输出 DPI"))
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
            button.setMinimumHeight(30)
            button.clicked.connect(lambda checked=False, value=dpi: self.dpi_spin.setValue(value))
            quick_dpi_row.addWidget(button)
        dpi_layout.addLayout(quick_dpi_row)

        quality_group = QFrame()
        quality_group.setObjectName("settingGroup")
        quality_layout = QVBoxLayout(quality_group)
        quality_layout.setContentsMargins(10, 8, 10, 10)
        quality_layout.setSpacing(5)
        quality_layout.addWidget(field_label("输出质量"))
        quality_hint = QLabel("1-10")
        quality_hint.setObjectName("fieldHint")
        quality_layout.addWidget(quality_hint)
        quality_row = QHBoxLayout()
        quality_row.setSpacing(8)
        quality_row.addWidget(self.quality_spin)
        quality_row.addStretch()
        quality_layout.addLayout(quality_row)

        preset_size_row.addWidget(preset_group, 1)
        preset_size_row.addWidget(size_group, 1)

        dpi_quality_composition_row = QHBoxLayout()
        dpi_quality_composition_row.setSpacing(10)

        composition_group = QFrame()
        composition_group.setObjectName("settingGroup")
        composition_layout = QVBoxLayout(composition_group)
        composition_layout.setContentsMargins(10, 8, 10, 10)
        composition_layout.setSpacing(5)
        composition_layout.addWidget(field_label("构图控制"))
        ratio_hint = QLabel("头部占画面宽度")
        ratio_hint.setObjectName("fieldHint")
        composition_layout.addWidget(ratio_hint)
        ratio_row = QHBoxLayout()
        ratio_row.setSpacing(8)
        ratio_row.addWidget(self.head_ratio_spin)
        ratio_row.addStretch()
        composition_layout.addLayout(ratio_row)

        dpi_quality_composition_row.addWidget(dpi_group, 2)
        dpi_quality_composition_row.addWidget(quality_group, 1)
        dpi_quality_composition_row.addWidget(composition_group, 1)

        settings_layout.addLayout(preset_size_row)
        settings_layout.addLayout(dpi_quality_composition_row)

        self.start_button = QPushButton("开始裁切")
        self.start_button.setEnabled(False)
        self.start_button.setMinimumHeight(34)
        action_row = QHBoxLayout()
        action_row.addStretch()
        action_row.addWidget(self.start_button)
        settings_layout.addLayout(action_row)

        left_panel = QFrame()
        left_panel.setObjectName("toolPanel")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(14)
        left_layout.addWidget(input_card)
        left_layout.addWidget(settings_card)
        left_layout.addStretch()

        preview_card = QFrame()
        preview_card.setObjectName("previewCard")
        preview_layout = QVBoxLayout(preview_card)
        preview_layout.setContentsMargins(16, 14, 16, 16)
        preview_layout.setSpacing(12)
        preview_layout.addWidget(section_title("输出预览"))

        preview_stage = QFrame()
        preview_stage.setObjectName("previewStage")
        preview_stage_layout = QVBoxLayout(preview_stage)
        preview_stage_layout.setContentsMargins(18, 22, 18, 22)
        preview_stage_layout.setSpacing(10)

        photo_placeholder = QFrame()
        photo_placeholder.setObjectName("photoPlaceholder")
        photo_placeholder.setFixedSize(142, 198)
        photo_layout = QVBoxLayout(photo_placeholder)
        photo_layout.setContentsMargins(16, 16, 16, 16)
        photo_layout.setSpacing(8)
        self.preview_image = QLabel("选择图片后显示预览")
        self.preview_image.setObjectName("previewImage")
        self.preview_image.setAlignment(Qt.AlignCenter)
        self.preview_image.setWordWrap(True)
        bust = QLabel("证件照裁切预览")
        bust.setObjectName("previewCaption")
        bust.setAlignment(Qt.AlignCenter)
        bust.setWordWrap(True)
        photo_layout.addWidget(self.preview_image, 1)
        photo_layout.addWidget(bust)
        preview_stage_layout.addWidget(photo_placeholder, 0, Qt.AlignHCenter)

        self.summary_title = QLabel("当前规格")
        self.summary_title.setObjectName("summaryTitle")
        self.summary_size = QLabel()
        self.summary_size.setObjectName("summaryLine")
        self.summary_pixels = QLabel()
        self.summary_pixels.setObjectName("summaryLine")
        self.summary_quality = QLabel()
        self.summary_quality.setObjectName("summaryLine")

        summary_card = QFrame()
        summary_card.setObjectName("summaryCard")
        summary_layout = QVBoxLayout(summary_card)
        summary_layout.setContentsMargins(14, 12, 14, 12)
        summary_layout.setSpacing(6)
        summary_layout.addWidget(self.summary_title)
        summary_layout.addWidget(self.summary_size)
        summary_layout.addWidget(self.summary_pixels)
        summary_layout.addWidget(self.summary_quality)

        preview_layout.addWidget(preview_stage)
        preview_layout.addWidget(summary_card)
        preview_layout.addStretch()

        workbench = QHBoxLayout()
        workbench.setSpacing(14)
        workbench.addWidget(left_panel, 3)
        workbench.addWidget(preview_card, 2)

        progress_card = QFrame()
        progress_card.setObjectName("progressCard")
        progress_layout = QVBoxLayout(progress_card)
        progress_layout.setContentsMargins(14, 12, 14, 14)
        progress_layout.setSpacing(8)
        progress_layout.addWidget(section_title("处理进度"))

        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.status = QLabel("等待选择图片或目录")
        self.status.setObjectName("statusText")
        progress_layout.addWidget(self.progress)
        progress_layout.addWidget(self.status)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setFixedHeight(105)
        self.log.setPlaceholderText("处理日志")

        layout.addWidget(hero)
        layout.addLayout(workbench, 1)
        layout.addWidget(progress_card)
        layout.addWidget(field_label("处理详情"))
        layout.addWidget(self.log)

        self.file_button.clicked.connect(self._choose_file)
        self.folder_button.clicked.connect(self._choose_folder)
        self.output_button.clicked.connect(self._choose_output)
        self.start_button.clicked.connect(self._start)
        self.input_edit.textChanged.connect(self._update_start_state)
        self.preset_combo.currentIndexChanged.connect(self._apply_preset)
        self.width_mm_spin.valueChanged.connect(self._update_pixel_preview)
        self.height_mm_spin.valueChanged.connect(self._update_pixel_preview)
        self.dpi_spin.valueChanged.connect(self._update_pixel_preview)
        self.quality_spin.valueChanged.connect(self._update_summary)
        self.head_ratio_spin.valueChanged.connect(self._update_summary)
        self._apply_preset()
        self.setStyleSheet(_stylesheet())

    def _choose_file(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(self, "选择图片", "", "Images (*.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff)")
        if file_path:
            self.input_edit.setText(file_path)
            self._set_default_output(Path(file_path))
            self._update_input_preview(Path(file_path))

    def _choose_folder(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "选择照片目录")
        if directory:
            self.input_edit.setText(directory)
            self._set_default_output(Path(directory))
            self._update_input_preview(Path(directory))

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
        self._update_summary()

    def _update_summary(self) -> None:
        if not hasattr(self, "summary_title"):
            return
        preset = self.preset_combo.currentData()
        preset_name = preset.name if preset is not None else "自定义尺寸"
        width, height = self._calculated_pixels()
        self.summary_title.setText(preset_name)
        self.summary_size.setText(f"{self.width_mm_spin.value():g} x {self.height_mm_spin.value():g} mm")
        self.summary_pixels.setText(f"{width} x {height} px · {self.dpi_spin.value()} DPI")
        self.summary_quality.setText(f"质量 {self.quality_spin.value()} · 头部宽度 {self.head_ratio_spin.value()}%")

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
        worker.signals.preview.connect(lambda path: self._set_preview_image(Path(path), "已生成输出预览"))
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

    def _update_input_preview(self, input_path: Path) -> None:
        try:
            images = collect_input_images(input_path)
        except Exception:
            self._clear_preview("无法预览所选路径")
            return
        if not images:
            self._clear_preview("未找到可预览图片")
            return
        self._set_preview_image(images[0], "输入图片预览")

    def _set_preview_image(self, image_path: Path, caption: str) -> None:
        pixmap = QPixmap(str(image_path))
        if pixmap.isNull():
            self._clear_preview("无法读取预览图片")
            return
        scaled = pixmap.scaled(self.preview_image.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.preview_image.setPixmap(scaled)
        self.preview_image.setText("")
        self.status.setText(caption)

    def _clear_preview(self, text: str) -> None:
        self.preview_image.clear()
        self.preview_image.setText(text)

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
        #toolPanel {
            background: transparent;
            border: none;
        }
        #previewCard {
            background: #ffffff;
            border: 1px solid #dcdcde;
            border-radius: 12px;
        }
        #progressCard {
            background: #ffffff;
            border: 1px solid #dcdcde;
            border-radius: 12px;
        }
        #previewStage {
            background: #f2f2f7;
            border: 1px solid #e5e5ea;
            border-radius: 10px;
        }
        #photoPlaceholder {
            background: #ffffff;
            border: 1px solid #c7c7cc;
            border-radius: 8px;
        }
        #previewAvatar {
            background: #f2f2f7;
            border: 1px solid #d1d1d6;
            border-radius: 36px;
            color: #6e6e73;
            font-weight: 650;
        }
        #previewImage {
            background: transparent;
            color: #8e8e93;
            font-size: 12px;
            border: none;
        }
        #previewCaption {
            background: transparent;
            color: #8e8e93;
            font-size: 12px;
        }
        #summaryCard {
            background: #f9f9fb;
            border: 1px solid #e5e5ea;
            border-radius: 10px;
        }
        #summaryTitle {
            background: transparent;
            color: #1d1d1f;
            font-size: 16px;
            font-weight: 800;
        }
        #summaryLine {
            background: transparent;
            color: #6e6e73;
            font-size: 13px;
        }
        #previewCard QPushButton {
            font-size: 14px;
        }
        QComboBox, QSpinBox, QDoubleSpinBox {
            min-height: 28px;
        }
        #pixelPreview {
            color: #0057d9;
            font-weight: 700;
            background: #f2f7ff;
            border: 1px solid #d7e8ff;
            border-radius: 7px;
            padding: 5px 8px;
        }
        #secondaryButton {
            padding: 6px 11px;
        }
    """


def _preset_label(preset: CropPreset) -> str:
    if preset.width_mm is None or preset.height_mm is None:
        return f"{preset.name} - {preset.width}x{preset.height}px"
    return f"{preset.name} - {preset.width_mm:g}x{preset.height_mm:g} mm"
