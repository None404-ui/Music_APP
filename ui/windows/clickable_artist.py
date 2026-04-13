"""Кликабельный никнейм исполнителя (переход на страницу артиста по user id)."""

from __future__ import annotations

from typing import Callable, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import QLabel, QSizePolicy

OnOpenArtist = Callable[[int], None]


def artist_user_id_from_item(item: dict) -> Optional[int]:
    if not isinstance(item, dict):
        return None
    uid = item.get("artist_user_id")
    if uid is not None:
        try:
            return int(uid)
        except (TypeError, ValueError):
            return None
    au = item.get("artist_user")
    if isinstance(au, dict) and au.get("id") is not None:
        try:
            return int(au["id"])
        except (TypeError, ValueError):
            return None
    return None


class ClickableArtistLabel(QLabel):
    """При наличии user_id и колбэка — курсор-рука и клик открывает артиста."""

    def __init__(
        self,
        text: str,
        user_id: Optional[int],
        on_open: Optional[OnOpenArtist] = None,
        *,
        object_name: str = "trackArtist",
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName(object_name)
        self.setText(text if text.strip() else "—")
        self._user_id = user_id
        self._on_open = on_open
        self.setWordWrap(False)
        self.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Preferred,
        )
        if user_id is not None and on_open is not None:
            self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_on_open(self, on_open: Optional[OnOpenArtist]) -> None:
        self._on_open = on_open

    def set_artist(self, text: str, user_id: Optional[int] = None) -> None:
        """Обновить подпись и id."""
        self.setText(text if (text or "").strip() else "—")
        self._user_id = user_id if self._on_open is not None else None
        if self._user_id is not None and self._on_open is not None:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self._user_id is not None
            and self._on_open is not None
        ):
            self._on_open(self._user_id)
            event.accept()
            return
        super().mouseReleaseEvent(event)
