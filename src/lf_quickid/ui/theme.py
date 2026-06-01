from __future__ import annotations

from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout


def app_stylesheet() -> str:
    return """
        QMainWindow, QWidget {
            background: #f6f7f9;
            color: #20242a;
            font-family: "SF Pro Text", "PingFang SC", "Helvetica Neue", Arial, sans-serif;
            font-size: 13px;
        }
        #sidebar {
            background: #eef1f5;
            border-right: 1px solid #d8dee8;
        }
        #brand {
            background: #ffffff;
            border: 1px solid #dfe5ee;
            border-radius: 12px;
        }
        #logoMark {
            background: #111827;
            color: #ffffff;
            border: 1px solid #111827;
            border-radius: 9px;
            font-size: 17px;
            font-weight: 900;
        }
        #appTitle {
            background: transparent;
            color: #111827;
            font-size: 19px;
            font-weight: 800;
        }
        #appSubtitle {
            background: transparent;
            color: #667085;
            font-size: 12px;
        }
        #sidebarSectionLabel {
            background: transparent;
            color: #7b8494;
            font-size: 11px;
            font-weight: 750;
        }
        #sidebarHint {
            background: #ffffff;
            color: #4b5565;
            border: 1px solid #dfe5ee;
            border-radius: 10px;
            padding: 10px 11px;
            font-size: 12px;
        }
        #nav {
            background: transparent;
            border: none;
            color: #344054;
            outline: none;
        }
        #nav::item {
            padding: 9px 11px;
            border-radius: 8px;
            margin-bottom: 5px;
        }
        #nav::item:hover {
            background: #e3e8ef;
            color: #111827;
        }
        #nav::item:selected {
            background: #ffffff;
            color: #1d4f91;
            font-weight: 700;
            border: 1px solid #d7e3f6;
        }
        #workspace {
            background: #f6f7f9;
        }
        #pageTitle {
            background: transparent;
            color: #111827;
            font-size: 26px;
            font-weight: 800;
        }
        #pageDescription, #statusText, #fieldHint, #groupPaths {
            background: transparent;
            color: #667085;
        }
        #heroCard, #settingsCard, #inputCard, #resultPanel, #groupCard, #settingGroup {
            background: #ffffff;
            border: 1px solid #dfe5ee;
            border-radius: 10px;
        }
        #heroCard {
            background: transparent;
            border: none;
        }
        #inputCard {
            border: 1px solid #dfe5ee;
        }
        #sectionTitle {
            background: transparent;
            color: #111827;
            font-size: 15px;
            font-weight: 750;
        }
        #fieldLabel {
            background: transparent;
            color: #344054;
            font-size: 12px;
            font-weight: 650;
        }
        #settingGroup {
            background: #f8fafc;
            border-radius: 9px;
        }
        QPushButton {
            background: #1d4f91;
            border: 1px solid #1d4f91;
            color: #ffffff;
            padding: 8px 14px;
            border-radius: 6px;
            font-weight: 650;
        }
        QPushButton:hover {
            background: #245ea8;
            border-color: #245ea8;
        }
        QPushButton:pressed {
            background: #173f74;
            border-color: #173f74;
        }
        QPushButton:disabled {
            background: #e4e7ec;
            border-color: #e4e7ec;
            color: #98a2b3;
        }
        QPushButton:focus {
            border: 1px solid #0f62c4;
        }
        #secondaryButton {
            background: #ffffff;
            color: #20242a;
            border: 1px solid #cfd6e2;
        }
        #secondaryButton:hover {
            background: #f2f5f9;
            border-color: #b8c2d1;
        }
        #secondaryButton:pressed {
            background: #e7ecf3;
        }
        QLineEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {
            background: #ffffff;
            border: 1px solid #cfd6e2;
            border-radius: 6px;
            padding: 6px 9px;
            selection-background-color: #1d4f91;
        }
        QComboBox {
            padding-right: 24px;
        }
        QComboBox::drop-down {
            width: 24px;
            border: none;
        }
        QComboBox QAbstractItemView {
            background: #ffffff;
            border: 1px solid #cfd6e2;
            border-radius: 6px;
            selection-background-color: #eef5ff;
            selection-color: #1d4f91;
            padding: 4px;
            outline: none;
        }
        QLineEdit:focus, QTextEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
            border: 1px solid #1d4f91;
        }
        QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {
            background: #f1f4f8;
            color: #98a2b3;
        }
        QTextEdit {
            color: #344054;
        }
        QTextEdit[readOnly="true"] {
            background: #fbfcfe;
        }
        QCheckBox {
            background: transparent;
            color: #344054;
            spacing: 8px;
        }
        QCheckBox::indicator {
            width: 16px;
            height: 16px;
            border: 1px solid #b8c2d1;
            border-radius: 4px;
            background: #ffffff;
        }
        QCheckBox::indicator:hover {
            border-color: #1d4f91;
        }
        QCheckBox::indicator:checked {
            background: #1d4f91;
            border-color: #1d4f91;
        }
        QProgressBar {
            border: none;
            border-radius: 4px;
            background: #e4e7ec;
            height: 8px;
            text-align: center;
            color: transparent;
        }
        QProgressBar::chunk {
            background: #1d4f91;
            border-radius: 4px;
        }
        QScrollArea, QScrollArea QWidget {
            background: transparent;
        }
        QScrollBar:vertical {
            background: transparent;
            width: 10px;
            margin: 4px 0 4px 0;
        }
        QScrollBar::handle:vertical {
            background: #c9d2df;
            border-radius: 5px;
            min-height: 34px;
        }
        QScrollBar::handle:vertical:hover {
            background: #aeb9c8;
        }
        QScrollBar::add-line:vertical,
        QScrollBar::sub-line:vertical,
        QScrollBar::add-page:vertical,
        QScrollBar::sub-page:vertical {
            background: transparent;
            border: none;
            height: 0;
        }
    """


def build_hero(title: str, description: str) -> QFrame:
    hero = QFrame()
    hero.setObjectName("heroCard")
    layout = QVBoxLayout(hero)
    layout.setContentsMargins(4, 2, 4, 8)
    layout.setSpacing(8)

    title_label = QLabel(title)
    title_label.setObjectName("pageTitle")
    description_label = QLabel(description)
    description_label.setObjectName("pageDescription")
    description_label.setWordWrap(True)

    layout.addWidget(title_label)
    layout.addWidget(description_label)
    return hero


def field_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("fieldLabel")
    return label


def section_title(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("sectionTitle")
    return label
