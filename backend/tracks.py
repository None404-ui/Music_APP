from datetime import datetime, timezone

from backend.db import get_connection, init_schema


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def add_user_track(
    user_id: int,
    title: str,
    artist: str,
    file_path: str | None = None,
    duration_sec: int | None = None,
) -> int:
    init_schema()
    title = (title or "").strip()
    artist = (artist or "").strip()
    if not title:
        raise ValueError("Укажите название трека.")
    conn = get_connection()
    try:
        cur = conn.execute(
            """
            INSERT INTO tracks (title, artist, file_path, duration_sec, owner_user_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            (title, artist, file_path, duration_sec, user_id),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def list_user_owned_tracks(user_id: int) -> list[dict]:
    init_schema()
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT id, title, artist, file_path, duration_sec, owner_user_id
            FROM tracks
            WHERE owner_user_id = ?
            ORDER BY id DESC
            """,
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def add_favorite(user_id: int, track_id: int) -> None:
    init_schema()
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO user_favorites (user_id, track_id) VALUES (?, ?)",
            (user_id, track_id),
        )
        conn.commit()
    finally:
        conn.close()


def remove_favorite(user_id: int, track_id: int) -> None:
    init_schema()
    conn = get_connection()
    try:
        conn.execute(
            "DELETE FROM user_favorites WHERE user_id = ? AND track_id = ?",
            (user_id, track_id),
        )
        conn.commit()
    finally:
        conn.close()


def list_favorites(user_id: int) -> list[dict]:
    init_schema()
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT t.id, t.title, t.artist, t.file_path, t.duration_sec, t.owner_user_id
            FROM user_favorites uf
            JOIN tracks t ON t.id = uf.track_id
            WHERE uf.user_id = ?
            ORDER BY t.title
            """,
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def mark_downloaded(
    user_id: int,
    track_id: int,
    local_path: str | None = None,
) -> None:
    init_schema()
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO user_downloads (user_id, track_id, local_path, downloaded_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id, track_id) DO UPDATE SET
                local_path = excluded.local_path,
                downloaded_at = excluded.downloaded_at
            """,
            (user_id, track_id, local_path, _now_iso()),
        )
        conn.commit()
    finally:
        conn.close()


def remove_download(user_id: int, track_id: int) -> None:
    init_schema()
    conn = get_connection()
    try:
        conn.execute(
            "DELETE FROM user_downloads WHERE user_id = ? AND track_id = ?",
            (user_id, track_id),
        )
        conn.commit()
    finally:
        conn.close()


def list_downloads(user_id: int) -> list[dict]:
    init_schema()
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT t.id, t.title, t.artist, t.file_path, t.duration_sec, t.owner_user_id,
                   ud.local_path, ud.downloaded_at
            FROM user_downloads ud
            JOIN tracks t ON t.id = ud.track_id
            WHERE ud.user_id = ?
            ORDER BY ud.downloaded_at DESC
            """,
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
