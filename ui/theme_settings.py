"""Application theme selection stored per user in QSettings."""

from __future__ import annotations

from PyQt6.QtCore import QSettings

_ORG = "CRATES"
_APP = "CRATES"

RETRO_NEON = "retro_neon"
CLASSIC7 = "classic7"
DEFAULT_THEME = RETRO_NEON
THEME_KEYS = (RETRO_NEON, CLASSIC7)

_THEME_KEY = "ui/theme"
_APP_THEME_KEY = "ui/last_theme"
_APP_THEME_SOURCE_KEY = "ui/last_theme_source"
_scope_prefix = ""


def _s() -> QSettings:
    return QSettings(QSettings.Scope.UserScope, _ORG, _APP)


def set_user_scope(user_id: int | None) -> None:
    global _scope_prefix
    _scope_prefix = f"users/{int(user_id)}/" if user_id else ""


def _key(name: str) -> str:
    return f"{_scope_prefix}{name}"


def normalize_theme_key(key: str | None) -> str:
    raw = (key or "").strip().lower()
    return raw if raw in THEME_KEYS else DEFAULT_THEME


def _valid_theme_key(key: str | None) -> str | None:
    raw = (key or "").strip().lower()
    return raw if raw in THEME_KEYS else None


def theme_key() -> str:
    return normalize_theme_key(_s().value(_key(_THEME_KEY), DEFAULT_THEME, str))


def _theme_key_from_existing_user_settings(s: QSettings) -> str | None:
    found: list[str] = []
    s.beginGroup("users")
    try:
        for user_group in s.childGroups():
            key = _valid_theme_key(s.value(f"{user_group}/{_THEME_KEY}", None, str))
            if key is not None:
                found.append(key)
    finally:
        s.endGroup()
    if CLASSIC7 in found:
        return CLASSIC7
    return found[-1] if found else None


def app_theme_key() -> str:
    s = _s()
    direct = _valid_theme_key(s.value(_APP_THEME_KEY, None, str))
    fallback = _theme_key_from_existing_user_settings(s)
    source = str(s.value(_APP_THEME_SOURCE_KEY, "", str) or "")
    if direct == DEFAULT_THEME and source != "user" and fallback not in (None, DEFAULT_THEME):
        s.setValue(_APP_THEME_KEY, fallback)
        s.sync()
        return fallback
    if direct is not None:
        return direct
    if fallback is not None:
        s.setValue(_APP_THEME_KEY, fallback)
        s.sync()
        return fallback
    return DEFAULT_THEME


def set_app_theme_key(key: str) -> None:
    s = _s()
    s.setValue(_APP_THEME_KEY, normalize_theme_key(key))
    s.sync()


def set_theme_key(key: str) -> None:
    s = _s()
    normalized = normalize_theme_key(key)
    s.setValue(_key(_THEME_KEY), normalized)
    s.setValue(_APP_THEME_KEY, normalized)
    s.setValue(_APP_THEME_SOURCE_KEY, "user")
    s.sync()
