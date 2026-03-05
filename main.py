import sys
import os
from PyQt6.QtWidgets import QApplication
from ui.windows.main_window import MainWindow

_QSS_FILES = [
    "buttons",
    "popular",
    "reviews",
    "search",
    "player",
    "settings",
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
    app.setStyleSheet(load_stylesheets())

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
