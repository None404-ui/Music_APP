"""Настройки воспроизведения (QSettings), читает плеер и пишет вкладка «настройки»."""

from __future__ import annotations

import json
import re
from typing import Any, Optional

from PyQt6.QtCore import QSettings

_ORG = "CRATES"
_APP = "CRATES"

_QUALITY_KEY = "playback/quality_key"
_LEGACY_QUALITY = "playback/quality"

_QUALITY_AUTO = "auto"
_QUALITY_HIGH = "high"
_QUALITY_MEDIUM = "medium"
_QUALITY_LOW = "low"

QUALITY_CHOICES: list[tuple[str, str]] = [
    (_QUALITY_AUTO, "Авто"),
    (_QUALITY_HIGH, "Высокое"),
    (_QUALITY_MEDIUM, "Среднее"),
    (_QUALITY_LOW, "Низкое"),
]

_LEGACY_LABEL_TO_KEY: dict[str, str] = {
    "Авто": _QUALITY_AUTO,
    "Высокое": _QUALITY_HIGH,
    "Среднее": _QUALITY_MEDIUM,
    "Низкое": _QUALITY_LOW,
}


def _s() -> QSettings:
    return QSettings(QSettings.Scope.UserScope, _ORG, _APP)


def _migrate_legacy_quality() -> None:
    s = _s()
    if s.contains(_QUALITY_KEY):
        return
    label = s.value(_LEGACY_QUALITY, "Авто", str)
    key = _LEGACY_LABEL_TO_KEY.get((label or "").strip(), _QUALITY_AUTO)
    s.setValue(_QUALITY_KEY, key)
    s.remove(_LEGACY_QUALITY)


def quality_key() -> str:
    _migrate_legacy_quality()
    raw = _s().value(_QUALITY_KEY, _QUALITY_AUTO, str)
    if raw in (_QUALITY_AUTO, _QUALITY_HIGH, _QUALITY_MEDIUM, _QUALITY_LOW):
        return raw
    return _QUALITY_AUTO


def set_quality_key(key: str) -> None:
    if key not in (_QUALITY_AUTO, _QUALITY_HIGH, _QUALITY_MEDIUM, _QUALITY_LOW):
        key = _QUALITY_AUTO
    _s().setValue(_QUALITY_KEY, key)


def quality_label() -> str:
    return _key_to_ru_label(quality_key())


def set_quality_label(label: str) -> None:
    k = _LEGACY_LABEL_TO_KEY.get((label or "").strip(), _QUALITY_AUTO)
    set_quality_key(k)


def _key_to_ru_label(key: str) -> str:
    return {
        _QUALITY_AUTO: "Авто",
        _QUALITY_HIGH: "Высокое",
        _QUALITY_MEDIUM: "Среднее",
        _QUALITY_LOW: "Низкое",
    }.get(key, "Авто")


def autoplay() -> bool:
    return _s().value("playback/autoplay", False, bool)


def set_autoplay(v: bool) -> None:
    _s().setValue("playback/autoplay", v)


def normalization() -> bool:
    return _s().value("playback/normalization", False, bool)


def set_normalization(v: bool) -> None:
    _s().setValue("playback/normalization", v)


# Нормализация: множитель к выходной громкости (после ползунка и quality cap).
_DEFAULT_NORM_GAIN_NO_METADATA = 0.82
_NORM_GAIN_MIN = 0.12
_NORM_GAIN_MAX = 1.55


def _parse_meta_dict(item: Optional[dict]) -> dict[str, Any]:
    if not item or not isinstance(item, dict):
        return {}
    m = item.get("meta_json")
    if isinstance(m, dict):
        return m
    if isinstance(m, str) and m.strip():
        try:
            parsed = json.loads(m)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _parse_db_value(v: Any) -> Optional[float]:
    if v is None:
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().lower()
    s = re.sub(r"\s*db\s*$", "", s).strip()
    try:
        return float(s)
    except ValueError:
        return None


def normalization_gain_for_item(item: Optional[dict]) -> float:
    """
    Множитель громкости при включённой нормализации.
    Если в meta_json трека есть ReplayGain (dB), применяется 10^(dB/20) с ограничением.
    Иначе — мягкое снижение по умолчанию (как раньше одна константа 0.82).
    """
    if not normalization():
        return 1.0
    meta = _parse_meta_dict(item)
    for key in (
        "replay_gain_db",
        "replaygain_track_gain_db",
        "replaygain_track_gain",
        "rg_track_db",
    ):
        if key not in meta:
            continue
        db = _parse_db_value(meta.get(key))
        if db is not None:
            g = 10.0 ** (db / 20.0)
            return max(_NORM_GAIN_MIN, min(_NORM_GAIN_MAX, g))
    return _DEFAULT_NORM_GAIN_NO_METADATA


def quality_volume_cap() -> float:
    """Верхняя граница громкости (множитель) в зависимости от «качества»."""
    q = quality_key()
    if q == _QUALITY_LOW:
        return 0.48
    if q == _QUALITY_MEDIUM:
        return 0.72
    if q == _QUALITY_HIGH:
        return 1.0
    return 0.88
