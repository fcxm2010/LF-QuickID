from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Qt, Signal, Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from lf_quickid.core.id_photo_cropper import CropPreset, STANDARD_PRESETS, collect_input_images, mm_to_pixels
from lf_quickid.core.id_photo_layout import (
    DEFAULT_SPACING_PX,
    PAPER_PRESETS,
    LayoutValidationError,
    PaperPreset,
    calculate_best_layout,
    layout_one_id_photo,
    validate_layout_inputs,
)
from lf_quickid.ui.theme import build_hero, field_label, section_title


class LayoutWorkerSignals(QObject):
    progress = Signal(int, int, str)
    finished = Signal(int, int, str)
    failed = Signal(str)
    log = Signal(str)


class IdPhotoLayoutWorker(QRunnable):
    def __init__(self, input_path: Path, output_dir: Path, photo_preset: CropPreset, paper: PaperPreset, dpi: int, add_border: bool) -> None:
        super().__init__()
        self.input_path = input_path
        self.output_dir = output_dir
        self.photo_preset = photo_preset
        self.paper = paper
        self.dpi = dpi
        self.add_border = add_border
        self.signals = LayoutWorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            images = collect_input_images(self.input_path)
            if not images:
                self.signals.finished.emit(0, 0, str(self.output_dir))
                return

            self._validate_images(images)
            self.output_dir.mkdir(parents=True, exist_ok=True)
            total = len(images)
            success_count = 0
            failed_count = 0

            for index, image_path in enumerate(images, start=1):
                self.signals.progress.emit(index, total, image_path.name)
                try:
                    output_path, plan = layout_one_id_photo(
                        image_path,
                        self.output_dir,
                        self.paper,
                        self.dpi,
                        self.add_border,
                        DEFAULT_SPACING_PX,
                    )
                except Exception as exc:
                    failed_count += 1
                    self.signals.log.emit(f"失败 {image_path.name}: {exc}")
                    continue
                success_count += 1
                self.signals.log.emit(f"完成 {image_path.name} -> {output_path.name}，{plan.orientation}，排入 {plan.count} 张")

            self.signals.finished.emit(success_count, failed_count, str(self.output_dir))
        except LayoutValidationError as exc:
            self.signals.failed.emit(str(exc))
        except Exception as exc:
            self.signals.failed.emit(f"处理失败: {exc}")

    def _validate_images(self, images: list[Path]) -> None:
        validate_layout_inputs(images, (self.photo_preset.width, self.photo_preset.height), self.dpi)


class IdPhotoLayoutPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._thread_pool = QThreadPool.globalInstance()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 28, 30, 28)
        layout.setSpacing(16)

        hero = build_hero("证件照排版", "选择已裁切好的证件照，按纸张尺寸和 DPI 自动计算最优横竖方向，并把每张输入图重复排满一张纸。")

        input_card = QFrame()
        input_card.setObjectName("inputCard")
        input_layout = QVBoxLayout(input_card)
        input_layout.setContentsMargins(18, 16, 18, 18)
        input_layout.setSpacing(10)
        input_layout.addWidget(section_title("选择输入与输出"))

        input_row = QHBoxLayout()
        input_row.setSpacing(10)
        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText("请选择已裁切好的证件照图片或目录")
        self.file_button = QPushButton("选择图片")
        self.folder_button = QPushButton("选择目录")
        input_row.addWidget(self.input_edit, 1)
        input_row.addWidget(self.file_button)
        input_row.addWidget(self.folder_button)

        output_row = QHBoxLayout()
        output_row.setSpacing(10)
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("默认输出到所选目录下的 layout_output")
        self.output_button = QPushButton("输出位置")
        output_row.addWidget(self.output_edit, 1)
        output_row.addWidget(self.output_button)
        input_layout.addLayout(input_row)
        input_layout.addLayout(output_row)

        settings_card = QFrame()
        settings_card.setObjectName("settingsCard")
        settings_layout = QVBoxLayout(settings_card)
        settings_layout.setContentsMargins(16, 14, 16, 16)
        settings_layout.setSpacing(10)
        settings_layout.addWidget(section_title("排版参数"))

        self.photo_combo = QComboBox()
        for preset in STANDARD_PRESETS:
            self.photo_combo.addItem(_preset_label(preset), preset)
        self.photo_combo.addItem("自定义尺寸", None)
        self.photo_combo.setMinimumHeight(36)

        self.photo_width_spin = QDoubleSpinBox()
        self.photo_width_spin.setRange(5, 300)
        self.photo_width_spin.setDecimals(1)
        self.photo_width_spin.setSuffix(" mm")
        self.photo_width_spin.setMinimumHeight(36)
        self.photo_height_spin = QDoubleSpinBox()
        self.photo_height_spin.setRange(5, 300)
        self.photo_height_spin.setDecimals(1)
        self.photo_height_spin.setSuffix(" mm")
        self.photo_height_spin.setMinimumHeight(36)

        self.paper_combo = QComboBox()
        for paper in PAPER_PRESETS:
            self.paper_combo.addItem(_paper_label(paper), paper)
        self.paper_combo.addItem("自定义纸张", None)
        self.paper_combo.setMinimumHeight(36)

        self.paper_width_spin = QDoubleSpinBox()
        self.paper_width_spin.setRange(20, 1000)
        self.paper_width_spin.setDecimals(1)
        self.paper_width_spin.setSuffix(" mm")
        self.paper_width_spin.setMinimumHeight(36)
        self.paper_height_spin = QDoubleSpinBox()
        self.paper_height_spin.setRange(20, 1000)
        self.paper_height_spin.setDecimals(1)
        self.paper_height_spin.setSuffix(" mm")
        self.paper_height_spin.setMinimumHeight(36)

        self.dpi_spin = QSpinBox()
        self.dpi_spin.setRange(72, 1200)
        self.dpi_spin.setValue(300)
        self.dpi_spin.setSuffix(" DPI")
        self.dpi_spin.setMinimumHeight(36)

        self.border_check = QCheckBox("添加 1px 黑色描边")
        self.border_check.setMinimumHeight(36)
        self.summary_label = QLabel()
        self.summary_label.setObjectName("layoutSummary")
        self.summary_label.setWordWrap(True)

        spec_group = QFrame()
        spec_group.setObjectName("settingGroup")
        spec_layout = QVBoxLayout(spec_group)
        spec_layout.setContentsMargins(12, 9, 12, 12)
        spec_layout.setSpacing(7)
        spec_layout.addWidget(field_label("证件照规格"))
        spec_layout.addWidget(self.photo_combo)
        photo_size_row = QHBoxLayout()
        photo_size_row.setSpacing(8)
        photo_size_row.addWidget(self.photo_width_spin)
        photo_size_row.addWidget(QLabel("x"))
        photo_size_row.addWidget(self.photo_height_spin)
        spec_layout.addLayout(photo_size_row)

        paper_group = QFrame()
        paper_group.setObjectName("settingGroup")
        paper_layout = QVBoxLayout(paper_group)
        paper_layout.setContentsMargins(12, 9, 12, 12)
        paper_layout.setSpacing(7)
        paper_layout.addWidget(field_label("纸张大小"))
        paper_layout.addWidget(self.paper_combo)
        paper_size_row = QHBoxLayout()
        paper_size_row.setSpacing(8)
        paper_size_row.addWidget(self.paper_width_spin)
        paper_size_row.addWidget(QLabel("x"))
        paper_size_row.addWidget(self.paper_height_spin)
        paper_layout.addLayout(paper_size_row)

        output_group = QFrame()
        output_group.setObjectName("settingGroup")
        output_layout = QVBoxLayout(output_group)
        output_layout.setContentsMargins(12, 9, 12, 12)
        output_layout.setSpacing(7)
        output_layout.addWidget(field_label("输出设置"))
        output_layout.addWidget(self.dpi_spin)
        output_layout.addWidget(self.border_check)
        spacing_hint = QLabel("照片间距固定 25px，JPG 白底输出，质量 100")
        spacing_hint.setObjectName("fieldHint")
        spacing_hint.setWordWrap(True)
        output_layout.addWidget(spacing_hint)

        settings_row = QHBoxLayout()
        settings_row.setSpacing(10)
        settings_row.addWidget(spec_group, 1)
        settings_row.addWidget(paper_group, 1)
        settings_row.addWidget(output_group, 1)
        settings_layout.addLayout(settings_row)
        settings_layout.addWidget(self.summary_label)

        action_row = QHBoxLayout()
        self.start_button = QPushButton("开始排版")
        self.start_button.setEnabled(False)
        self.start_button.setMinimumHeight(40)
        self.start_button.setMinimumWidth(136)
        action_row.addStretch()
        action_row.addWidget(self.start_button)
        settings_layout.addLayout(action_row)

        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.status = QLabel("等待选择图片或目录")
        self.status.setObjectName("statusText")
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setPlaceholderText("处理日志")

        layout.addWidget(hero)
        layout.addWidget(input_card)
        layout.addWidget(settings_card)
        layout.addWidget(self.progress)
        layout.addWidget(self.status)
        layout.addWidget(field_label("处理详情"))
        layout.addWidget(self.log, 1)

        self.file_button.clicked.connect(self._choose_file)
        self.folder_button.clicked.connect(self._choose_folder)
        self.output_button.clicked.connect(self._choose_output)
        self.start_button.clicked.connect(self._start)
        self.input_edit.textChanged.connect(self._update_start_state)
        self.photo_combo.currentIndexChanged.connect(self._apply_photo_preset)
        self.paper_combo.currentIndexChanged.connect(self._apply_paper_preset)
        self.photo_width_spin.valueChanged.connect(self._update_summary)
        self.photo_height_spin.valueChanged.connect(self._update_summary)
        self.paper_width_spin.valueChanged.connect(self._update_summary)
        self.paper_height_spin.valueChanged.connect(self._update_summary)
        self.dpi_spin.valueChanged.connect(self._update_summary)
        self.border_check.stateChanged.connect(self._update_summary)
        self._apply_photo_preset()
        self._apply_paper_preset()
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
        self.output_edit.setText(str(base / "layout_output"))

    def _apply_photo_preset(self) -> None:
        preset = self.photo_combo.currentData()
        custom = preset is None
        if preset is not None:
            self.photo_width_spin.setValue(preset.width_mm or 25)
            self.photo_height_spin.setValue(preset.height_mm or 35)
        self.photo_width_spin.setEnabled(custom)
        self.photo_height_spin.setEnabled(custom)
        self._update_summary()

    def _apply_paper_preset(self) -> None:
        paper = self.paper_combo.currentData()
        custom = paper is None
        if paper is not None:
            self.paper_width_spin.setValue(paper.width_mm)
            self.paper_height_spin.setValue(paper.height_mm)
        self.paper_width_spin.setEnabled(custom)
        self.paper_height_spin.setEnabled(custom)
        self._update_summary()

    def _update_summary(self) -> None:
        if not hasattr(self, "summary_label"):
            return
        dpi = self.dpi_spin.value()
        photo_width, photo_height = self._photo_pixels()
        paper = self._selected_paper()
        border_extra = 2 if self.border_check.isChecked() else 0
        try:
            plan = calculate_best_layout(photo_width + border_extra, photo_height + border_extra, paper, dpi, DEFAULT_SPACING_PX)
            summary = (
                f"证件照 {photo_width} x {photo_height} px · 纸张 {paper.width_mm:g} x {paper.height_mm:g} mm · "
                f"最优 {plan.orientation} {plan.paper_width_px} x {plan.paper_height_px} px · "
                f"{plan.columns} 列 x {plan.rows} 行，共 {plan.count} 张"
            )
        except Exception as exc:
            summary = f"当前参数无法排版：{exc}"
        self.summary_label.setText(summary)

    def _update_start_state(self) -> None:
        self.start_button.setEnabled(bool(self.input_edit.text().strip()))

    def _start(self) -> None:
        input_path = Path(self.input_edit.text()).expanduser()
        if not input_path.exists():
            QMessageBox.warning(self, "路径无效", "请选择有效的图片文件或照片目录。")
            return

        output_text = self.output_edit.text().strip()
        output_dir = Path(output_text).expanduser() if output_text else self._default_output_for(input_path)
        photo_preset = self._selected_photo_preset()
        paper = self._selected_paper()

        self.log.clear()
        self.progress.setValue(0)
        self.status.setText("准备排版...")
        self._set_controls_enabled(False)

        worker = IdPhotoLayoutWorker(input_path, output_dir, photo_preset, paper, self.dpi_spin.value(), self.border_check.isChecked())
        worker.signals.progress.connect(self._on_progress)
        worker.signals.log.connect(self._append_log)
        worker.signals.finished.connect(self._on_finished)
        worker.signals.failed.connect(self._on_failed)
        self._thread_pool.start(worker)

    def _default_output_for(self, input_path: Path) -> Path:
        base = input_path if input_path.is_dir() else input_path.parent
        return base / "layout_output"

    def _selected_photo_preset(self) -> CropPreset:
        preset = self.photo_combo.currentData()
        width_px, height_px = self._photo_pixels()
        if preset is not None:
            return CropPreset(preset.name, width_px, height_px, preset.head_ratio, preset.face_center_y, preset.width_mm, preset.height_mm, self.dpi_spin.value(), 10)
        return CropPreset("自定义", width_px, height_px, 0.58, 0.43, self.photo_width_spin.value(), self.photo_height_spin.value(), self.dpi_spin.value(), 10)

    def _selected_paper(self) -> PaperPreset:
        paper = self.paper_combo.currentData()
        if paper is not None:
            return paper
        return PaperPreset("自定义纸张", self.paper_width_spin.value(), self.paper_height_spin.value())

    def _photo_pixels(self) -> tuple[int, int]:
        dpi = self.dpi_spin.value()
        return mm_to_pixels(self.photo_width_spin.value(), dpi), mm_to_pixels(self.photo_height_spin.value(), dpi)

    def _set_controls_enabled(self, enabled: bool) -> None:
        self.file_button.setEnabled(enabled)
        self.folder_button.setEnabled(enabled)
        self.output_button.setEnabled(enabled)
        self.photo_combo.setEnabled(enabled)
        self.paper_combo.setEnabled(enabled)
        self.photo_width_spin.setEnabled(enabled and self.photo_combo.currentData() is None)
        self.photo_height_spin.setEnabled(enabled and self.photo_combo.currentData() is None)
        self.paper_width_spin.setEnabled(enabled and self.paper_combo.currentData() is None)
        self.paper_height_spin.setEnabled(enabled and self.paper_combo.currentData() is None)
        self.dpi_spin.setEnabled(enabled)
        self.border_check.setEnabled(enabled)
        self.start_button.setEnabled(enabled and bool(self.input_edit.text().strip()))

    def _on_progress(self, index: int, total: int, filename: str) -> None:
        self.progress.setMaximum(total)
        self.progress.setValue(index)
        self.status.setText(f"正在排版 {index}/{total}: {filename}")

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


def _preset_label(preset: CropPreset) -> str:
    if preset.width_mm is None or preset.height_mm is None:
        return f"{preset.name} - {preset.width}x{preset.height}px"
    return f"{preset.name} - {preset.width_mm:g}x{preset.height_mm:g} mm"


def _paper_label(paper: PaperPreset) -> str:
    return f"{paper.name} - {paper.width_mm:g}x{paper.height_mm:g} mm"


def _stylesheet() -> str:
    return """
        QComboBox, QSpinBox, QDoubleSpinBox {
            min-height: 28px;
        }
        #layoutSummary {
            background: #f2f7ff;
            border: 1px solid #d7e8ff;
            border-radius: 8px;
            color: #0057d9;
            font-weight: 700;
            padding: 8px 10px;
        }
    """
