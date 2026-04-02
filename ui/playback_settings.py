"""Настройки воспроизведения (QSettings), читает плеер и пишет вкладка «настройки»."""

from PyQt6.QtCore import QSettings

_ORG = "CRATES"
_APP = "CRATES"


def _s() -> QSettings:
    return QSettings(QSettings.Scope.UserScope, _ORG, _APP)


def quality_label() -> str:
    return _s().value("playback/quality", "Авто", str)


def set_quality_label(label: str) -> None:
    _s().setValue("playback/quality", label)


def autoplay() -> bool:
    return _s().value("playback/autoplay", False, bool)


def set_autoplay(v: bool) -> None:
    _s().setValue("playback/autoplay", v)


def normalization() -> bool:
    return _s().value("playback/normalization", False, bool)


def set_normalization(v: bool) -> None:
    _s().setValue("playback/normalization", v)


def quality_volume_cap() -> float:
    """Верхняя граница громкости (множитель) в зависимости от «качества»."""
    q = quality_label()
    if q == "Низкое":
        return 0.72
    if q == "Среднее":
        return 0.88
    if q == "Высокое":
        return 1.0
    return 0.95


def normalization_factor() -> float:
    return 0.82 if normalization() else 1.0
