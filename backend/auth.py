import hashlib
import secrets
import sqlite3
from datetime import datetime, timezone

from backend.db import get_connection, init_schema
from backend.session import UserSession

_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1
_SCRYPT_DK_LEN = 32


def _hash_password(password: str, salt: bytes) -> bytes:
    return hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=_SCRYPT_DK_LEN,
    )


def register(email: str, password: str) -> UserSession:
    init_schema()
    email = (email or "").strip().lower()
    if not email or "@" not in email:
        raise ValueError("Укажите корректный email.")
    if len(password) < 6:
        raise ValueError("Пароль не короче 6 символов.")

    salt = secrets.token_bytes(16)
    pw_hash = _hash_password(password, salt)
    now = datetime.now(timezone.utc).isoformat()

    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO users (email, password_hash, salt, role, created_at)
            VALUES (?, ?, ?, 'free', ?)
            """,
            (email, pw_hash, salt, now),
        )
        conn.commit()
        row = conn.execute(
            "SELECT id, email, role FROM users WHERE email = ?",
            (email,),
        ).fetchone()
    except sqlite3.IntegrityError as e:
        conn.rollback()
        raise ValueError("Этот email уже зарегистрирован.") from e
    finally:
        conn.close()

    return UserSession(user_id=row["id"], email=row["email"], role=row["role"])


def login(email: str, password: str) -> UserSession | None:
    init_schema()
    email = (email or "").strip().lower()
    if not email:
        return None

    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, email, role, password_hash, salt FROM users WHERE email = ?",
            (email,),
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        return None
    try:
        check = _hash_password(password, row["salt"])
    except Exception:
        return None
    if not secrets.compare_digest(check, row["password_hash"]):
        return None
    return UserSession(
        user_id=row["id"],
        email=row["email"],
        role=row["role"],
    )
