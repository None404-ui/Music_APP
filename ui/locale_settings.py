"""Язык интерфейса (QSettings), тот же org/app, что и воспроизведение."""

from PyQt6.QtCore import QSettings

_ORG = "CRATES"
_APP = "CRATES"

_LANG_RU = "ru"
_LANG_EN = "en"


def _s() -> QSettings:
    return QSettings(QSettings.Scope.UserScope, _ORG, _APP)


def language_code() -> str:
    raw = _s().value("ui/language", _LANG_RU)
    if raw == _LANG_EN:
        return _LANG_EN
    return _LANG_RU


def set_language_code(code: str) -> None:
    c = (code or "").strip().lower()
    if c == _LANG_EN:
        _s().setValue("ui/language", _LANG_EN)
    else:
        _s().setValue("ui/language", _LANG_RU)


def is_english() -> bool:
    return language_code() == _LANG_EN
