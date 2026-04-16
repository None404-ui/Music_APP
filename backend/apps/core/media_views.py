import mimetypes
import os
from typing import Iterator

from django.conf import settings
from django.core.exceptions import SuspiciousFileOperation
from django.http import FileResponse, Http404, HttpResponse, StreamingHttpResponse
from django.utils._os import safe_join


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
