from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS track (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rel_path TEXT NOT NULL UNIQUE,
            title TEXT NOT NULL,
            artist TEXT NOT NULL DEFAULT '',
            mime TEXT,
            size_bytes INTEGER,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    conn.commit()


@contextmanager
def session(conn: sqlite3.Connection) -> Generator[sqlite3.Connection, None, None]:
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def insert_track(
    conn: sqlite3.Connection,
    *,
    rel_path: str,
    title: str,
    artist: str,
    mime: str | None,
    size_bytes: int | None,
) -> int:
    with session(conn):
        cur = conn.execute(
            """
            INSERT INTO track (rel_path, title, artist, mime, size_bytes)
            VALUES (?, ?, ?, ?, ?)
            """,
            (rel_path, title, artist, mime, size_bytes),
        )
        return int(cur.lastrowid)


def list_tracks(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT id, title, artist, mime, size_bytes, created_at FROM track ORDER BY id"
    ).fetchall()
    return [dict(r) for r in rows]


def get_track(conn: sqlite3.Connection, track_id: int) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT id, rel_path, title, artist, mime, size_bytes FROM track WHERE id = ?",
        (track_id,),
    ).fetchone()
    return dict(row) if row else None


def abs_path_for_track(conn: sqlite3.Connection, track_id: int, tracks_root: Path) -> Path | None:
    row = get_track(conn, track_id)
    if not row:
        return None
    p = tracks_root / row["rel_path"]
    return p if p.is_file() else None
