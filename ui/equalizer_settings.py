"""Сохранение положений эквалайзера (QSettings)."""

from __future__ import annotations

import json
from typing import List

from PyQt6.QtCore import QSettings

from ui.audio_eq import BAND_CENTER_HZ, EQ_PRESET_GAINS_DB

_ORG = "CRATES"
_APP = "CRATES"
_KEY_BANDS = "equalizer/band_db_json"
_KEY_PRESET = "equalizer/preset_id"


def _s() -> QSettings:
    return QSettings(QSettings.Scope.UserScope, _ORG, _APP)


def preset_id() -> str:
    v = (_s().value(_KEY_PRESET, "flat", str) or "flat").strip()
    if v == "custom" or v in EQ_PRESET_GAINS_DB:
        return v
    return "flat"


def set_preset_id(preset: str) -> None:
    p = (preset or "flat").strip()
    if p != "custom" and p not in EQ_PRESET_GAINS_DB:
        p = "flat"
    _s().setValue(_KEY_PRESET, p)


def band_gains_db() -> List[float]:
    n = len(BAND_CENTER_HZ)
    raw = _s().value(_KEY_BANDS, "", str)
    if raw and raw.strip():
        try:
            arr = json.loads(raw)
            if isinstance(arr, list) and len(arr) >= n:
                return [max(-12.0, min(12.0, float(arr[i]))) for i in range(n)]
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
    tpl = EQ_PRESET_GAINS_DB.get(preset_id(), EQ_PRESET_GAINS_DB["flat"])
    return list(tpl[:n])


def set_band_gains_db(gains: List[float]) -> None:
    n = len(BAND_CENTER_HZ)
    g = [max(-12.0, min(12.0, float(gains[i]))) for i in range(min(n, len(gains)))]
    while len(g) < n:
        g.append(0.0)
    _s().setValue(_KEY_BANDS, json.dumps(g))
