from pathlib import Path

from PyQt6.QtCore import QSize, pyqtSignal
from PyQt6.QtGui import QCloseEvent, QIcon
from PyQt6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from backend.session import UserSession
from ui.ambient_background import ContentWithAmbient
from ui.windows.home_hub import HomeHubWidget
from ui.windows.player_tab import PlayerTab
from ui.windows.popular_tab import PopularTab
from ui.windows.review_detail_dialog import ReviewDetailDialog
from ui.windows.reviews_tab import ReviewsTab
from ui.windows.search_tab import SearchTab
from ui.windows.selected_tab import SelectedTab
from ui.windows.settings_tab import SettingsTab

_ICONS_DIR = Path(__file__).resolve().parent.parent / "icons"
_SIDENAV_ICON_SIZE = QSize(40, 40)


class SideNavBar(QWidget):
    page_selected = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sideNavBar")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 20, 10, 20)
        layout.setSpacing(32)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)

        icon_paths = [
            _ICONS_DIR / "home_icon.svg",
            _ICONS_DIR / "search.svg",
            _ICONS_DIR / "player_like.svg",
            _ICONS_DIR / "music_icon.svg",
            _ICONS_DIR / "settings_icon.svg",
        ]
        self._buttons: list[QPushButton] = []
        for i, path in enumerate(icon_paths):
            btn = QPushButton()
            btn.setObjectName("sideNavButton")
            btn.setCheckable(True)
            btn.setIcon(QIcon(str(path)))
            btn.setIconSize(_SIDENAV_ICON_SIZE)
            btn.setFixedSize(40, 40)
            btn.setFlat(True)
            btn.toggled.connect(
                lambda c, b=btn: self._ensure_one_checked(c, b),
            )
            self._group.addButton(btn, i)
            layout.addWidget(btn)
            self._buttons.append(btn)

        layout.addStretch()
        self._group.idClicked.connect(self.page_selected.emit)

    def _ensure_one_checked(self, checked: bool, btn: QPushButton) -> None:
        if checked or self._group.checkedButton() is not None:
            return
        self._group.blockSignals(True)
        btn.blockSignals(True)
        btn.setChecked(True)
        btn.blockSignals(False)
        self._group.blockSignals(False)

    def set_current_index(self, index: int) -> None:
        self._group.blockSignals(True)
        try:
            if 0 <= index < len(self._buttons):
                self._buttons[index].setChecked(True)
        finally:
            self._group.blockSignals(False)


class MainWindow(QMainWindow):
    _HOME_PAGE_INDEX = 0
    _SEARCH_PAGE_INDEX = 1
    _SELECTED_PAGE_INDEX = 2
    _PLAYER_PAGE_INDEX = 3
    _SETTINGS_PAGE_INDEX = 4

    def __init__(self, session: UserSession):
        super().__init__()
        self._session = session
        self._logout_restart = False
        self.setWindowTitle("CRATES")
        self.setMinimumSize(900, 600)

        central = QWidget()
        central.setObjectName("centralWidget")
        self.setCentralWidget(central)

        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self._side_nav = SideNavBar()
        root_layout.addWidget(self._side_nav, stretch=0)

        self._ambient_host = ContentWithAmbient()
        self._stack = self._ambient_host.page_stack
        root_layout.addWidget(self._ambient_host, stretch=1)

        self._player = PlayerTab(session=session)

        def on_select_track(music_item: dict) -> None:
            self._player.set_track(music_item)
            self._stack.setCurrentIndex(self._PLAYER_PAGE_INDEX)
            self._side_nav.set_current_index(self._PLAYER_PAGE_INDEX)

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
            self._stack.setCurrentIndex(self._PLAYER_PAGE_INDEX)
            self._side_nav.set_current_index(self._PLAYER_PAGE_INDEX)

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

        self._selected_tab = SelectedTab(
            session,
            on_play_track=on_select_track,
            on_open_album=on_open_album_queue,
            on_open_review=on_open_review_from_selected,
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
        )
        self._reviews_tab = ReviewsTab(session)

        self._home_hub = HomeHubWidget(self._popular_tab, self._reviews_tab)

        self._pages: list[QWidget] = [
            self._home_hub,
            SearchTab(on_select_track=on_select_track),
            self._selected_tab,
            self._player,
            self._settings,
        ]
        for page in self._pages:
            page.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Expanding,
            )
            self._stack.addWidget(page)

        self._side_nav.page_selected.connect(self._on_side_nav_clicked)
        self._home_hub.sub_page_changed.connect(self._on_home_sub_changed)

        self._side_nav.set_current_index(self._HOME_PAGE_INDEX)
        self._stack.setCurrentIndex(self._HOME_PAGE_INDEX)
        self._home_hub.reset_to_popular()
        self._popular_tab.reload_content()

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

    def _on_side_nav_clicked(self, index: int) -> None:
        self._stack.setCurrentIndex(index)
        if index == self._HOME_PAGE_INDEX:
            self._home_hub.reset_to_popular()
            self._popular_tab.reload_content()
        elif index == self._SELECTED_PAGE_INDEX:
            self._selected_tab.reload_content()

    def _on_home_sub_changed(self, sub: int) -> None:
        if self._stack.currentIndex() != self._HOME_PAGE_INDEX:
            return
        if sub == 0:
            self._popular_tab.reload_content()
        else:
            self._reviews_tab.reload_content()
