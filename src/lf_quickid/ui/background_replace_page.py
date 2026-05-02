from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Qt, Signal, Slot
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QColorDialog,
    QComboBox,
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

from lf_quickid.core.background_replacer import (
    BackgroundPreset,
    MattingUnavailable,
    PortraitMattingEngine,
    background_presets,
    collect_input_images,
    replace_background_one,
)


class BackgroundReplaceSignals(QObject):
    progress = Signal(int, int, str)
    finished = Signal(int, int, str)
    failed = Signal(str)
    log = Signal(str)


class BackgroundReplaceWorker(QRunnable):
    def __init__(self, input_path: Path, output_dir: Path, preset: BackgroundPreset, quality: int) -> None:
        super().__init__()
        self.input_path = input_path
        self.output_dir = output_dir
        self.preset = preset
        self.quality = quality
        self.signals = BackgroundReplaceSignals()

    @Slot()
    def run(self) -> None:
        try:
            images = collect_input_images(self.input_path)
            if not images:
                self.signals.finished.emit(0, 0, str(self.output_dir))
                return

            self.output_dir.mkdir(parents=True, exist_ok=True)
            self.signals.log.emit(f"找到 {len(images)} 张图片，正在加载本地人像抠图模型...")
            engine = PortraitMattingEngine()
            total = len(images)
            success_count = 0
            failed_count = 0

            for index, image_path in enumerate(images, start=1):
                self.signals.progress.emit(index, total, image_path.name)
                try:
                    output_path = replace_background_one(image_path, self.output_dir, self.preset, engine, self.quality)
                except Exception as exc:
                    failed_count += 1
                    self.signals.log.emit(f"失败 {image_path.name}: {exc}")
                    continue
                success_count += 1
                self.signals.log.emit(f"完成 {image_path.name} -> {output_path.name}")

            self.signals.finished.emit(success_count, failed_count, str(self.output_dir))
        except MattingUnavailable as exc:
            self.signals.failed.emit(str(exc))
        except Exception as exc:
            self.signals.failed.emit(f"处理失败: {exc}")


class BackgroundReplacePage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._thread_pool = QThreadPool.globalInstance()
        self._custom_color_bgr = (255, 255, 255)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 26, 28, 26)
        layout.setSpacing(18)

        header = QLabel("证件照换背景")
        header.setObjectName("pageTitle")
        description = QLabel("选择图片或目录后，程序会在本机批量抠出人像，并合成为红底、蓝底或白底图片。")
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
        self.output_edit.setPlaceholderText("默认输出到所选目录下的 bg_output")
        self.output_button = QPushButton("输出位置")
        output_row.addWidget(self.output_edit, 1)
        output_row.addWidget(self.output_button)

        settings_card = QFrame()
        settings_card.setObjectName("settingsCard")
        settings_layout = QVBoxLayout(settings_card)
        settings_layout.setContentsMargins(16, 14, 16, 16)
        settings_layout.setSpacing(10)

        settings_title = QLabel("换背景参数")
        settings_title.setObjectName("sectionTitle")
        settings_layout.addWidget(settings_title)

        settings_row = QHBoxLayout()
        settings_row.setSpacing(10)

        background_group = QFrame()
        background_group.setObjectName("settingGroup")
        background_layout = QVBoxLayout(background_group)
        background_layout.setContentsMargins(12, 9, 12, 12)
        background_layout.setSpacing(7)
        background_layout.addWidget(_field_label("背景颜色"))
        self.background_combo = QComboBox()
        for preset in background_presets():
            self.background_combo.addItem(preset.name, preset)
        self.background_combo.addItem("自定义颜色", None)
        self.background_combo.setMinimumHeight(36)

        background_row = QHBoxLayout()
        background_row.setSpacing(8)
        self.color_preview = QFrame()
        self.color_preview.setObjectName("colorPreview")
        self.color_preview.setFixedSize(38, 38)
        self.custom_color_button = QPushButton("选择颜色")
        self.custom_color_button.setObjectName("secondaryButton")
        self.custom_color_button.setMinimumHeight(36)
        background_row.addWidget(self.background_combo, 1)
        background_row.addWidget(self.color_preview)
        background_row.addWidget(self.custom_color_button)
        background_layout.addLayout(background_row)

        quality_group = QFrame()
        quality_group.setObjectName("settingGroup")
        quality_layout = QVBoxLayout(quality_group)
        quality_layout.setContentsMargins(12, 9, 12, 12)
        quality_layout.setSpacing(7)
        quality_layout.addWidget(_field_label("输出质量"))
        quality_row = QHBoxLayout()
        quality_row.setSpacing(8)
        self.quality_spin = QSpinBox()
        self.quality_spin.setRange(1, 100)
        self.quality_spin.setValue(100)
        self.quality_spin.setMinimumHeight(36)
        quality_hint = QLabel("JPEG/WebP 输出质量，默认 100")
        quality_hint.setObjectName("fieldHint")
        quality_row.addWidget(self.quality_spin)
        quality_row.addWidget(quality_hint, 1)
        quality_layout.addLayout(quality_row)

        settings_row.addWidget(background_group, 1)
        settings_row.addWidget(quality_group, 1)
        settings_layout.addLayout(settings_row)

        action_row = QHBoxLayout()
        self.start_button = QPushButton("开始换背景")
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
        self.background_combo.currentIndexChanged.connect(self._on_background_changed)
        self.custom_color_button.clicked.connect(self._choose_custom_color)
        self.setStyleSheet(_stylesheet())
        self._on_background_changed()

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
        self.output_edit.setText(str(base / "bg_output"))

    def _update_start_state(self) -> None:
        self.start_button.setEnabled(bool(self.input_edit.text().strip()))

    def _start(self) -> None:
        input_path = Path(self.input_edit.text()).expanduser()
        if not input_path.exists():
            QMessageBox.warning(self, "路径无效", "请选择有效的图片文件或照片目录。")
            return

        output_text = self.output_edit.text().strip()
        output_dir = Path(output_text).expanduser() if output_text else self._default_output_for(input_path)
        preset = self._selected_background_preset()

        self.log.clear()
        self.progress.setValue(0)
        self.status.setText("准备换背景...")
        self._set_controls_enabled(False)

        worker = BackgroundReplaceWorker(input_path, output_dir, preset, self.quality_spin.value())
        worker.signals.progress.connect(self._on_progress)
        worker.signals.log.connect(self._append_log)
        worker.signals.finished.connect(self._on_finished)
        worker.signals.failed.connect(self._on_failed)
        self._thread_pool.start(worker)

    def _default_output_for(self, input_path: Path) -> Path:
        base = input_path if input_path.is_dir() else input_path.parent
        return base / "bg_output"

    def _set_controls_enabled(self, enabled: bool) -> None:
        self.file_button.setEnabled(enabled)
        self.folder_button.setEnabled(enabled)
        self.output_button.setEnabled(enabled)
        self.background_combo.setEnabled(enabled)
        self.custom_color_button.setEnabled(enabled and self.background_combo.currentData() is None)
        self.quality_spin.setEnabled(enabled)
        self.start_button.setEnabled(enabled and bool(self.input_edit.text().strip()))

    def _on_background_changed(self) -> None:
        preset = self._selected_background_preset()
        self.custom_color_button.setEnabled(self.background_combo.currentData() is None)
        self._set_color_preview(preset.color_bgr)

    def _choose_custom_color(self) -> None:
        color = QColorDialog.getColor(_qcolor_from_bgr(self._custom_color_bgr), self, "选择背景颜色")
        if not color.isValid():
            return
        self._custom_color_bgr = (color.blue(), color.green(), color.red())
        self._set_color_preview(self._custom_color_bgr)

    def _selected_background_preset(self) -> BackgroundPreset:
        preset = self.background_combo.currentData()
        if preset is not None:
            return preset
        return BackgroundPreset("custom", "自定义颜色", self._custom_color_bgr)

    def _set_color_preview(self, color_bgr: tuple[int, int, int]) -> None:
        self.color_preview.setStyleSheet(
            "#colorPreview {"
            f"background: {_css_color_from_bgr(color_bgr)};"
            "border: 1px solid #98a2b3;"
            "border-radius: 10px;"
            "}"
        )

    def _on_progress(self, index: int, total: int, filename: str) -> None:
        self.progress.setMaximum(total)
        self.progress.setValue(index)
        self.status.setText(f"正在换背景 {index}/{total}: {filename}")

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
        QComboBox, QSpinBox {
            background: #ffffff;
            border: 1px solid #d0d5dd;
            border-radius: 10px;
            padding: 4px 9px;
            font-size: 14px;
        }
        QComboBox:disabled, QSpinBox:disabled {
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
        #secondaryButton {
            background: #eef4ff;
            color: #2563eb;
            padding: 6px 11px;
        }
        #secondaryButton:hover {
            background: #dbeafe;
        }
    """


def _field_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("fieldLabel")
    return label


def _qcolor_from_bgr(color_bgr: tuple[int, int, int]) -> QColor:
    blue, green, red = color_bgr
    return QColor(red, green, blue)


def _css_color_from_bgr(color_bgr: tuple[int, int, int]) -> str:
    blue, green, red = color_bgr
    return f"#{red:02x}{green:02x}{blue:02x}"
