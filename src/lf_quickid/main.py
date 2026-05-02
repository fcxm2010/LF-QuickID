from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from lf_quickid.ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("LF QuickID")
    app.setOrganizationName("LF")

    window = MainWindow()
    window.resize(1180, 760)
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
