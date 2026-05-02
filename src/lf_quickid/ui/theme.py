from __future__ import annotations

from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout


def app_stylesheet() -> str:
    return """
        QMainWindow, QWidget {
            background: #eef2f7;
            color: #172033;
            font-family: "PingFang SC", "Microsoft YaHei", "Helvetica Neue", Arial, sans-serif;
            font-size: 14px;
        }
        #sidebar {
            background: #0a1020;
            border-right: 1px solid #182235;
        }
        #brand {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #172554, stop:1 #312e81);
            border: 1px solid #334155;
            border-radius: 22px;
        }
        #logoMark {
            background: #ffffff;
            color: #1d4ed8;
            border-radius: 14px;
            font-size: 19px;
            font-weight: 900;
        }
        #appTitle {
            background: transparent;
            color: #f8fafc;
            font-size: 24px;
            font-weight: 900;
            letter-spacing: 0.3px;
        }
        #appSubtitle, #sidebarHint {
            background: transparent;
            color: #bac6d8;
            font-size: 12px;
            line-height: 18px;
        }
        #nav {
            background: transparent;
            border: none;
            color: #cbd5e1;
            outline: none;
        }
        #nav::item {
            padding: 13px 15px;
            border-radius: 13px;
            margin-bottom: 8px;
        }
        #nav::item:hover {
            background: #142033;
            color: #ffffff;
        }
        #nav::item:selected {
            background: #2563eb;
            color: #ffffff;
        }
        #workspace {
            background: #eef2f7;
        }
        #pageTitle {
            background: transparent;
            color: #0f172a;
            font-size: 30px;
            font-weight: 900;
        }
        #pageDescription, #statusText, #fieldHint, #groupPaths {
            background: transparent;
            color: #667085;
        }
        #heroCard, #settingsCard, #inputCard, #resultPanel, #groupCard, #settingGroup {
            background: #ffffff;
            border: 1px solid #dfe7f2;
            border-radius: 20px;
        }
        #heroCard {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #ffffff, stop:1 #eff6ff);
        }
        #inputCard {
            border: 1px dashed #a9b9d0;
        }
        #sectionTitle {
            background: transparent;
            color: #101828;
            font-size: 17px;
            font-weight: 850;
        }
        #fieldLabel {
            background: transparent;
            color: #344054;
            font-size: 13px;
            font-weight: 750;
        }
        #settingGroup {
            background: #f8fafc;
            border-radius: 16px;
        }
        QPushButton {
            background: #2563eb;
            border: none;
            color: #ffffff;
            padding: 10px 16px;
            border-radius: 12px;
            font-weight: 750;
        }
        QPushButton:hover {
            background: #1d4ed8;
        }
        QPushButton:pressed {
            background: #1e40af;
        }
        QPushButton:disabled {
            background: #b9c2d0;
            color: #f8fafc;
        }
        #secondaryButton {
            background: #e8f0ff;
            color: #1d4ed8;
        }
        #secondaryButton:hover {
            background: #dbeafe;
        }
        QLineEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {
            background: #ffffff;
            border: 1px solid #cfd8e6;
            border-radius: 12px;
            padding: 8px 10px;
            selection-background-color: #2563eb;
        }
        QLineEdit:focus, QTextEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
            border: 1px solid #2563eb;
        }
        QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {
            background: #f2f4f7;
            color: #667085;
        }
        QTextEdit {
            color: #475467;
        }
        QProgressBar {
            border: none;
            border-radius: 8px;
            background: #dbe3ef;
            height: 12px;
            text-align: center;
            color: transparent;
        }
        QProgressBar::chunk {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #38bdf8, stop:1 #2563eb);
            border-radius: 8px;
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
