"""
«Запомнить меня»: email + пароль в QSettings, пароль XOR на ключе от имени ПК.
Не криптостойко, но лучше открытого текста; для локального десктоп-приложения приемлемо.
"""

from __future__ import annotations

import base64
import hashlib
import socket

from PyQt6.QtCore import QSettings

from backend.api_client import CratesApiClient, api_login, build_user_session
from backend.session import UserSession

_ORG = "CRATES"
_APP = "CRATES"
_KEY_MATERIAL = b"CRATES-remember-login-v1"


def _settings() -> QSettings:
    return QSettings(QSettings.Scope.UserScope, _ORG, _APP)


def _machine_key() -> bytes:
    host = (socket.gethostname() or "localhost").encode("utf-8", errors="replace")
    return hashlib.sha256(_KEY_MATERIAL + host).digest()


def _xor(data: bytes, key: bytes) -> bytes:
    return bytes(b ^ key[i % len(key)] for i, b in enumerate(data))


def _encrypt_password(plain: str) -> str:
    enc = _xor(plain.encode("utf-8"), _machine_key())
    return base64.urlsafe_b64encode(enc).decode("ascii")


def _decrypt_password(blob: str) -> str:
    raw = base64.urlsafe_b64decode(blob.encode("ascii"))
    return _xor(raw, _machine_key()).decode("utf-8")


def save_remembered(email: str, password: str) -> None:
    s = _settings()
    s.setValue("remember_me", True)
    s.setValue("email", email.strip().lower())
    s.setValue("password_enc", _encrypt_password(password))
    s.sync()


def clear_remembered() -> None:
    s = _settings()
    s.remove("remember_me")
    s.remove("email")
    s.remove("password_enc")
    s.sync()


def load_remembered_credentials() -> tuple[str, str] | None:
    s = _settings()
    if not s.value("remember_me", False, type=bool):
        return None
    email = (s.value("email", "", type=str) or "").strip().lower()
    enc = s.value("password_enc", "", type=str) or ""
    if not email or not enc:
        return None
    try:
        password = _decrypt_password(enc)
    except Exception:
        clear_remembered()
        return None
    return email, password


def try_session_from_saved() -> UserSession | None:
    """Если включено «запомнить» и логин успешен — сессия без диалога."""
    creds = load_remembered_credentials()
    if creds is None:
        return None
    email, password = creds
    client = CratesApiClient()
    ok, _ = api_login(client, email, password)
    if not ok:
        clear_remembered()
        return None
    session = build_user_session(client, email)
    if session is None:
        clear_remembered()
        return None
    return session


def is_remember_me_enabled() -> bool:
    return _settings().value("remember_me", False, type=bool)
