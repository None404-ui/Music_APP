"""Снимок очереди плеера для перезапуска окна (смена языка)."""

from __future__ import annotations

import json
from typing import Any, Optional

from PyQt6.QtCore import QSettings

_ORG = "CRATES"
_APP = "CRATES"
_KEY = "session/language_restart_playback_json"


def _s() -> QSettings:
    return QSettings(QSettings.Scope.UserScope, _ORG, _APP)


def save_language_restart_snapshot(payload: dict[str, Any]) -> None:
    _s().setValue(_KEY, json.dumps(payload, ensure_ascii=False, default=str))


def peek_language_restart_snapshot() -> Optional[dict[str, Any]]:
    raw = _s().value(_KEY, "", str)
    if not (raw or "").strip():
        return None
    try:
        obj = json.loads(raw)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        return None


def clear_language_restart_snapshot() -> None:
    _s().remove(_KEY)
