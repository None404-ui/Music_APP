from __future__ import annotations

from PyQt6.QtCore import QRectF, Qt, QTimer, QUrl
from PyQt6.QtGui import QColor, QImage, QPainter, QPainterPath, QPixmap
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PyQt6.QtWidgets import QWidget

from backend.api_client import resolve_backend_media_url
from backend.session import UserSession


class AdBannerWidget(QWidget):
    """Top application banner loaded from /api/ads/ for non-premium users."""

    _PLACEMENT = "app_top_banner"

    def __init__(self, session: UserSession, parent=None):
        super().__init__(parent)
        self.setObjectName("adBanner")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._session = session
        self._nam = QNetworkAccessManager(self)
        self._reply: QNetworkReply | None = None
        self._pixmap = QPixmap()
        self.hide()
        QTimer.singleShot(0, self.refresh)

    def refresh(self) -> None:
        self._abort_load()
        self._pixmap = QPixmap()
        self.hide()
        try:
            status, body = self._session.client.get_json(
                f"/api/ads/?placement={self._PLACEMENT}&limit=1",
                timeout=10.0,
            )
        except Exception:
            return
        if status != 200 or not isinstance(body, dict):
            return
        ads = body.get("ads")
        if not isinstance(ads, list) or not ads:
            return
        ad = ads[0]
        if not isinstance(ad, dict):
            return
        image_url = resolve_backend_media_url(
            self._session.client.base_url,
            (ad.get("image_url") or "").strip(),
        )
        if not image_url.startswith(("http://", "https://")):
            return
        self._reply = self._nam.get(QNetworkRequest(QUrl(image_url)))
        self._reply.finished.connect(self._on_image_finished)

    def _abort_load(self) -> None:
        if self._reply is None:
            return
        reply = self._reply
        self._reply = None
        reply.abort()
        reply.deleteLater()

    def _on_image_finished(self) -> None:
        reply = self.sender()
        if not isinstance(reply, QNetworkReply):
            return
        if reply is not self._reply:
            reply.deleteLater()
            return
        self._reply = None
        try:
            if reply.error() != QNetworkReply.NetworkError.NoError:
                self.hide()
                return
            img = QImage()
            if not img.loadFromData(reply.readAll()):
                self.hide()
                return
            pm = QPixmap.fromImage(img)
            if pm.isNull():
                self.hide()
                return
            self._pixmap = pm
            self.show()
            self.update()
        finally:
            reply.deleteLater()

    def paintEvent(self, event) -> None:
        del event
        if self._pixmap.isNull():
            return

        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        if rect.width() <= 1 or rect.height() <= 1:
            return

        scaled = self._pixmap.scaled(
            int(rect.width()),
            int(rect.height()),
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        x = int(rect.x() + (rect.width() - scaled.width()) / 2)
        y = int(rect.y() + (rect.height() - scaled.height()) / 2)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        path = QPainterPath()
        path.addRoundedRect(rect, 8, 8)
        painter.setClipPath(path)
        painter.fillRect(rect, QColor("#1f1828"))
        painter.drawPixmap(x, y, scaled)
        painter.end()
