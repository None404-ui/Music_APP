"""
HTTP-клиент для PyQt: session-cookie от Django DRF (логин/регистрация и защищённые GET).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from http.cookiejar import CookieJar
from typing import Any
from urllib.error import HTTPError
from urllib.request import HTTPCookieProcessor, HTTPRedirectHandler, Request, build_opener


def default_backend_url() -> str:
    return os.getenv("CRATES_BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")


@dataclass
class CratesApiClient:
    base_url: str = ""
    _jar: CookieJar | None = None
    _opener: Any = None

    def __post_init__(self) -> None:
        if not self.base_url:
            self.base_url = default_backend_url()
        self._jar = CookieJar()
        self._opener = build_opener(
            HTTPCookieProcessor(self._jar),
            HTTPRedirectHandler(),
        )

    def request_json(
        self,
        method: str,
        path: str,
        body: dict | None = None,
        timeout: float = 20.0,
    ) -> tuple[int, Any]:
        url = f"{self.base_url}{path}"
        data = None if body is None else json.dumps(body).encode("utf-8")
        headers = {"Accept": "application/json"}
        if data is not None:
            headers["Content-Type"] = "application/json"
        req = Request(url, data=data, method=method.upper(), headers=headers)
        try:
            with self._opener.open(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8")
                if not raw:
                    return resp.status, None
                try:
                    return resp.status, json.loads(raw)
                except json.JSONDecodeError:
                    snippet = (raw[:240] + "…") if len(raw) > 240 else raw
                    return resp.status, {"detail": f"Ответ не JSON: {snippet}"}
        except HTTPError as e:
            raw = e.read().decode("utf-8")
            try:
                parsed = json.loads(raw) if raw else None
            except json.JSONDecodeError:
                parsed = {"detail": raw or str(e)}
            return e.code, parsed

    def post_json(self, path: str, body: dict, timeout: float = 20.0) -> tuple[int, Any]:
        return self.request_json("POST", path, body, timeout=timeout)

    def get_json(self, path: str, timeout: float = 20.0) -> tuple[int, Any]:
        return self.request_json("GET", path, None, timeout=timeout)


def api_login(client: CratesApiClient, email: str, password: str) -> tuple[bool, str | None]:
    username = (email or "").strip().lower()
    status, body = client.post_json(
        "/api/auth/login/",
        {"username": username, "password": password},
    )
    if status == 200:
        return True, None
    detail = (body or {}).get("detail", "Ошибка входа")
    return False, str(detail)


def api_logout(client: CratesApiClient) -> None:
    """Сбрасывает session cookie на сервере (игнорируем код ответа)."""
    client.post_json("/api/auth/logout/", {})


def api_register(client: CratesApiClient, email: str, password: str) -> tuple[bool, str | None]:
    status, body = client.post_json(
        "/api/auth/register/",
        {"email": (email or "").strip().lower(), "password": password},
    )
    if status in (200, 201):
        return True, None
    detail = (body or {}).get("detail", "Ошибка регистрации")
    return False, str(detail)


def build_user_session(client: CratesApiClient, email: str) -> "UserSession | None":
    from backend.session import UserSession

    status, prof = client.get_json("/api/profile/me/")
    if status != 200 or not isinstance(prof, dict):
        return None
    uid = prof.get("user")
    if uid is None:
        return None
    role = "premium" if prof.get("is_premium") else "free"
    return UserSession(user_id=int(uid), email=email.strip().lower(), role=role, client=client)
