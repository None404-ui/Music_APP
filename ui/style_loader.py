"""QSS loading and theme overlay application."""

from __future__ import annotations

import os

from PyQt6.QtWidgets import QApplication

from ui import theme_settings
from ui.retro_font import inject_font_into_qss

QSS_FILES = [
    "buttons",
    "popular",
    "reviews",
    "search",
    "selected",
    "player",
    "auth",
    "review_dialog",
    "player_appearance",
    "settings",
    "scrollbars",
]

THEME_QSS_FILES = [
    "buttons",
    "popular",
    "reviews",
    "search",
    "selected",
    "auth",
    "review_dialog",
    "player_appearance",
    "settings",
    "scrollbars",
]


def _read_qss(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def load_stylesheets(theme_key: str | None = None) -> str:
    base = os.path.join(os.path.dirname(__file__), "styles")
    combined = []
    for name in QSS_FILES:
        combined.append(_read_qss(os.path.join(base, f"{name}.qss")))

    theme = theme_settings.normalize_theme_key(theme_key)
    if theme != theme_settings.DEFAULT_THEME:
        theme_dir = os.path.join(base, "themes", theme)
        for name in THEME_QSS_FILES:
            path = os.path.join(theme_dir, f"{name}.qss")
            if os.path.isfile(path):
                combined.append(_read_qss(path))
    return "\n".join(combined) + "\n"


def build_app_stylesheet(font_family: str, theme_key: str | None = None) -> str:
    return inject_font_into_qss(load_stylesheets(theme_key), font_family)


def apply_app_stylesheet(
    app: QApplication | None,
    font_family: str,
    theme_key: str | None = None,
) -> None:
    if app is None:
        return
    app.setStyleSheet(build_app_stylesheet(font_family, theme_key))
