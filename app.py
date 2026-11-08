"""BlockServer GUI (PySide6) desktop entry point."""
from __future__ import annotations
import os
from pathlib import Path
import sys
import traceback

os.environ.setdefault("QT_API", "pyside6")

from PySide6.QtWidgets import QApplication, QMessageBox
from blockserver.ui import MainWindow


def exception_handler(typ, value, tb):
    details = "".join(traceback.format_exception(typ, value, tb))
    try:
        base = Path(os.environ.get("APPDATA", str(Path.home() / ".config"))) / "BlockServerGUI"
        base.mkdir(parents=True, exist_ok=True)
        with (base / "crash.log").open("a", encoding="utf-8") as log:
            log.write(details + "\n")
    except OSError:
        pass
    print(details, file=sys.stderr)
    if QApplication.instance():
        QMessageBox.critical(None, "Error inesperado — BlockServer GUI",
                             f"{value}\n\nSe registró el error en crash.log. Consulta el manual para localizarlo.")


def main():
    sys.excepthook = exception_handler
    app = QApplication(sys.argv)
    app.setApplicationName("BlockServer GUI")
    app.setOrganizationName("BlockServer")
    app.setStyle("Fusion")
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
