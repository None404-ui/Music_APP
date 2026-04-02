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
from backend import tracks as tracks_api
from ui.tape_background import CassetteBackgroundMixin


class SelectedTab(CassetteBackgroundMixin, QWidget):
    """Избранное, загруженные треки, рецензии пользователя (данные из БД + заглушки)."""

    def __init__(self, session: UserSession, parent=None):
        super().__init__(parent)
        self.setObjectName("selectedPage")
        self.setAutoFillBackground(False)
        self._session = session

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

        subtitle = QLabel("Избранное, загрузки и ваши действия в приложении")
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
        favs = tracks_api.list_favorites(session.user_id)
        if favs:
            for t in favs:
                col.addWidget(self._track_row(t["title"], t["artist"]))
        else:
            col.addWidget(self._empty("Пока нет треков в избранном."))

        col.addWidget(self._section_label("МОИ ТРЕКИ (ЗАГРУЖЕННЫЕ)"))
        own = tracks_api.list_user_owned_tracks(session.user_id)
        if own:
            for t in own:
                col.addWidget(self._track_row(t["title"], t["artist"]))
        else:
            col.addWidget(self._empty("Вы ещё не добавляли свои треки."))

        col.addWidget(self._section_label("МОИ РЕЦЕНЗИИ"))
        col.addWidget(
            self._empty(
                "Раздел рецензий пользователя подключим к базе на следующем шаге."
            )
        )

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
