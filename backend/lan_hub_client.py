"""
HTTP-клиент для LAN Audio Hub (lan_audio_hub): каталог и URL стрима.

Не трогает локальное хранилище и плеер — только запросы к отдельному сервису.
Базовый URL: CRATES_LAN_HUB_URL (например http://192.168.43.5:8765).
"""

from __future__ import annotations

import json
import mimetypes
import os
import secrets
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def default_lan_hub_url() -> str:
    return (os.environ.get("CRATES_LAN_HUB_URL") or "").strip().rstrip("/")


def stream_url(base_url: str, track_id: int) -> str:
    b = (base_url or "").strip().rstrip("/")
    return f"{b}/tracks/{int(track_id)}/stream"


def upload_track(
    base_url: str,
    *,
    filename: str,
    raw_bytes: bytes,
    title: str = "",
    artist: str = "",
    mime_type: str | None = None,
    timeout: float = 120.0,
) -> tuple[int, Any]:
    """
    POST /upload multipart/form-data -> JSON с id/title/artist/stream_url.
    Используется серверной оркестрацией Django: принимает уже прочитанные байты файла.
    """
    b = (base_url or "").strip().rstrip("/")
    if not b:
        return 0, {"detail": "Пустой base_url (задайте CRATES_LAN_HUB_URL)"}
    if not raw_bytes:
        return 0, {"detail": "Пустой файл"}
    boundary = secrets.token_hex(16)
    crlf = "\r\n"
    ct = mime_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"
    chunks: list[bytes] = []
    for key, value in {"title": title, "artist": artist}.items():
        chunks.extend(
            [
                f"--{boundary}{crlf}".encode("utf-8"),
                f'Content-Disposition: form-data; name="{key}"{crlf}{crlf}'.encode("utf-8"),
                str(value or "").encode("utf-8"),
                crlf.encode("utf-8"),
            ]
        )
    chunks.extend(
        [
            f"--{boundary}{crlf}".encode("utf-8"),
            (
                f'Content-Disposition: form-data; name="file"; '
                f'filename="{filename or "track.bin"}"{crlf}'
            ).encode("utf-8"),
            f"Content-Type: {ct}{crlf}{crlf}".encode("utf-8"),
            raw_bytes,
            crlf.encode("utf-8"),
            f"--{boundary}--{crlf}".encode("utf-8"),
        ]
    )
    body = b"".join(chunks)
    req = Request(
        f"{b}/upload",
        data=body,
        method="POST",
        headers={
            "Accept": "application/json",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
    )
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            st = getattr(resp, "status", 200) or 200
            if not raw:
                return st, None
            try:
                return st, json.loads(raw)
            except json.JSONDecodeError:
                return st, {"detail": raw[:240]}
    except HTTPError as e:
        raw = e.read().decode("utf-8")
        try:
            parsed = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            parsed = {"detail": raw or str(e)}
        return e.code, parsed
    except OSError as e:
        return 0, {"detail": str(e)}


def list_tracks(base_url: str, *, timeout: float = 20.0) -> tuple[int, list[dict[str, Any]] | Any]:
    """
    GET /tracks → JSON-массив объектов (id, title, artist, stream_url, ...).
    Возвращает (status, body): при 200 body — list[dict], иначе dict с detail или сырой текст.
    """
    b = (base_url or "").strip().rstrip("/")
    if not b:
        return 0, {"detail": "Пустой base_url (задайте CRATES_LAN_HUB_URL)"}
    url = f"{b}/tracks"
    req = Request(url, method="GET", headers={"Accept": "application/json"})
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            st = getattr(resp, "status", 200) or 200
            if not raw:
                return st, []
            try:
                parsed: Any = json.loads(raw)
            except json.JSONDecodeError:
                return st, {"detail": raw[:240]}
            if st == 200 and isinstance(parsed, list):
                return st, [x for x in parsed if isinstance(x, dict)]
            return st, parsed if isinstance(parsed, dict) else {"detail": str(parsed)}
    except HTTPError as e:
        raw = e.read().decode("utf-8")
        try:
            parsed = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            parsed = {"detail": raw or str(e)}
        return e.code, parsed
    except OSError as e:
        return 0, {"detail": str(e)}


def hub_health(base_url: str, *, timeout: float = 5.0) -> tuple[int, Any]:
    b = (base_url or "").strip().rstrip("/")
    if not b:
        return 0, {"detail": "Пустой base_url"}
    url = f"{b}/health"
    req = Request(url, method="GET", headers={"Accept": "application/json"})
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            st = getattr(resp, "status", 200) or 200
            if not raw:
                return st, None
            try:
                return st, json.loads(raw)
            except json.JSONDecodeError:
                return st, {"detail": raw[:240]}
    except HTTPError as e:
        raw = e.read().decode("utf-8")
        try:
            return e.code, json.loads(raw) if raw else None
        except json.JSONDecodeError:
            return e.code, {"detail": raw or str(e)}
    except OSError as e:
        return 0, {"detail": str(e)}
