from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QFrame,
    QSizePolicy,
    QGraphicsDropShadowEffect,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from backend.session import UserSession
from ui.tape_background import CassetteBackgroundMixin


def _response_list(body) -> list:
    if isinstance(body, list):
        return body
    if isinstance(body, dict) and "results" in body:
        return body["results"]
    return []


class SelectedTab(CassetteBackgroundMixin, QWidget):
    """Избранное, подборки и рецензии пользователя через Django API."""

    def __init__(self, session: UserSession, parent=None):
        super().__init__(parent)
        self.setObjectName("selectedPage")
        self.setAutoFillBackground(False)
        client = session.client

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 16, 24, 24)
        outer.setSpacing(6)

        title = QLabel("МОЁ")
        title.setObjectName("sectionHeading")
        sh = QGraphicsDropShadowEffect(title)
        sh.setBlurRadius(16)
        sh.setOffset(2, 3)
        sh.setColor(QColor(8, 28, 42, 150))
        title.setGraphicsEffect(sh)
        outer.addWidget(title)

        subtitle = QLabel("Избранное, подборки и рецензии (данные с сервера)")
        subtitle.setObjectName("selectedRowSub")
        subtitle.setWordWrap(True)
        outer.addWidget(subtitle)

        scroll = QScrollArea()
        scroll.setObjectName("selectedScroll")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        col = QVBoxLayout(container)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(6)

        col.addWidget(self._section_label("ИЗБРАННЫЕ ТРЕКИ"))
        st_fav, fav_body = client.get_json("/api/favorites/")
        favs = _response_list(fav_body) if st_fav == 200 else []
        if favs:
            for row in favs:
                mi = row.get("music_item") or {}
                title_t = mi.get("title") or "—"
                artist = mi.get("artist") or ""
                col.addWidget(self._track_row(str(title_t), str(artist)))
        else:
            msg = (
                "Нет избранного или сервер недоступен."
                if st_fav != 200
                else "Пока нет треков в избранном."
            )
            col.addWidget(self._empty(msg))

        col.addWidget(self._section_label("МОИ ПОДБОРКИ"))
        st_col, col_body = client.get_json("/api/collections/")
        collections = _response_list(col_body) if st_col == 200 else []
        own = [c for c in collections if c.get("owner") == session.user_id]
        if own:
            for c in own:
                col.addWidget(self._track_row(c.get("title") or "—", c.get("description") or ""))
        else:
            msg = (
                "Не удалось загрузить подборки."
                if st_col != 200
                else "Подборок пока нет."
            )
            col.addWidget(self._empty(msg))

        col.addWidget(self._section_label("МОИ РЕЦЕНЗИИ"))
        st_rev, rev_body = client.get_json(f"/api/reviews/?author_id={session.user_id}")
        reviews = _response_list(rev_body) if st_rev == 200 else []
        if reviews:
            for r in reviews[:20]:
                text = (r.get("text") or "")[:120]
                if len(r.get("text") or "") > 120:
                    text += "…"
                col.addWidget(self._track_row("Рецензия", text or "—"))
        else:
            msg = (
                "Не удалось загрузить рецензии."
                if st_rev != 200
                else "Рецензий пока нет."
            )
            col.addWidget(self._empty(msg))

        col.addStretch()
        scroll.setWidget(container)
        outer.addWidget(scroll, stretch=1)

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

    @staticmethod
    def _track_row(title: str, artist: str) -> QFrame:
        row = QFrame()
        row.setObjectName("selectedRow")
        row.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        lay = QVBoxLayout(row)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(2)
        t = QLabel(title)
        t.setObjectName("selectedRowTitle")
        a = QLabel(artist)
        a.setObjectName("selectedRowSub")
        lay.addWidget(t)
        lay.addWidget(a)
        return row
