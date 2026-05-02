from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Qt, Signal, Slot
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
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
    QVBoxLayout,
    QWidget,
)

from lf_quickid.core.face_clusterer import cluster_faces
from lf_quickid.core.face_detector import FaceAnalyzerUnavailable, InsightFaceAnalyzer
from lf_quickid.core.image_scanner import scan_images
from lf_quickid.core.models import FaceGroup
from lf_quickid.ui.theme import build_hero, field_label, section_title


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
            self.signals.finished.emit(groups)
        except FaceAnalyzerUnavailable as exc:
            self.signals.failed.emit(str(exc))
        except Exception as exc:
            self.signals.failed.emit(f"处理失败: {exc}")


class FaceGroupPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._thread_pool = QThreadPool.globalInstance()
        self._groups_layout: QGridLayout | None = None

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
        result_layout.addWidget(section_title("识别结果"))

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.results = QWidget()
        self._groups_layout = QGridLayout(self.results)
        self._groups_layout.setContentsMargins(0, 0, 0, 0)
        self._groups_layout.setSpacing(14)
        self.scroll.setWidget(self.results)
        result_layout.addWidget(self.scroll, 1)

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
        self.path_edit.textChanged.connect(lambda text: self.start_button.setEnabled(bool(text.strip())))
        self.setStyleSheet(_stylesheet())

    def _choose_directory(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "选择照片目录")
        if directory:
            self.path_edit.setText(directory)

    def _start(self) -> None:
        directory = Path(self.path_edit.text()).expanduser()
        if not directory.is_dir():
            QMessageBox.warning(self, "目录无效", "请选择一个有效的照片目录。")
            return

        self._clear_results()
        self.log.clear()
        self.progress.setValue(0)
        self.status.setText("准备处理...")
        self.browse_button.setEnabled(False)
        self.start_button.setEnabled(False)

        worker = FaceGroupingWorker(directory)
        worker.signals.progress.connect(self._on_progress)
        worker.signals.log.connect(self._append_log)
        worker.signals.finished.connect(self._on_finished)
        worker.signals.failed.connect(self._on_failed)
        self._thread_pool.start(worker)

    def _on_progress(self, index: int, total: int, filename: str) -> None:
        self.progress.setMaximum(total)
        self.progress.setValue(index)
        self.status.setText(f"正在处理 {index}/{total}: {filename}")

    def _append_log(self, message: str) -> None:
        self.log.append(message)

    def _on_finished(self, groups: list[FaceGroup]) -> None:
        self.browse_button.setEnabled(True)
        self.start_button.setEnabled(True)

        if not groups:
            self.status.setText("未找到可分组的人脸。")
            self._append_empty_state("未检测到人脸或目录中没有支持的图片。")
            return

        self.status.setText(f"完成：识别出 {sum(len(group.faces) for group in groups)} 张人脸，聚为 {len(groups)} 组。")
        self._render_groups(groups)

    def _on_failed(self, message: str) -> None:
        self.browse_button.setEnabled(True)
        self.start_button.setEnabled(True)
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
        label = QLabel(text)
        label.setAlignment(Qt.AlignCenter)
        label.setObjectName("emptyState")
        label.setWordWrap(True)
        self._groups_layout.addWidget(label, 0, 0)

    def _render_groups(self, groups: list[FaceGroup]) -> None:
        self._clear_results()
        columns = 3
        for index, group in enumerate(groups):
            card = _GroupCard(group)
            self._groups_layout.addWidget(card, index // columns, index % columns)
        self._groups_layout.setRowStretch((len(groups) + columns - 1) // columns, 1)


class _GroupCard(QFrame):
    def __init__(self, group: FaceGroup) -> None:
        super().__init__()
        self.setObjectName("groupCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(9)

        preview = QLabel()
        preview.setObjectName("facePreview")
        preview.setFixedHeight(154)
        preview.setAlignment(Qt.AlignCenter)

        thumbnail = group.faces[0].thumbnail_jpeg if group.faces else None
        if thumbnail:
            pixmap = QPixmap()
            pixmap.loadFromData(thumbnail, "JPEG")
            preview.setPixmap(pixmap.scaled(150, 150, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            preview.setText("无预览")

        title = QLabel(group.label)
        title.setObjectName("groupTitle")
        count = QLabel(f"出现 {len(group.faces)} 次 · 涉及 {group.image_count} 张照片")
        count.setObjectName("groupMeta")

        paths = QLabel("\n".join(str(face.image_path.name) for face in group.faces[:5]))
        if len(group.faces) > 5:
            paths.setText(paths.text() + f"\n... 还有 {len(group.faces) - 5} 条")
        paths.setObjectName("groupPaths")
        paths.setWordWrap(True)

        layout.addWidget(preview)
        layout.addWidget(title)
        layout.addWidget(count)
        layout.addWidget(paths)


def _stylesheet() -> str:
    return """
        #groupCard {
            min-width: 220px;
        }
        #facePreview {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #eff6ff, stop:1 #f8fafc);
            border: 1px solid #dbeafe;
            border-radius: 16px;
            color: #94a3b8;
        }
        #groupTitle {
            font-size: 17px;
            font-weight: 850;
            color: #101828;
        }
        #groupMeta {
            color: #2563eb;
            font-weight: 750;
        }
        #emptyState {
            color: #667085;
            padding: 80px;
        }
    """
