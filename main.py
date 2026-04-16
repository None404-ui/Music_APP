import os
import sys

from PyQt6.QtWidgets import QApplication, QDialog
from ui.windows.main_window import MainWindow
from ui.windows.auth_dialog import AuthDialog
from backend.remember_login import try_session_from_saved
from ui.retro_font import register_retro_font, inject_font_into_qss

_QSS_FILES = [
    "buttons",
    "popular",
    "reviews",
    "search",
    "selected",
    "player",
    "auth",
    "review_dialog",
    "settings",  # последним — стили вкладки «Настройки» не перебиваются
]


def load_stylesheets() -> str:
    base = os.path.join(os.path.dirname(__file__), "ui", "styles")
    combined = ""
    for name in _QSS_FILES:
        path = os.path.join(base, f"{name}.qss")
        with open(path, "r", encoding="utf-8") as f:
            combined += f.read() + "\n"
    return combined


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("CRATES")
    family = register_retro_font()
    app.setStyleSheet(inject_font_into_qss(load_stylesheets(), family))

    while True:
        session = try_session_from_saved()
        if session is None:
            auth = AuthDialog()
            if auth.exec() != QDialog.DialogCode.Accepted or auth.session is None:
                sys.exit(0)
            session = auth.session

        window = MainWindow(session)
        window.show()
        app.exec()

        if not window.consume_logout_restart():
            break

    sys.exit(0)


if __name__ == "__main__":
    main()
