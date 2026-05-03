from __future__ import annotations

from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout


def app_stylesheet() -> str:
    return """
        QMainWindow, QWidget {
            background: #f5f5f7;
            color: #1d1d1f;
            font-family: "-apple-system", "SF Pro Text", "PingFang SC", "Helvetica Neue", Arial, sans-serif;
            font-size: 13px;
        }
        #sidebar {
            background: #ededf2;
            border-right: 1px solid #d8d8de;
        }
        #brand {
            background: transparent;
            border: none;
        }
        #logoMark {
            background: #ffffff;
            color: #007aff;
            border: 1px solid #d1d1d6;
            border-radius: 10px;
            font-size: 17px;
            font-weight: 900;
        }
        #appTitle {
            background: transparent;
            color: #1d1d1f;
            font-size: 20px;
            font-weight: 800;
        }
        #appSubtitle, #sidebarHint {
            background: transparent;
            color: #6e6e73;
            font-size: 12px;
        }
        #nav {
            background: transparent;
            border: none;
            color: #2c2c2e;
            outline: none;
        }
        #nav::item {
            padding: 8px 11px;
            border-radius: 8px;
            margin-bottom: 4px;
        }
        #nav::item:hover {
            background: #e1e1e7;
            color: #1d1d1f;
        }
        #nav::item:selected {
            background: #dcecff;
            color: #0057d9;
            font-weight: 700;
        }
        #workspace {
            background: #f5f5f7;
        }
        #pageTitle {
            background: transparent;
            color: #1d1d1f;
            font-size: 24px;
            font-weight: 800;
        }
        #pageDescription, #statusText, #fieldHint, #groupPaths {
            background: transparent;
            color: #6e6e73;
        }
        #heroCard, #settingsCard, #inputCard, #resultPanel, #groupCard, #settingGroup {
            background: #ffffff;
            border: 1px solid #dcdcde;
            border-radius: 12px;
        }
        #heroCard {
            background: transparent;
            border: none;
        }
        #inputCard {
            border: 1px solid #dcdcde;
        }
        #sectionTitle {
            background: transparent;
            color: #1d1d1f;
            font-size: 15px;
            font-weight: 750;
        }
        #fieldLabel {
            background: transparent;
            color: #3a3a3c;
            font-size: 12px;
            font-weight: 650;
        }
        #settingGroup {
            background: #f9f9fb;
            border-radius: 10px;
        }
        QPushButton {
            background: #007aff;
            border: none;
            color: #ffffff;
            padding: 7px 13px;
            border-radius: 7px;
            font-weight: 650;
        }
        QPushButton:hover {
            background: #0a84ff;
        }
        QPushButton:pressed {
            background: #0060df;
        }
        QPushButton:disabled {
            background: #d1d1d6;
            color: #ffffff;
        }
        #secondaryButton {
            background: #eeeeef;
            color: #1d1d1f;
            border: 1px solid #d1d1d6;
        }
        #secondaryButton:hover {
            background: #e5e5ea;
        }
        QLineEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {
            background: #ffffff;
            border: 1px solid #c7c7cc;
            border-radius: 7px;
            padding: 5px 8px;
            selection-background-color: #007aff;
        }
        QLineEdit:focus, QTextEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
            border: 1px solid #007aff;
        }
        QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {
            background: #f2f2f7;
            color: #8e8e93;
        }
        QTextEdit {
            color: #3a3a3c;
        }
        QProgressBar {
            border: none;
            border-radius: 4px;
            background: #e5e5ea;
            height: 8px;
            text-align: center;
            color: transparent;
        }
        QProgressBar::chunk {
            background: #007aff;
            border-radius: 4px;
        }
        QScrollArea, QScrollArea QWidget {
            background: transparent;
        }
    """


def build_hero(title: str, description: str) -> QFrame:
    hero = QFrame()
    hero.setObjectName("heroCard")
    layout = QVBoxLayout(hero)
    layout.setContentsMargins(22, 20, 22, 20)
    layout.setSpacing(7)

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
