"""Кликабельное имя исполнителя — открывает профиль артиста в приложении."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import QLabel


class ArtistLinkLabel(QLabel):
    """Показывает имя; по клику испускает artist_clicked с непустой строкой."""

    artist_clicked = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("artistLinkLabel")
        self._name = ""

    def set_artist(self, name: str) -> None:
        self._name = (name or "").strip()
        if self._name:
            self.setText(self._name)
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self.setToolTip(f"Профиль: {self._name}")
        else:
            self.clear()
            self.setText("—")
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.setToolTip("")

    def artist_name(self) -> str:
        return self._name

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self._name
            and self.rect().contains(event.position().toPoint())
        ):
            self.artist_clicked.emit(self._name)
        super().mouseReleaseEvent(event)
