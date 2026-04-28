from __future__ import annotations

import mimetypes
import os
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import FileResponse, JSONResponse

from lan_audio_hub import db as hub_db

DEFAULT_DATA = Path(__file__).resolve().parent / "_data"


def _data_dir() -> Path:
    raw = (os.environ.get("LAN_HUB_DATA") or "").strip()
    return Path(raw).expanduser() if raw else DEFAULT_DATA


@asynccontextmanager
async def lifespan(app: FastAPI):
    data = _data_dir()
    tracks = data / "tracks"
    data.mkdir(parents=True, exist_ok=True)
    tracks.mkdir(parents=True, exist_ok=True)
    db_path = data / "index.sqlite"
    conn = hub_db.connect(db_path)
    hub_db.init_schema(conn)
    app.state.hub_conn = conn
    app.state.hub_tracks_dir = tracks
    yield
    conn.close()


app = FastAPI(title="CRATES LAN Audio Hub", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}


@app.get("/tracks")
def list_tracks(request: Request) -> JSONResponse:
    conn = request.app.state.hub_conn
    rows = hub_db.list_tracks(conn)
    base = str(request.base_url).rstrip("/")
    out: list[dict[str, Any]] = []
    for r in rows:
        tid = int(r["id"])
        out.append(
            {
                "id": tid,
                "title": r.get("title") or "",
                "artist": r.get("artist") or "",
                "mime": r.get("mime"),
                "size_bytes": r.get("size_bytes"),
                "created_at": r.get("created_at"),
                "stream_url": f"{base}/tracks/{tid}/stream",
            }
        )
    return JSONResponse(out)


@app.get("/tracks/{track_id}/stream")
def stream_track(track_id: int, request: Request) -> FileResponse:
    conn = request.app.state.hub_conn
    root: Path = request.app.state.hub_tracks_dir
    path = hub_db.abs_path_for_track(conn, track_id, root)
    if path is None:
        raise HTTPException(status_code=404, detail="track not found")
    row = hub_db.get_track(conn, track_id)
    mime = (row or {}).get("mime") or mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return FileResponse(
        path,
        media_type=mime,
        filename=path.name,
        headers={"Accept-Ranges": "bytes"},
    )


@app.post("/upload")
async def upload(
    request: Request,
    file: UploadFile = File(...),
    title: str = Form(""),
    artist: str = Form(""),
) -> JSONResponse:
    conn = request.app.state.hub_conn
    root: Path = request.app.state.hub_tracks_dir
    if not file.filename:
        raise HTTPException(status_code=400, detail="empty filename")
    suffix = Path(file.filename).suffix.lower() or ".bin"
    if suffix not in {".mp3", ".m4a", ".aac", ".ogg", ".opus", ".flac", ".wav", ".webm"}:
        raise HTTPException(status_code=400, detail="unsupported audio extension")
    rel = f"{uuid.uuid4().hex}{suffix}"
    dest = root / rel
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="empty file")
    dest.write_bytes(raw)
    mime = file.content_type or mimetypes.guess_type(file.filename)[0]
    t = (title or "").strip() or Path(file.filename).stem
    a = (artist or "").strip()
    tid = hub_db.insert_track(
        conn,
        rel_path=rel,
        title=t,
        artist=a,
        mime=mime,
        size_bytes=len(raw),
    )
    base = str(request.base_url).rstrip("/")
    return JSONResponse(
        {
            "id": tid,
            "title": t,
            "artist": a,
            "stream_url": f"{base}/tracks/{tid}/stream",
        },
        status_code=201,
    )
