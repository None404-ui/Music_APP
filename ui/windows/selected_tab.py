from __future__ import annotations

from typing import Callable, Optional

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QScrollArea,
    QFrame,
    QSizePolicy,
    QGraphicsDropShadowEffect,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from backend.session import UserSession

OnPlayTrack = Callable[[dict], None]
OnOpenAlbum = Callable[[list, dict], None]
OnOpenReview = Callable[[dict], None]


def _response_list(body) -> list:
    if isinstance(body, list):
        return body
    if isinstance(body, dict) and "results" in body:
        return body["results"]
    return []


def _owner_id(collection: dict):
    o = collection.get("owner")
    if isinstance(o, dict):
        return o.get("id")
    return o


class _ClickableRow(QFrame):
    def __init__(
        self,
        title: str,
        subtitle: str,
        on_click: Optional[Callable[[], None]] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("selectedRow")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._on_click = on_click
        if on_click:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(2)
        t = QLabel(title)
        t.setObjectName("selectedRowTitle")
        a = QLabel(subtitle)
        a.setObjectName("selectedRowSub")
        a.setWordWrap(True)
        lay.addWidget(t)
        lay.addWidget(a)

    def mousePressEvent(self, event):
        if (
            self._on_click
            and event.button() == Qt.MouseButton.LeftButton
        ):
            self._on_click()
        super().mousePressEvent(event)


class SelectedTab(QWidget):
    """Избранное, подборки и рецензии — данные подгружаются с сервера при открытии вкладки."""

    def __init__(
        self,
        session: UserSession,
        *,
        on_play_track: Optional[OnPlayTrack] = None,
        on_open_album: Optional[OnOpenAlbum] = None,
        on_open_review: Optional[OnOpenReview] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("selectedPage")
        self.setAutoFillBackground(True)
        self._session = session
        self._client = session.client
        self._on_play_track = on_play_track
        self._on_open_album = on_open_album
        self._on_open_review = on_open_review

        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(24, 16, 24, 24)
        self._outer.setSpacing(6)

        title = QLabel("МОЁ")
        title.setObjectName("sectionHeading")
        sh = QGraphicsDropShadowEffect(title)
        sh.setBlurRadius(16)
        sh.setOffset(2, 3)
        sh.setColor(QColor(8, 28, 42, 150))
        title.setGraphicsEffect(sh)
        self._outer.addWidget(title)

        self._scroll = QScrollArea()
        self._scroll.setObjectName("selectedScroll")
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._outer.addWidget(self._scroll, stretch=1)

        self.reload_content()

    def reload_content(self) -> None:
        """Перечитать списки с API (после лайка / рецензии / входа на вкладку)."""
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        col = QVBoxLayout(container)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(6)

        st_fav, fav_body = self._client.get_json("/api/favorites/")
        favs = _response_list(fav_body) if st_fav == 200 else []

        fav_tracks: list[dict] = []
        fav_albums: list[dict] = []
        for row in favs:
            mi = row.get("music_item")
            if not isinstance(mi, dict) or mi.get("id") is None:
                continue
            k = (mi.get("kind") or "").strip().lower()
            if k in ("album", "playlist"):
                fav_albums.append(mi)
            else:
                fav_tracks.append(mi)

        if st_fav != 200:
            col.addWidget(self._section_label("ИЗБРАННОЕ"))
            col.addWidget(self._empty("Не удалось загрузить избранное с сервера."))
        else:
            col.addWidget(self._section_label("ИЗБРАННЫЕ АЛЬБОМЫ И ПЛЕЙЛИСТЫ"))
            if fav_albums:
                for mi in fav_albums:
                    title_t = mi.get("title") or "—"
                    artist = (mi.get("artist") or "").strip() or "—"
                    sub = (
                        "Альбом"
                        if (mi.get("kind") or "").strip().lower() == "album"
                        else "Плейлист"
                    )
                    open_cb = None
                    if self._on_open_album:
                        open_cb = lambda m=mi: self._open_favorite_album(m)
                    col.addWidget(
                        _ClickableRow(str(title_t), f"{sub} · {artist}", open_cb)
                    )
            else:
                col.addWidget(
                    self._empty(
                        "Пока нет. Во время воспроизведения альбома нажмите ♥ — "
                        "в избранное сохранится альбом."
                    )
                )

            col.addWidget(self._section_label("ИЗБРАННЫЕ ТРЕКИ"))
            if fav_tracks:
                for mi in fav_tracks:
                    title_t = mi.get("title") or "—"
                    artist = mi.get("artist") or ""
                    play_cb = None
                    if self._on_play_track:
                        play_cb = lambda m=mi: self._on_play_track(m)
                    col.addWidget(_ClickableRow(str(title_t), str(artist), play_cb))
            else:
                col.addWidget(
                    self._empty(
                        "Пока нет. ♥ для одного трека (поиск / не из очереди альбома)."
                    )
                )

        col.addWidget(self._section_label("МОИ ПОДБОРКИ"))
        st_col, col_body = self._client.get_json("/api/collections/")
        collections = _response_list(col_body) if st_col == 200 else []
        uid = self._session.user_id
        own = [c for c in collections if _owner_id(c) == uid]
        if own:
            for c in own:
                col.addWidget(
                    _ClickableRow(
                        c.get("title") or "—",
                        (c.get("description") or "").strip(),
                        None,
                    )
                )
        else:
            msg = (
                "Не удалось загрузить подборки."
                if st_col != 200
                else "Подборок пока нет."
            )
            col.addWidget(self._empty(msg))

        col.addWidget(self._section_label("МОИ РЕЦЕНЗИИ"))
        st_rev, rev_body = self._client.get_json(
            f"/api/reviews/?author_id={self._session.user_id}"
        )
        reviews = _response_list(rev_body) if st_rev == 200 else []
        if reviews:
            for r in reviews[:20]:
                full = r.get("text") or ""
                text = full[:120]
                if len(full) > 120:
                    text += "…"
                mi = r.get("music_item")
                if isinstance(mi, dict):
                    row_title = mi.get("title") or "Рецензия"
                elif mi is not None:
                    row_title = f"Трек #{mi}"
                else:
                    row_title = "Рецензия"
                rev_cb = None
                if self._on_open_review:
                    rev_cb = lambda rev=r: self._on_open_review(rev)
                col.addWidget(_ClickableRow(row_title, text or "—", rev_cb))
        else:
            msg = (
                "Не удалось загрузить рецензии."
                if st_rev != 200
                else "Рецензий пока нет. Добавьте из плеера."
            )
            col.addWidget(self._empty(msg))

        col.addStretch()
        self._scroll.takeWidget()
        self._scroll.setWidget(container)

    def _open_favorite_album(self, mi: dict) -> None:
        if not self._on_open_album:
            return
        mid = mi.get("id")
        if mid is None:
            return
        st, body = self._client.get_json(
            f"/api/music-items/playback-queue/?music_item_id={int(mid)}"
        )
        if st != 200 or not isinstance(body, dict):
            return
        raw = body.get("tracks")
        if not isinstance(raw, list):
            return
        tracks = [x for x in raw if isinstance(x, dict)]
        if tracks:
            self._on_open_album(tracks, mi)

    @staticmethod
    def _section_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("selectedSectionLabel")
        return lbl

    @staticmethod
    def _empty(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("selectedEmpty")
        lbl.setWordWrap(True)
        return lbl
