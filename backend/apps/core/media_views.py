import mimetypes
import os
import shutil
import subprocess
from pathlib import Path
from typing import Iterator

from django.conf import settings
from django.core.exceptions import SuspiciousFileOperation
from django.http import FileResponse, Http404, HttpResponse, StreamingHttpResponse
from django.utils._os import safe_join

# Совпадает с ui.playback_settings.STREAM_QUALITY_QUERY_PARAM
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


def _is_probably_audio_file(full_path: str) -> bool:
    return Path(full_path).suffix.lower() in _AUDIO_SUFFIXES


def _try_transcoded_mp3_response(full_path: str, bitrate_kbps: int) -> StreamingHttpResponse | None:
    if not shutil.which("ffmpeg"):
        return None
    proc = subprocess.Popen(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-nostdin",
            "-i",
            full_path,
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

    def combined() -> Iterator[bytes]:
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

    resp = StreamingHttpResponse(combined(), content_type="audio/mpeg")
    resp["Accept-Ranges"] = "none"
    resp["Cache-Control"] = "no-store"
    return resp


def _parse_range_header(raw_range: str, file_size: int) -> tuple[int, int] | None:
    raw = (raw_range or "").strip()
    if not raw.startswith("bytes="):
        return None
    spec = raw[6:].strip()
    if not spec or "," in spec:
        return None
    start_raw, sep, end_raw = spec.partition("-")
    if not sep:
        return None
    try:
        if start_raw == "":
            suffix = int(end_raw)
            if suffix <= 0:
                return None
            if suffix >= file_size:
                return 0, max(0, file_size - 1)
            return file_size - suffix, file_size - 1
        start = int(start_raw)
        if start < 0 or start >= file_size:
            return None
        if end_raw == "":
            return start, file_size - 1
        end = int(end_raw)
        if end < start:
            return None
        return start, min(end, file_size - 1)
    except (TypeError, ValueError):
        return None


def _iter_file_range(
    file_obj, start: int, length: int, chunk_size: int = 64 * 1024
) -> Iterator[bytes]:
    remaining = max(0, int(length))
    file_obj.seek(max(0, int(start)))
    try:
        while remaining > 0:
            chunk = file_obj.read(min(chunk_size, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk
    finally:
        file_obj.close()


def serve_media(request, path: str):
    try:
        full_path = safe_join(str(settings.MEDIA_ROOT), path)
    except SuspiciousFileOperation as exc:
        raise Http404("File not found") from exc

    if not full_path or not os.path.isfile(full_path):
        raise Http404("File not found")

    file_size = os.path.getsize(full_path)
    content_type, _ = mimetypes.guess_type(full_path)
    content_type = content_type or "application/octet-stream"
    range_header = request.headers.get("Range") or request.META.get("HTTP_RANGE") or ""

    abr = _parse_stream_bitrate_kbps(request.GET.get(_STREAM_BITRATE_QUERY))
    if abr and _is_probably_audio_file(full_path):
        transcoded = _try_transcoded_mp3_response(full_path, abr)
        if transcoded is not None:
            return transcoded

    if not range_header:
        response = FileResponse(open(full_path, "rb"), content_type=content_type)
        response["Content-Length"] = str(file_size)
        response["Accept-Ranges"] = "bytes"
        return response

    byte_range = _parse_range_header(range_header, file_size)
    if byte_range is None:
        response = HttpResponse(status=416)
        response["Content-Range"] = f"bytes */{file_size}"
        response["Accept-Ranges"] = "bytes"
        return response

    start, end = byte_range
    length = end - start + 1
    response = StreamingHttpResponse(
        _iter_file_range(open(full_path, "rb"), start, length),
        status=206,
        content_type=content_type,
    )
    response["Content-Length"] = str(length)
    response["Content-Range"] = f"bytes {start}-{end}/{file_size}"
    response["Accept-Ranges"] = "bytes"
    return response
