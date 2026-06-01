from __future__ import annotations

import json
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from lf_quickid.ui.main_window import MainWindow


def main() -> int:
    if "--self-test" in sys.argv:
        from lf_quickid.core.packaged_self_test import run_packaged_self_test

        output_dir = _self_test_output_dir(sys.argv)
        report = run_packaged_self_test(output_dir)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["ok"] else 1

    app = QApplication(sys.argv)
    app.setApplicationName("LF QuickID")
    app.setOrganizationName("LF")

    window = MainWindow()
    window.resize(1180, 760)
    window.show()

    return app.exec()


def _self_test_output_dir(args: list[str]) -> Path | None:
    if "--self-test-output" not in args:
        return None
    index = args.index("--self-test-output")
    try:
        return Path(args[index + 1]).expanduser()
    except IndexError as exc:
        raise SystemExit("--self-test-output requires a path") from exc


if __name__ == "__main__":
    raise SystemExit(main())
