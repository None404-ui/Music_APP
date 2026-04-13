"""
Длительность локального аудио (секунды) для MusicItem.audio_file и файлов на диске.
"""

from __future__ import annotations

import os
import tempfile


def probe_audio_duration_sec(path: str) -> int | None:
    """Длительность в секундах (округление), либо None если не удалось прочитать."""
    if not path or not os.path.isfile(path):
        return None
    try:
        from mutagen import File as MutagenFile
    except ImportError:
        return None
    try:
        audio = MutagenFile(path)
        if audio is None:
            return None
        info = getattr(audio, "info", None)
        if info is None or not hasattr(info, "length"):
            return None
        ln = info.length
        if ln is None or ln <= 0:
            return None
        return max(1, int(round(float(ln))))
    except Exception:
        return None


def duration_from_filefield(field_file) -> int | None:
    """Читает длительность с диска (локальный storage) или через временный файл."""
    if not field_file or not getattr(field_file, "name", None):
        return None
    try:
        path = field_file.path
    except (NotImplementedError, ValueError, AttributeError):
        path = None
    if path and os.path.isfile(path):
        return probe_audio_duration_sec(path)

    ext = os.path.splitext(str(field_file.name))[1] or ".audio"
    tmp_path: str | None = None
    sec: int | None = None
    try:
        field_file.open("rb")
        try:
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                for chunk in field_file.chunks():
                    tmp.write(chunk)
                tmp_path = tmp.name
            sec = probe_audio_duration_sec(tmp_path) if tmp_path else None
        finally:
            field_file.close()
    except Exception:
        sec = None
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
    return sec
