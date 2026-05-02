from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMainWindow, QStackedWidget, QVBoxLayout, QWidget

from lf_quickid.ui.background_replace_page import BackgroundReplacePage
from lf_quickid.ui.face_group_page import FaceGroupPage
from lf_quickid.ui.id_photo_page import IdPhotoPage


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("LF QuickID - 照片批量处理")

        root = QWidget()
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(220)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(18, 22, 18, 18)
        sidebar_layout.setSpacing(16)

        brand = QFrame()
        brand.setObjectName("brand")
        brand_layout = QVBoxLayout(brand)
        brand_layout.setContentsMargins(14, 14, 14, 14)
        brand_layout.setSpacing(4)

        title = QLabel("LF QuickID")
        title.setObjectName("appTitle")
        subtitle = QLabel("照片批量处理工具集")
        subtitle.setObjectName("appSubtitle")
        brand_layout.addWidget(title)
        brand_layout.addWidget(subtitle)

        nav = QListWidget()
        nav.setObjectName("nav")
        nav.addItem(QListWidgetItem("人脸分组"))
        nav.addItem(QListWidgetItem("证件照换背景"))
        nav.addItem(QListWidgetItem("证件照裁切"))
        nav.setCurrentRow(0)
        nav.setFocusPolicy(Qt.NoFocus)

        sidebar_layout.addWidget(brand)
        sidebar_layout.addSpacing(10)
        sidebar_layout.addWidget(nav)
        sidebar_layout.addStretch()

        stack = QStackedWidget()
        stack.addWidget(FaceGroupPage())
        stack.addWidget(BackgroundReplacePage())
        stack.addWidget(IdPhotoPage())
        nav.currentRowChanged.connect(stack.setCurrentIndex)

        layout.addWidget(sidebar)
        layout.addWidget(stack, 1)
        self.setCentralWidget(root)
        self.setStyleSheet(_stylesheet())


def _stylesheet() -> str:
    return """
        QMainWindow, QWidget {
            background: #f5f7fb;
            color: #162033;
            font-size: 14px;
        }
        #sidebar {
            background: #0b1220;
            border-right: 1px solid #111827;
        }
        #brand {
            background: #111c31;
            border: 1px solid #26344f;
            border-radius: 16px;
        }
        #brand QLabel {
            background: transparent;
        }
        #appTitle {
            background: transparent;
            color: #f8fafc;
            font-size: 26px;
            font-weight: 900;
            letter-spacing: 0.4px;
        }
        #appSubtitle {
            background: transparent;
            color: #cbd5e1;
            font-size: 13px;
            font-weight: 500;
        }
        #nav {
            background: transparent;
            border: none;
            color: #d0d5dd;
            outline: none;
        }
        #nav::item {
            padding: 12px 14px;
            border-radius: 10px;
            margin-bottom: 6px;
        }
        #nav::item:selected {
            background: #1d2939;
            color: #ffffff;
        }
        QPushButton {
            background: #2563eb;
            border: none;
            color: #ffffff;
            padding: 10px 16px;
            border-radius: 10px;
            font-weight: 600;
        }
        QPushButton:hover {
            background: #1d4ed8;
        }
        QPushButton:disabled {
            background: #98a2b3;
        }
        QLineEdit, QTextEdit {
            background: #ffffff;
            border: 1px solid #d0d5dd;
            border-radius: 10px;
            padding: 10px;
        }
        QProgressBar {
            border: 1px solid #d0d5dd;
            border-radius: 8px;
            background: #ffffff;
            height: 14px;
            text-align: center;
        }
        QProgressBar::chunk {
            background: #2563eb;
            border-radius: 8px;
        }
    """
