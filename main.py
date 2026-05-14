import sys

from PyQt6.QtWidgets import QApplication, QDialog

from backend.remember_login import try_session_from_saved
from ui import theme_settings
from ui.retro_font import register_retro_font
from ui.style_loader import apply_app_stylesheet
from ui.windows.auth_dialog import AuthDialog
from ui.windows.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("CRATES")
    family = register_retro_font()
    app.setProperty("retroFontFamily", family)
    apply_app_stylesheet(app, family, theme_settings.app_theme_key())

    session = None
    while True:
        if session is None:
            theme_settings.set_user_scope(None)
            apply_app_stylesheet(app, family, theme_settings.app_theme_key())
            session = try_session_from_saved()
            if session is None:
                auth = AuthDialog()
                if auth.exec() != QDialog.DialogCode.Accepted or auth.session is None:
                    sys.exit(0)
                session = auth.session

        window = MainWindow(session)
        window.show()
        app.exec()

        if window.consume_logout_restart():
            session = None
            continue
        if window.consume_language_restart():
            continue
        break

    sys.exit(0)


if __name__ == "__main__":
    main()
