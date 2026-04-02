import os
import sqlite3

_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
_DB_NAME = "crates.db"


def get_db_path() -> str:
    os.makedirs(_DATA_DIR, exist_ok=True)
    return os.path.join(_DATA_DIR, _DB_NAME)


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_schema() -> None:
    conn = get_connection()
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash BLOB NOT NULL,
                salt BLOB NOT NULL,
                role TEXT NOT NULL CHECK (role IN ('free', 'premium', 'admin')),
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS tracks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                artist TEXT NOT NULL,
                file_path TEXT,
                duration_sec INTEGER,
                owner_user_id INTEGER REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS user_favorites (
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                track_id INTEGER NOT NULL REFERENCES tracks(id) ON DELETE CASCADE,
                PRIMARY KEY (user_id, track_id)
            );

            CREATE TABLE IF NOT EXISTS user_downloads (
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                track_id INTEGER NOT NULL REFERENCES tracks(id) ON DELETE CASCADE,
                local_path TEXT,
                downloaded_at TEXT NOT NULL,
                PRIMARY KEY (user_id, track_id)
            );

            CREATE INDEX IF NOT EXISTS idx_tracks_owner ON tracks(owner_user_id);
            CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
            """
        )
        conn.commit()
    finally:
        conn.close()


def init_db() -> sqlite3.Connection:
    """Создаёт схему при первом запуске; возвращает соединение для закрытия при выходе."""
    init_schema()
    return get_connection()
