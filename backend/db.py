"""
Local SQLite DB runner for the project (used by the desktop app entrypoint).

It can apply SQL migrations from `backend/migrations/*.sql` into the local DB file.

Note: Django backend itself uses ORM-managed migrations; this file is for the
non-Django desktop client / early prototype compatibility.
"""

import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union


@dataclass(frozen=True)
class DbConfig:
    path: Path


def default_db_path(app_name: str = "crates") -> Path:
    """
    Returns a per-user DB path.
    macOS/Linux: ~/.<app_name>/<app_name>.db
    Windows: %APPDATA%\\<app_name>\\<app_name>.db (best-effort)
    """
    env = os.getenv("CRATES_DB_PATH")
    if env:
        return Path(env).expanduser()

    if os.name == "nt":
        base = os.getenv("APPDATA") or str(Path.home())
        root = Path(base) / app_name
    else:
        root = Path.home() / f".{app_name}"

    return root / f"{app_name}.db"


def connect(cfg: DbConfig) -> sqlite3.Connection:
    cfg.path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(cfg.path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    return conn


def _ensure_schema_migrations(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        """
    )


def _migrations_dir() -> Path:
    return Path(__file__).resolve().parent / "migrations"


def _list_migration_files() -> list[tuple[int, Path]]:
    migrations = []
    for p in sorted(_migrations_dir().glob("*.sql")):
        # File name format: 0001_name.sql
        try:
            version = int(p.stem.split("_", 1)[0])
        except Exception:
            continue
        migrations.append((version, p))
    migrations.sort(key=lambda t: t[0])
    return migrations


def _applied_versions(conn: sqlite3.Connection) -> set[int]:
    _ensure_schema_migrations(conn)
    rows = conn.execute("SELECT version FROM schema_migrations;").fetchall()
    return {int(r["version"]) for r in rows}


def apply_migrations(conn: sqlite3.Connection) -> None:
    """
    Applies all pending migrations in a single transaction.
    Migrations are plain SQL files in backend/migrations.
    """
    _ensure_schema_migrations(conn)
    applied = _applied_versions(conn)
    migrations = _list_migration_files()

    pending = [(v, p) for (v, p) in migrations if v not in applied]
    if not pending:
        return

    with conn:
        for version, path in pending:
            sql = path.read_text(encoding="utf-8")
            conn.executescript(sql)
            conn.execute("INSERT INTO schema_migrations(version) VALUES (?);", (version,))


def init_db(path: Optional[Union[str, Path]] = None) -> sqlite3.Connection:
    cfg = DbConfig(path=Path(path) if path else default_db_path())
    conn = connect(cfg)
    apply_migrations(conn)
    return conn

