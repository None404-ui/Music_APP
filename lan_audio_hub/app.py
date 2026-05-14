from __future__ import annotations

import mimetypes
import os
import shutil
import subprocess
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Iterator

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import FileResponse, JSONResponse, Response, StreamingResponse

from lan_audio_hub import db as hub_db

DEFAULT_DATA = Path(__file__).resolve().parent / "_data"

_STREAM_BITRATE_QUERY = "crates_abr"
_AUDIO_SUFFIXES = frozenset(
    {".mp3", ".m4a", ".aac", ".ogg", ".opus", ".flac", ".wav", ".webm"}
)


def _parse_stream_bitrate_kbps(raw: str | None) -> int | None:
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    try:
        v = int(s)
    except ValueError:
        return None
    if 64 <= v <= 320:
        return v
    return None


def _try_transcoded_mp3_stream(path: Path, bitrate_kbps: int) -> StreamingResponse | None:
    if path.suffix.lower() not in _AUDIO_SUFFIXES:
        return None
    if not shutil.which("ffmpeg"):
        return None
    full = str(path)
    proc = subprocess.Popen(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-nostdin",
            "-i",
            full,
            "-vn",
            "-codec:a",
            "libmp3lame",
            "-b:a",
            f"{int(bitrate_kbps)}k",
            "-f",
            "mp3",
            "pipe:1",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout = proc.stdout
    if stdout is None:
        proc.wait(timeout=5)
        return None
    first = stdout.read(8192)
    if not first:
        if proc.stderr:
            proc.stderr.close()
        stdout.close()
        proc.kill()
        proc.wait(timeout=5)
        return None

    def body() -> Iterator[bytes]:
        yield first
        try:
            while True:
                chunk = stdout.read(64 * 1024)
                if not chunk:
                    break
                yield chunk
        finally:
            stdout.close()
            if proc.stderr:
                proc.stderr.close()
            proc.wait(timeout=120)

    return StreamingResponse(
        body(),
        media_type="audio/mpeg",
        headers={"Accept-Ranges": "none", "Cache-Control": "no-store"},
    )


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


@app.get("/tracks/{track_id}/stream", response_model=None)
def stream_track(track_id: int, request: Request) -> Response:
    conn = request.app.state.hub_conn
    root: Path = request.app.state.hub_tracks_dir
    path = hub_db.abs_path_for_track(conn, track_id, root)
    if path is None:
        raise HTTPException(status_code=404, detail="track not found")
    row = hub_db.get_track(conn, track_id)
    mime = (row or {}).get("mime") or mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    abr = _parse_stream_bitrate_kbps(request.query_params.get(_STREAM_BITRATE_QUERY))
    if abr is not None:
        transcoded = _try_transcoded_mp3_stream(path, abr)
        if transcoded is not None:
            return transcoded
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
