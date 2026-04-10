"""Длительность трека из ответа API (duration_sec + запасной разбор meta_json)."""

from __future__ import annotations

import json
from typing import Any, Optional


def effective_duration_sec(item: dict) -> Optional[int]:
    """
    Секунды длительности: поле duration_sec с сервера, иначе типичные ключи в meta_json.
    """
    if not isinstance(item, dict):
        return None

    raw = item.get("duration_sec")
    if raw is not None and raw != "":
        try:
            v = int(float(raw))
            if v > 0:
                return v
        except (TypeError, ValueError):
            pass

    meta = item.get("meta_json")
    j: dict[str, Any] | None = None
    if isinstance(meta, str) and meta.strip():
        try:
            parsed = json.loads(meta)
            if isinstance(parsed, dict):
                j = parsed
        except json.JSONDecodeError:
            pass
    elif isinstance(meta, dict):
        j = meta
    if not j:
        return None

    for key in ("duration_sec", "length_seconds", "duration"):
        if key not in j or j[key] is None or j[key] == "":
            continue
        try:
            v = int(float(j[key]))
            if v > 0:
                return v
        except (TypeError, ValueError):
            pass

    dm = j.get("duration_ms")
    if dm is not None and dm != "":
        try:
            v = int(float(dm) // 1000)
            if v > 0:
                return v
        except (TypeError, ValueError):
            pass

    return None


def format_duration_mm_ss(sec: Optional[int]) -> str:
    if sec is None or sec <= 0:
        return "—"
    m, s = divmod(int(sec), 60)
    return f"{m:d}:{s:02d}"
