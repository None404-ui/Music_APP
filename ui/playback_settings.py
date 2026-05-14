"""Настройки воспроизведения (QSettings), читает плеер и пишет вкладка «настройки»."""

from __future__ import annotations

import json
import re
from typing import Any, Optional
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from PyQt6.QtCore import QSettings

_ORG = "CRATES"
_APP = "CRATES"

_QUALITY_KEY = "playback/quality_key"
_LEGACY_QUALITY = "playback/quality"
_scope_prefix = ""

# Устаревшее значение «auto» в QSettings мигрируется в high при чтении.
_QUALITY_AUTO = "auto"
_QUALITY_HIGH = "high"
_QUALITY_MEDIUM = "medium"
_QUALITY_LOW = "low"

_QUALITY_KEYS_ORDERED = (_QUALITY_HIGH, _QUALITY_MEDIUM, _QUALITY_LOW)

QUALITY_CHOICES: list[tuple[str, str]] = [
    (_QUALITY_HIGH, "Высокое"),
    (_QUALITY_MEDIUM, "Среднее"),
    (_QUALITY_LOW, "Низкое"),
]

_LEGACY_LABEL_TO_KEY: dict[str, str] = {
    "Авто": _QUALITY_HIGH,
    "Высокое": _QUALITY_HIGH,
    "Среднее": _QUALITY_MEDIUM,
    "Низкое": _QUALITY_LOW,
}

# Параметр URL, который понимают Django serve_media и LAN Hub (перекодирование в MP3).
STREAM_QUALITY_QUERY_PARAM = "crates_abr"
_BITRATE_LOW_KBPS = 128
_BITRATE_MEDIUM_KBPS = 192


def _s() -> QSettings:
    return QSettings(QSettings.Scope.UserScope, _ORG, _APP)


def set_user_scope(user_id: int | None) -> None:
    global _scope_prefix
    _scope_prefix = f"users/{int(user_id)}/" if user_id else ""


def _key(name: str) -> str:
    return f"{_scope_prefix}{name}"


def _migrate_legacy_quality() -> None:
    s = _s()
    if s.contains(_key(_QUALITY_KEY)):
        return
    label = s.value(_LEGACY_QUALITY, "Высокое", str)
    key = _LEGACY_LABEL_TO_KEY.get((label or "").strip(), _QUALITY_HIGH)
    s.setValue(_key(_QUALITY_KEY), key)


def _migrate_stored_auto_to_high() -> None:
    raw = _s().value(_key(_QUALITY_KEY), "", str)
    if raw == _QUALITY_AUTO:
        _s().setValue(_key(_QUALITY_KEY), _QUALITY_HIGH)


def quality_key() -> str:
    _migrate_legacy_quality()
    _migrate_stored_auto_to_high()
    raw = _s().value(_key(_QUALITY_KEY), _QUALITY_HIGH, str)
    if raw in _QUALITY_KEYS_ORDERED:
        return raw
    return _QUALITY_HIGH


def set_quality_key(key: str) -> None:
    if key not in _QUALITY_KEYS_ORDERED:
        key = _QUALITY_HIGH
    _s().setValue(_key(_QUALITY_KEY), key)


def quality_label() -> str:
    return _key_to_ru_label(quality_key())


def set_quality_label(label: str) -> None:
    k = _LEGACY_LABEL_TO_KEY.get((label or "").strip(), _QUALITY_HIGH)
    set_quality_key(k)


def _key_to_ru_label(key: str) -> str:
    return {
        _QUALITY_HIGH: "Высокое",
        _QUALITY_MEDIUM: "Среднее",
        _QUALITY_LOW: "Низкое",
    }.get(key, "Высокое")


def stream_quality_signature() -> str:
    """Метка для перезагрузки источника при смене качества."""
    b = stream_reencode_bitrate_kbps()
    return str(b) if b is not None else "orig"


def stream_reencode_bitrate_kbps() -> int | None:
    """Целевой битрейт перекодированного MP3 или None = оригинальный файл."""
    q = quality_key()
    if q == _QUALITY_LOW:
        return _BITRATE_LOW_KBPS
    if q == _QUALITY_MEDIUM:
        return _BITRATE_MEDIUM_KBPS
    return None


def append_stream_quality_query(url: str) -> str:
    """Для http(s) добавляет или снимает crates_abr в соответствии с настройкой качества."""
    u = (url or "").strip()
    if not u:
        return ""
    low = u.lower()
    if not low.startswith(("http://", "https://")):
        return u
    br = stream_reencode_bitrate_kbps()
    parsed = urlparse(u)
    pairs = [
        (k, v)
        for k, v in parse_qsl(parsed.query, keep_blank_values=True)
        if k != STREAM_QUALITY_QUERY_PARAM
    ]
    if br is not None:
        pairs.append((STREAM_QUALITY_QUERY_PARAM, str(int(br))))
    new_q = urlencode(pairs)
    return urlunparse(parsed._replace(query=new_q))


def autoplay() -> bool:
    return _s().value(_key("playback/autoplay"), False, bool)


def set_autoplay(v: bool) -> None:
    _s().setValue(_key("playback/autoplay"), v)


def normalization() -> bool:
    return _s().value(_key("playback/normalization"), False, bool)


def set_normalization(v: bool) -> None:
    _s().setValue(_key("playback/normalization"), v)


# Нормализация: множитель к выходной громкости (после ползунка).
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
