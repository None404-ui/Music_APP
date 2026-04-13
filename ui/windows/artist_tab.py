"""Страница артиста: аватар, ник, список треков."""

from __future__ import annotations

from typing import Callable, Optional

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QImage, QMouseEvent, QPixmap
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from backend.api_client import resolve_backend_media_url
from backend.session import UserSession

OnPlayTrack = Callable[[dict], None]

_avatar_nam: QNetworkAccessManager | None = None


def _avatar_network() -> QNetworkAccessManager:
    global _avatar_nam
    if _avatar_nam is None:
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance()
        _avatar_nam = QNetworkAccessManager(app)
    return _avatar_nam


def _fmt_duration(sec: int | None) -> str:
    if sec is None or sec <= 0:
        return "—"
    m, s = divmod(int(sec), 60)
    return f"{m}:{s:02d}"


class _ArtistTrackRow(QFrame):
    def __init__(
        self,
        index: int,
        item: dict,
        on_play: Optional[OnPlayTrack],
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("artistPageTrackRow")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._item = item
        self._on_play = on_play

        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(12)

        num = QLabel(str(index))
        num.setObjectName("trackNumber")
        num.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel((item.get("title") or "Без названия").strip())
        title.setObjectName("trackTitle")
        title.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        stats = QLabel(
            f"♥ {int(item.get('favorites_count') or 0)}  ·  "
            f"{int(item.get('listens_count') or 0)} слуш."
        )
        stats.setObjectName("trackStats")

        dur = QLabel(_fmt_duration(item.get("duration_sec")))
        dur.setObjectName("trackDuration")
        dur.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        lay.addWidget(num, 0, Qt.AlignmentFlag.AlignVCenter)
        lay.addWidget(title, 1, Qt.AlignmentFlag.AlignVCenter)
        lay.addWidget(stats, 0, Qt.AlignmentFlag.AlignVCenter)
        lay.addWidget(dur, 0, Qt.AlignmentFlag.AlignVCenter)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._on_play:
            self._on_play(self._item)
        super().mouseReleaseEvent(event)


class ArtistTab(QWidget):
    def __init__(
        self,
        session: UserSession,
        *,
        on_back: Callable[[], None],
        on_play_track: Optional[OnPlayTrack] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("artistPage")
        self._session = session
        self._on_back = on_back
        self._on_play_track = on_play_track
        self._avatar_reply: QNetworkReply | None = None
        self._user_id: int | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 16, 24, 24)
        outer.setSpacing(14)

        head = QHBoxLayout()
        head.setSpacing(16)

        self._btn_back = QPushButton("← Назад")
        self._btn_back.setObjectName("btnArtistBack")
        self._btn_back.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_back.clicked.connect(on_back)
        head.addWidget(self._btn_back)
        head.addStretch()
        outer.addLayout(head)

        profile_row = QHBoxLayout()
        profile_row.setSpacing(16)

        self._avatar = QLabel()
        self._avatar.setObjectName("artistPageAvatar")
        self._avatar.setFixedSize(96, 96)
        self._avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._avatar.setText("♫")
        self._avatar.setStyleSheet("font-size: 36px; color: #A14016;")

        meta = QVBoxLayout()
        self._nickname = QLabel("—")
        self._nickname.setObjectName("artistPageNickname")
        self._bio = QLabel("")
        self._bio.setObjectName("artistPageBio")
        self._bio.setWordWrap(True)
        meta.addWidget(self._nickname)
        meta.addWidget(self._bio)
        meta.addStretch()

        profile_row.addWidget(self._avatar)
        profile_row.addLayout(meta, stretch=1)
        outer.addLayout(profile_row)

        tracks_title = QLabel("ТРЕКИ")
        tracks_title.setObjectName("sectionHeading")
        outer.addWidget(tracks_title)

        self._status = QLabel("")
        self._status.setObjectName("popularLoadStatus")
        self._status.hide()
        outer.addWidget(self._status)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._tracks_host = QWidget()
        self._tracks_layout = QVBoxLayout(self._tracks_host)
        self._tracks_layout.setContentsMargins(0, 4, 0, 0)
        self._tracks_layout.setSpacing(8)
        scroll.setWidget(self._tracks_host)
        outer.addWidget(scroll, stretch=1)

    def _abort_avatar(self) -> None:
        if self._avatar_reply is None:
            return
        r = self._avatar_reply
        self._avatar_reply = None
        r.abort()

    def _on_avatar_finished(self) -> None:
        reply = self.sender()
        if not isinstance(reply, QNetworkReply):
            return
        if self._avatar_reply is not reply:
            reply.deleteLater()
            return
        self._avatar_reply = None
        try:
            if reply.error() != QNetworkReply.NetworkError.NoError:
                return
            data = reply.readAll()
            img = QImage()
            if not img.loadFromData(data):
                return
            pix = QPixmap.fromImage(img).scaled(
                96,
                96,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._avatar.setPixmap(pix)
            self._avatar.setText("")
        finally:
            reply.deleteLater()

    def load_artist(self, user_id: int) -> None:
        self._user_id = user_id
        self._abort_avatar()
        self._clear_tracks()
        self._nickname.setText("…")
        self._bio.setText("")
        self._avatar.clear()
        self._avatar.setPixmap(QPixmap())
        self._avatar.setText("♫")
        self._status.hide()

        st, body = self._session.client.get_json(f"/api/users/{user_id}/artist/")
        if st != 200 or not isinstance(body, dict):
            self._status.setText(
                "Не удалось загрузить страницу артиста."
                if st != 404
                else "Пользователь не найден."
            )
            self._status.show()
            self._nickname.setText("—")
            return

        nick = (body.get("nickname") or "").strip() or "—"
        self._nickname.setText(nick)
        bio = (body.get("bio") or "").strip()
        self._bio.setText(bio)
        self._bio.setVisible(bool(bio))

        api_base = self._session.client.base_url
        url = resolve_backend_media_url(
            api_base, (body.get("avatar_url") or "").strip()
        )
        if url.startswith(("http://", "https://")):
            self._avatar_reply = _avatar_network().get(QNetworkRequest(QUrl(url)))
            self._avatar_reply.finished.connect(self._on_avatar_finished)

        tracks = body.get("tracks")
        if not isinstance(tracks, list):
            tracks = []
        for i, it in enumerate(tracks, start=1):
            if not isinstance(it, dict):
                continue
            row = _ArtistTrackRow(i, it, self._on_play_track, self._tracks_host)
            self._tracks_layout.addWidget(row)
        if not tracks:
            empty = QLabel("Пока нет треков.")
            empty.setObjectName("popularEmptyHint")
            self._tracks_layout.addWidget(empty)

    def _clear_tracks(self) -> None:
        while self._tracks_layout.count():
            it = self._tracks_layout.takeAt(0)
            w = it.widget()
            if w is not None:
                w.deleteLater()
