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
        on_open_review: Optional[OnOpenReview] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("selectedPage")
        self.setAutoFillBackground(True)
        self._session = session
        self._client = session.client
        self._on_play_track = on_play_track
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

        subtitle = QLabel(
            "Избранное, подборки и рецензии. Трек в избранном — открыть в плеере; "
            "строка рецензии — прочитать текст."
        )
        subtitle.setObjectName("selectedRowSub")
        subtitle.setWordWrap(True)
        self._outer.addWidget(subtitle)

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

        col.addWidget(self._section_label("ИЗБРАННЫЕ ТРЕКИ"))
        st_fav, fav_body = self._client.get_json("/api/favorites/")
        favs = _response_list(fav_body) if st_fav == 200 else []
        if favs:
            for row in favs:
                mi = row.get("music_item") or {}
                if isinstance(mi, dict):
                    title_t = mi.get("title") or "—"
                    artist = mi.get("artist") or ""
                else:
                    title_t, artist = "—", ""
                play_cb = None
                if self._on_play_track and isinstance(mi, dict) and mi.get("id") is not None:
                    play_cb = lambda m=mi: self._on_play_track(m)
                col.addWidget(_ClickableRow(str(title_t), str(artist), play_cb))
        else:
            msg = (
                "Нет избранного или сервер недоступен."
                if st_fav != 200
                else "Пока нет треков в избранном. Нажмите ♥ в плеере."
            )
            col.addWidget(self._empty(msg))

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
