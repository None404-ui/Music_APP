from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTabBar,
    QSizePolicy,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QCloseEvent

from backend.session import UserSession
from ui.ambient_background import ContentWithAmbient
from ui.windows.popular_tab import PopularTab
from ui.windows.reviews_tab import ReviewsTab
from ui.windows.search_tab import SearchTab
from ui.windows.selected_tab import SelectedTab
from ui.windows.player_tab import PlayerTab
from ui.windows.review_detail_dialog import ReviewDetailDialog
from ui.windows.settings_tab import SettingsTab
from ui.windows.artist_tab import ArtistTab


_TAB_NAMES = [
    "популярное",
    "рецензии",
    "поиск",
    "моё",
    "плеер",
    "настройки",
]


class TopBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("topBar")
        self.setFixedHeight(52)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 6, 16, 0)
        layout.setSpacing(0)

        self.tab_bar = QTabBar()
        self.tab_bar.setObjectName("mainTabBar")
        self.tab_bar.setExpanding(False)
        self.tab_bar.setDrawBase(False)

        for name in _TAB_NAMES:
            self.tab_bar.addTab(name)

        layout.addWidget(self.tab_bar)
        layout.addStretch()


class MainWindow(QMainWindow):
    _POPULAR_TAB_INDEX = 0
    _REVIEWS_TAB_INDEX = 1
    _SELECTED_TAB_INDEX = 3
    _ARTIST_PAGE_INDEX = 6

    def __init__(self, session: UserSession):
        super().__init__()
        self._session = session
        self._logout_restart = False
        self.setWindowTitle("CRATES")
        self.setMinimumSize(900, 600)

        central = QWidget()
        central.setObjectName("centralWidget")
        self.setCentralWidget(central)

        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self._top_bar = TopBar()
        root_layout.addWidget(self._top_bar)

        self._ambient_host = ContentWithAmbient()
        self._stack = self._ambient_host.page_stack
        root_layout.addWidget(self._ambient_host, stretch=1)

        self._saved_stack_index = 0
        self._saved_tab_index = 0

        PLAYER_PAGE_INDEX = 4

        def on_select_track(music_item: dict) -> None:
            self._player.set_track(music_item)
            self._stack.setCurrentIndex(PLAYER_PAGE_INDEX)
            self._top_bar.tab_bar.setCurrentIndex(PLAYER_PAGE_INDEX)

        def on_open_album_queue(tracks: list, source_card: dict | None = None) -> None:
            ctx_id = None
            if isinstance(source_card, dict):
                prov = (source_card.get("provider") or "").strip()
                if prov != "collection":
                    sid = source_card.get("id")
                    if sid is not None:
                        ctx_id = int(sid)
            self._player.set_queue(
                tracks,
                0,
                context_music_item_id=ctx_id,
                source_card=source_card,
            )
            self._stack.setCurrentIndex(PLAYER_PAGE_INDEX)
            self._top_bar.tab_bar.setCurrentIndex(PLAYER_PAGE_INDEX)

        def on_open_review_from_selected(review: dict) -> None:
            body = review.get("text") or ""
            mi = review.get("music_item")
            if isinstance(mi, dict):
                album = mi.get("title") or "Трек"
            elif mi is not None:
                album = f"Трек #{mi}"
            else:
                album = "Рецензия"
            headline = body.split("\n")[0].strip() if body else "Рецензия"
            if len(headline) > 100:
                headline = headline[:97] + "…"
            author = session.email or "Вы"
            dlg = ReviewDetailDialog(album, headline, author, "—", body, self)
            dlg.exec()

        self._player = PlayerTab(
            session=session,
            on_open_artist=self._open_artist_page,
        )

        self._selected_tab = SelectedTab(
            session,
            on_play_track=on_select_track,
            on_open_album=on_open_album_queue,
            on_open_review=on_open_review_from_selected,
            on_open_artist=self._open_artist_page,
        )

        self._player.library_changed.connect(self._selected_tab.reload_content)

        self._settings = SettingsTab(
            session=session,
            on_playback_changed=self._player.refresh_playback_settings,
            on_logout=self._do_logout,
        )

        self._popular_tab = PopularTab(
            session,
            on_play_track=on_select_track,
            on_open_album=on_open_album_queue,
            on_open_artist=self._open_artist_page,
        )
        self._reviews_tab = ReviewsTab(
            session,
            on_open_artist=self._open_artist_page,
        )

        self._search_tab = SearchTab(
            on_select_track=on_select_track,
            on_open_artist=self._open_artist_page,
        )

        self._artist_tab = ArtistTab(
            session,
            on_back=self._close_artist_page,
            on_play_track=on_select_track,
        )

        self._pages: list[QWidget] = [
            self._popular_tab,
            self._reviews_tab,
            self._search_tab,
            self._selected_tab,
            self._player,
            self._settings,
            self._artist_tab,
        ]
        for page in self._pages:
            page.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Expanding,
            )
            self._stack.addWidget(page)

        self._top_bar.tab_bar.currentChanged.connect(self._on_main_tab_changed)
        self._top_bar.tab_bar.setCurrentIndex(0)

    def consume_logout_restart(self) -> bool:
        v = self._logout_restart
        self._logout_restart = False
        return v

    def _do_logout(self) -> None:
        from backend.api_client import api_logout
        from backend.remember_login import clear_remembered

        api_logout(self._session.client)
        clear_remembered()
        self._logout_restart = True
        self.close()

    def closeEvent(self, event: QCloseEvent) -> None:
        self._player.flush_listen_for_close()
        super().closeEvent(event)

    def _open_artist_page(self, user_id: int) -> None:
        self._saved_stack_index = self._stack.currentIndex()
        self._saved_tab_index = self._top_bar.tab_bar.currentIndex()
        self._artist_tab.load_artist(int(user_id))
        self._stack.setCurrentIndex(self._ARTIST_PAGE_INDEX)

    def _close_artist_page(self) -> None:
        self._stack.setCurrentIndex(self._saved_stack_index)
        self._top_bar.tab_bar.blockSignals(True)
        self._top_bar.tab_bar.setCurrentIndex(self._saved_tab_index)
        self._top_bar.tab_bar.blockSignals(False)

    def _on_main_tab_changed(self, index: int) -> None:
        self._stack.setCurrentIndex(index)
        if index == self._POPULAR_TAB_INDEX:
            self._popular_tab.reload_content()
        elif index == self._REVIEWS_TAB_INDEX:
            self._reviews_tab.reload_content()
        elif index == self._SELECTED_TAB_INDEX:
            self._selected_tab.reload_content()
