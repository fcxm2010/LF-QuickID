from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QFile, QObject, QRunnable, QSize, QThreadPool, Qt, Signal, Slot
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QScrollArea,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from lf_quickid.core.face_clusterer import cluster_faces
from lf_quickid.core.face_detector import FaceAnalyzerUnavailable, InsightFaceAnalyzer
from lf_quickid.core.face_group_exporter import ExportSummary, export_face_groups
from lf_quickid.core.face_group_namer import label_face_groups
from lf_quickid.core.face_group_state import remove_face_from_group, remove_image_from_groups
from lf_quickid.core.image_scanner import scan_images
from lf_quickid.core.models import FaceGroup, FaceRecord
from lf_quickid.ui.theme import build_hero, field_label, section_title


_GROUP_TONES = (
    ("#fff7ed", "#fed7aa"),
    ("#ecfdf5", "#bbf7d0"),
    ("#eff6ff", "#bfdbfe"),
    ("#fdf2f8", "#fbcfe8"),
    ("#f5f3ff", "#ddd6fe"),
    ("#f8fafc", "#cbd5e1"),
)


class WorkerSignals(QObject):
    progress = Signal(int, int, str)
    finished = Signal(list)
    failed = Signal(str)
    log = Signal(str)


class FaceGroupingWorker(QRunnable):
    def __init__(self, directory: Path) -> None:
        super().__init__()
        self.directory = directory
        self.signals = WorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            images = scan_images(self.directory)
            if not images:
                self.signals.finished.emit([])
                return

            self.signals.log.emit(f"找到 {len(images)} 张图片，正在加载本地人脸模型...")
            analyzer = InsightFaceAnalyzer()

            faces = []
            total = len(images)
            for index, image in enumerate(images, start=1):
                self.signals.progress.emit(index, total, image.path.name)
                try:
                    found = analyzer.analyze_image(image.path)
                except Exception as exc:
                    self.signals.log.emit(f"跳过 {image.path.name}: {exc}")
                    continue
                faces.extend(found)
                self.signals.log.emit(f"{image.path.name}: 检测到 {len(found)} 张人脸")

            groups = cluster_faces(faces)
            label_face_groups(groups, self.signals.log.emit)
            self.signals.finished.emit(groups)
        except FaceAnalyzerUnavailable as exc:
            self.signals.failed.emit(str(exc))
        except Exception as exc:
            self.signals.failed.emit(f"处理失败: {exc}")


class ExportSignals(QObject):
    progress = Signal(int, int, str)
    finished = Signal(object)
    failed = Signal(str)
    log = Signal(str)


class FaceGroupExportWorker(QRunnable):
    def __init__(self, groups: list[FaceGroup], output_dir: Path) -> None:
        super().__init__()
        self.groups = groups
        self.output_dir = output_dir
        self.signals = ExportSignals()

    @Slot()
    def run(self) -> None:
        try:
            summary = export_face_groups(self.groups, self.output_dir, self._on_progress)
        except Exception as exc:
            self.signals.failed.emit(f"导出失败: {exc}")
            return
        self.signals.finished.emit(summary)

    def _on_progress(self, index: int, total: int, source: Path) -> None:
        self.signals.progress.emit(index, total, source.name)


class FaceGroupPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._thread_pool = QThreadPool.globalInstance()
        self._groups_layout: QGridLayout | None = None
        self._groups: list[FaceGroup] = []
        self._export_worker: FaceGroupExportWorker | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 28, 30, 28)
        layout.setSpacing(16)

        hero = build_hero("人脸分组", "选择照片目录后，程序会在本机识别人脸，并把疑似同一个人聚合到一起。适合婚礼、活动、班级照片的快速整理。")

        input_card = QFrame()
        input_card.setObjectName("inputCard")
        input_layout = QVBoxLayout(input_card)
        input_layout.setContentsMargins(18, 16, 18, 18)
        input_layout.setSpacing(10)
        input_layout.addWidget(section_title("选择照片目录"))

        picker = QHBoxLayout()
        picker.setSpacing(10)
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("请选择包含照片的目录")
        self.browse_button = QPushButton("选择目录")
        self.start_button = QPushButton("开始识别")
        self.start_button.setEnabled(False)
        self.start_button.setMinimumWidth(132)
        picker.addWidget(self.path_edit, 1)
        picker.addWidget(self.browse_button)
        picker.addWidget(self.start_button)
        input_layout.addLayout(picker)

        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.status = QLabel("等待选择目录")
        self.status.setObjectName("statusText")

        result_panel = QFrame()
        result_panel.setObjectName("resultPanel")
        result_layout = QVBoxLayout(result_panel)
        result_layout.setContentsMargins(16, 16, 16, 16)
        result_layout.setSpacing(12)

        result_header = QHBoxLayout()
        result_header.setSpacing(10)
        result_header.addWidget(section_title("识别结果"))
        result_header.addStretch()
        self.export_button = QPushButton("导出分组")
        self.export_button.setObjectName("secondaryButton")
        self.export_button.setEnabled(False)
        result_header.addWidget(self.export_button)
        result_layout.addLayout(result_header)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.results = QWidget()
        self._groups_layout = QGridLayout(self.results)
        self._groups_layout.setContentsMargins(0, 0, 0, 0)
        self._groups_layout.setSpacing(14)
        self.scroll.setWidget(self.results)
        result_layout.addWidget(self.scroll, 1)
        self._append_empty_state("选择照片目录后，识别到的人脸分组会显示在这里。")

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setFixedHeight(118)
        self.log.setPlaceholderText("处理日志")

        layout.addWidget(hero)
        layout.addWidget(input_card)
        layout.addWidget(self.progress)
        layout.addWidget(self.status)
        layout.addWidget(result_panel, 1)
        layout.addWidget(field_label("处理详情"))
        layout.addWidget(self.log)

        self.browse_button.clicked.connect(self._choose_directory)
        self.start_button.clicked.connect(self._start)
        self.export_button.clicked.connect(self._export_groups)
        self.path_edit.textChanged.connect(self._update_start_state)
        self.setStyleSheet(_stylesheet())

    def _choose_directory(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "选择照片目录")
        if directory:
            self.path_edit.setText(directory)

    def _update_start_state(self) -> None:
        self.start_button.setEnabled(bool(self.path_edit.text().strip()))

    def _start(self) -> None:
        directory = Path(self.path_edit.text()).expanduser()
        if not directory.is_dir():
            QMessageBox.warning(self, "目录无效", "请选择一个有效的照片目录。")
            return

        self._groups = []
        self._clear_results()
        self._set_export_enabled(False)
        self.log.clear()
        self.progress.setValue(0)
        self.status.setText("准备处理...")
        self._set_recognition_controls_enabled(False)

        worker = FaceGroupingWorker(directory)
        worker.signals.progress.connect(self._on_progress)
        worker.signals.log.connect(self._append_log)
        worker.signals.finished.connect(self._on_finished)
        worker.signals.failed.connect(self._on_failed)
        self._thread_pool.start(worker)

    def _set_recognition_controls_enabled(self, enabled: bool) -> None:
        self.browse_button.setEnabled(enabled)
        self.start_button.setEnabled(enabled and bool(self.path_edit.text().strip()))
        self.path_edit.setEnabled(enabled)
        self._set_export_enabled(enabled and bool(self._groups))

    def _on_progress(self, index: int, total: int, filename: str) -> None:
        self.progress.setMaximum(total)
        self.progress.setValue(index)
        self.status.setText(f"正在处理 {index}/{total}: {filename}")

    def _append_log(self, message: str) -> None:
        self.log.append(message)

    def _on_finished(self, groups: list[FaceGroup]) -> None:
        self._set_recognition_controls_enabled(True)
        self._groups = groups

        if not groups:
            self.status.setText("未找到可分组的人脸。")
            self._render_current_groups("未检测到人脸或目录中没有支持的图片。")
            return

        self._update_result_status()
        self._render_current_groups()

    def _on_failed(self, message: str) -> None:
        self._set_recognition_controls_enabled(True)
        self.status.setText("处理失败")
        QMessageBox.critical(self, "处理失败", message)
        self._append_log(message)

    def _clear_results(self) -> None:
        if self._groups_layout is None:
            return
        while self._groups_layout.count():
            item = self._groups_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _append_empty_state(self, text: str) -> None:
        if self._groups_layout is None:
            return
        label = QLabel(text)
        label.setAlignment(Qt.AlignCenter)
        label.setObjectName("emptyState")
        label.setWordWrap(True)
        self._groups_layout.addWidget(label, 0, 0)

    def _render_current_groups(self, empty_text: str | None = None) -> None:
        self._clear_results()
        if not self._groups:
            self._append_empty_state(empty_text or "当前没有可显示的分组。")
            self._set_export_enabled(False)
            return

        columns = 2
        for index, group in enumerate(self._groups):
            card = _GroupCard(group, index)
            card.preview_requested.connect(self._open_face_preview)
            self._groups_layout.addWidget(card, index // columns, index % columns)
        self._groups_layout.setRowStretch((len(self._groups) + columns - 1) // columns, 1)
        self._set_export_enabled(True)

    def _open_face_preview(self, group: FaceGroup, face: FaceRecord) -> None:
        dialog = _FacePreviewDialog(group, face, self)
        dialog.remove_requested.connect(lambda target_group, target_face: self._remove_face_from_current_group(dialog, target_group, target_face))
        dialog.delete_requested.connect(lambda target_group, target_face: self._delete_image_from_all_groups(dialog, target_group, target_face))
        dialog.exec()

    def _remove_face_from_current_group(self, dialog: QDialog, group: FaceGroup, face: FaceRecord) -> None:
        self._groups = remove_face_from_group(self._groups, group, face)
        dialog.accept()
        self._after_group_mutation(f"已从“{group.label}”移出 {face.image_path.name}。")

    def _delete_image_from_all_groups(self, dialog: QDialog, group: FaceGroup, face: FaceRecord) -> None:
        reply = QMessageBox.question(
            dialog,
            "删除照片",
            f"确定要把“{face.image_path.name}”移到系统废纸篓，并从所有分组中移除吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        try:
            result = QFile.moveToTrash(str(face.image_path))
        except Exception as exc:
            QMessageBox.warning(dialog, "删除失败", f"无法移到废纸篓：{exc}")
            return

        success = result[0] if isinstance(result, tuple) else bool(result)
        if not success:
            QMessageBox.warning(dialog, "删除失败", "系统没有成功把照片移到废纸篓，文件未从分组中移除。")
            return

        self._groups = remove_image_from_groups(self._groups, face.image_path)
        dialog.accept()
        self._after_group_mutation(f"已删除 {face.image_path.name}，并从所有分组移除。")

    def _after_group_mutation(self, message: str) -> None:
        self._append_log(message)
        if self._groups:
            self._update_result_status()
            self._render_current_groups()
            return
        self.status.setText("当前分组已清空。")
        self._render_current_groups("当前分组已清空。")

    def _update_result_status(self) -> None:
        self.status.setText(f"完成：识别出 {sum(len(group.faces) for group in self._groups)} 张人脸，聚为 {len(self._groups)} 组。")

    def _export_groups(self) -> None:
        if not self._groups:
            QMessageBox.information(self, "没有可导出的分组", "当前没有可导出的分组结果。")
            return
        directory = QFileDialog.getExistingDirectory(self, "选择导出目录")
        if not directory:
            return

        self._set_export_enabled(False)
        self.progress.setValue(0)
        self.status.setText("准备导出分组...")
        self._export_worker = FaceGroupExportWorker(_snapshot_groups(self._groups), Path(directory).expanduser())
        self._export_worker.signals.progress.connect(self._on_export_progress)
        self._export_worker.signals.finished.connect(self._on_export_finished)
        self._export_worker.signals.failed.connect(self._on_export_failed)
        self._thread_pool.start(self._export_worker)

    def _on_export_progress(self, index: int, total: int, filename: str) -> None:
        self.progress.setMaximum(total)
        self.progress.setValue(index)
        self.status.setText(f"正在导出 {index}/{total}: {filename}")

    def _on_export_finished(self, summary: ExportSummary) -> None:
        self._export_worker = None
        self._set_export_enabled(bool(self._groups))
        for failure in summary.failures:
            self._append_log(f"导出失败 {failure.source.name}: {failure.message}")
        self.status.setText(
            f"导出完成：{summary.group_count} 组，复制 {summary.copied_count} 张，失败 {summary.failed_count} 张。目录：{summary.output_dir}"
        )

    def _on_export_failed(self, message: str) -> None:
        self._export_worker = None
        self._set_export_enabled(bool(self._groups))
        self.status.setText("导出失败")
        self._append_log(message)
        QMessageBox.critical(self, "导出失败", message)

    def _set_export_enabled(self, enabled: bool) -> None:
        self.export_button.setEnabled(enabled and bool(self._groups) and self._export_worker is None)


class _GroupCard(QFrame):
    preview_requested = Signal(object, object)

    def __init__(self, group: FaceGroup, index: int) -> None:
        super().__init__()
        self.group = group
        tone, border = _GROUP_TONES[index % len(_GROUP_TONES)]
        self.setObjectName("groupCard")
        self.setStyleSheet(
            "QFrame#groupCard {"
            f"background: {tone};"
            f"border: 1px solid {border};"
            "border-radius: 10px;"
            "}"
            "QFrame#groupCard:hover { border: 1px solid #94a3b8; }"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(9)

        title = QLineEdit(group.label)
        title.setObjectName("groupTitleEdit")
        title.setPlaceholderText("输入分组名称")
        title.textEdited.connect(self._update_group_label)

        count = QLabel(f"出现 {len(group.faces)} 次 · 涉及 {group.image_count} 张照片")
        count.setObjectName("groupMeta")

        thumbnails = QWidget()
        thumbnails.setObjectName("thumbnailGrid")
        thumbnails_layout = QGridLayout(thumbnails)
        thumbnails_layout.setContentsMargins(0, 2, 0, 0)
        thumbnails_layout.setHorizontalSpacing(8)
        thumbnails_layout.setVerticalSpacing(8)

        if group.faces:
            columns = 4
            for face_index, face in enumerate(group.faces):
                button = _thumbnail_button(face)
                button.clicked.connect(lambda checked=False, value=face: self.preview_requested.emit(self.group, value))
                thumbnails_layout.addWidget(button, face_index // columns, face_index % columns)
        else:
            empty = QLabel("空分组")
            empty.setObjectName("groupPaths")
            thumbnails_layout.addWidget(empty, 0, 0)

        layout.addWidget(title)
        layout.addWidget(count)
        layout.addWidget(thumbnails)

    def _update_group_label(self, text: str) -> None:
        self.group.label = text.strip()


class _FacePreviewDialog(QDialog):
    remove_requested = Signal(object, object)
    delete_requested = Signal(object, object)

    def __init__(self, group: FaceGroup, face: FaceRecord, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.group = group
        self.face = face
        self.setWindowTitle(f"查看照片 - {face.image_path.name}")
        self.setMinimumSize(820, 680)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        image = QLabel()
        image.setObjectName("previewImage")
        image.setAlignment(Qt.AlignCenter)
        image.setMinimumSize(760, 520)
        preview = _pixmap_with_face_box(face.image_path, face.bbox, QSize(980, 620))
        if preview is None:
            image.setText("无法读取图片")
        else:
            image.setPixmap(preview)

        details = QLabel(f"分组：{group.label or '未命名'} · 文件：{face.image_path.name}")
        details.setObjectName("groupMeta")
        details.setWordWrap(True)

        buttons = QHBoxLayout()
        buttons.addWidget(details, 1)
        remove_button = QPushButton("移出分组")
        remove_button.setObjectName("secondaryButton")
        delete_button = QPushButton("删除照片")
        delete_button.setObjectName("dangerButton")
        close_button = QPushButton("关闭")
        close_button.setObjectName("secondaryButton")
        buttons.addWidget(remove_button)
        buttons.addWidget(delete_button)
        buttons.addWidget(close_button)

        layout.addWidget(image, 1)
        layout.addLayout(buttons)

        remove_button.clicked.connect(lambda: self.remove_requested.emit(self.group, self.face))
        delete_button.clicked.connect(lambda: self.delete_requested.emit(self.group, self.face))
        close_button.clicked.connect(self.reject)
        self.setStyleSheet(_stylesheet())


def _thumbnail_button(face: FaceRecord) -> QToolButton:
    button = QToolButton()
    button.setObjectName("thumbnailButton")
    button.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
    button.setIconSize(QSize(76, 76))
    button.setFixedSize(104, 118)
    button.setToolTip(str(face.image_path))
    button.setText(_compact_filename(face.image_path.name))

    pixmap = _thumbnail_pixmap(face)
    if pixmap is not None:
        button.setIcon(QIcon(pixmap))
    return button


def _thumbnail_pixmap(face: FaceRecord) -> QPixmap | None:
    pixmap = QPixmap()
    if face.thumbnail_jpeg and pixmap.loadFromData(face.thumbnail_jpeg, "JPEG"):
        return pixmap
    pixmap = QPixmap(str(face.image_path))
    if pixmap.isNull():
        return None
    return pixmap


def _pixmap_with_face_box(image_path: Path, bbox: tuple[int, int, int, int], max_size: QSize) -> QPixmap | None:
    pixmap = QPixmap(str(image_path))
    if pixmap.isNull():
        return None
    scaled = pixmap.scaled(max_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    if scaled.isNull():
        return None

    scale_x = scaled.width() / pixmap.width()
    scale_y = scaled.height() / pixmap.height()
    x1, y1, x2, y2 = bbox

    painter = QPainter(scaled)
    pen = QPen(QColor("#f97316"))
    pen.setWidth(max(3, int(round(min(scaled.width(), scaled.height()) * 0.006))))
    painter.setPen(pen)
    painter.drawRect(
        int(round(x1 * scale_x)),
        int(round(y1 * scale_y)),
        int(round((x2 - x1) * scale_x)),
        int(round((y2 - y1) * scale_y)),
    )
    painter.end()
    return scaled


def _compact_filename(filename: str) -> str:
    if len(filename) <= 13:
        return filename
    path = Path(filename)
    stem = path.stem
    suffix = path.suffix
    if len(stem) <= 8:
        return filename[:12] + "..."
    return f"{stem[:4]}...{stem[-3:]}{suffix}"


def _snapshot_groups(groups: list[FaceGroup]) -> list[FaceGroup]:
    return [FaceGroup(label=group.label, faces=list(group.faces), label_source=group.label_source) for group in groups if group.faces]


def _stylesheet() -> str:
    return """
        #groupCard {
            min-width: 300px;
        }
        #groupTitleEdit {
            font-size: 15px;
            font-weight: 750;
            color: #111827;
            background: rgba(255, 255, 255, 180);
        }
        #groupMeta {
            background: transparent;
            color: #1d4f91;
            font-weight: 650;
        }
        #thumbnailGrid {
            background: transparent;
        }
        #thumbnailButton {
            background: rgba(255, 255, 255, 190);
            border: 1px solid rgba(148, 163, 184, 130);
            border-radius: 8px;
            color: #344054;
            padding: 5px;
            font-size: 11px;
        }
        #thumbnailButton:hover {
            background: #ffffff;
            border-color: #64748b;
        }
        #previewImage {
            background: #0f172a;
            border-radius: 8px;
            color: #e5e7eb;
        }
        #dangerButton {
            background: #b42318;
            border: 1px solid #b42318;
            color: #ffffff;
        }
        #dangerButton:hover {
            background: #d92d20;
            border-color: #d92d20;
        }
        #emptyState {
            background: #ffffff;
            border: 1px dashed #cfd6e2;
            border-radius: 10px;
            color: #667085;
            padding: 76px;
        }
    """
