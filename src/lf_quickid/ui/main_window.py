from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMainWindow, QStackedWidget, QVBoxLayout, QWidget

from lf_quickid.ui.background_replace_page import BackgroundReplacePage
from lf_quickid.ui.face_group_page import FaceGroupPage
from lf_quickid.ui.id_photo_page import IdPhotoPage
from lf_quickid.ui.theme import app_stylesheet


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("LF QuickID - 照片批量处理")
        self.resize(1180, 760)

        root = QWidget()
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(224)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(14, 18, 14, 16)
        sidebar_layout.setSpacing(12)

        brand = QFrame()
        brand.setObjectName("brand")
        brand_layout = QVBoxLayout(brand)
        brand_layout.setContentsMargins(8, 8, 8, 8)
        brand_layout.setSpacing(6)

        logo = QLabel("LF")
        logo.setObjectName("logoMark")
        logo.setFixedSize(34, 34)
        logo.setAlignment(Qt.AlignCenter)

        title = QLabel("LF QuickID")
        title.setObjectName("appTitle")
        subtitle = QLabel("本地照片批量处理工作台")
        subtitle.setObjectName("appSubtitle")
        subtitle.setWordWrap(True)
        brand_layout.addWidget(logo)
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
        sidebar_layout.addSpacing(6)
        sidebar_layout.addWidget(nav)
        sidebar_layout.addStretch()

        hint = QLabel("照片只在本机处理\n适合批量整理、证件照交付和快速复核")
        hint.setObjectName("sidebarHint")
        hint.setWordWrap(True)
        sidebar_layout.addWidget(hint)

        stack = QStackedWidget()
        stack.setObjectName("workspace")
        stack.addWidget(FaceGroupPage())
        stack.addWidget(BackgroundReplacePage())
        stack.addWidget(IdPhotoPage())
        nav.currentRowChanged.connect(stack.setCurrentIndex)

        layout.addWidget(sidebar)
        layout.addWidget(stack, 1)
        self.setCentralWidget(root)
        self.setStyleSheet(app_stylesheet())
