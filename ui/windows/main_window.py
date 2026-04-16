from pathlib import Path

from PyQt6.QtCore import QRectF, QSize, pyqtSignal
from PyQt6.QtGui import QColor, QCloseEvent, QIcon, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer
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
from ui.interactive_fx import animate_stack_fade
from ui.windows.artist_profile_tab import ArtistProfileTab
from ui.windows.home_hub import HomeHubWidget
from ui.windows.mini_player_bar import MiniPlayerBar
from ui.windows.player_tab import PlayerTab
from ui.windows.popular_tab import PopularTab
from ui.windows.review_detail_dialog import ReviewDetailDialog
from ui.windows.reviews_tab import ReviewsTab
from ui.windows.search_tab import SearchTab
from ui.windows.selected_tab import SelectedTab
from ui.windows.settings_tab import SettingsTab

_ICONS_DIR = Path(__file__).resolve().parent.parent / "icons"
_SIDENAV_ICON_SIZE = QSize(40, 40)


def _render_tinted_svg(icon_path: Path, color: QColor, size: QSize) -> QIcon:
    renderer = QSvgRenderer(str(icon_path))
    pixmap = QPixmap(size)
    pixmap.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pixmap)
    view_box = renderer.viewBoxF()
    if view_box.isEmpty():
        view_box = QRectF(0, 0, float(size.width()), float(size.height()))
    target = QRectF(0, 0, float(size.width()), float(size.height()))
    scale = min(
        target.width() / max(1.0, view_box.width()),
        target.height() / max(1.0, view_box.height()),
    )
    draw_w = view_box.width() * scale
    draw_h = view_box.height() * scale
    draw_rect = QRectF(
        (target.width() - draw_w) / 2.0,
        (target.height() - draw_h) / 2.0,
        draw_w,
        draw_h,
    )
    renderer.render(painter, draw_rect)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    painter.fillRect(pixmap.rect(), color)
    painter.end()
    return QIcon(pixmap)


class SideNavButton(QPushButton):
    _COLOR_IDLE = QColor("#89A194")
    _COLOR_HOVER = QColor("#A14016")
    _COLOR_ACTIVE = QColor("#CB883A")
    _COLOR_PRESSED = QColor("#CFC89A")

    def __init__(self, icon_path: Path, parent=None):
        super().__init__(parent)
        self._icon_path = icon_path
        self._hovered = False
        self.setObjectName("sideNavButton")
        self.setCheckable(True)
        self.setIconSize(_SIDENAV_ICON_SIZE)
        self.setFixedSize(40, 40)
        self.setFlat(True)
        self.toggled.connect(lambda _checked: self._refresh_icon())
        self._refresh_icon()

    def enterEvent(self, event) -> None:
        self._hovered = True
        self._refresh_icon()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovered = False
        self._refresh_icon()
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        self.setIcon(_render_tinted_svg(self._icon_path, self._COLOR_PRESSED, self.iconSize()))
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        super().mouseReleaseEvent(event)
        self._refresh_icon()

    def _refresh_icon(self) -> None:
        if self.isChecked():
            color = self._COLOR_ACTIVE
        elif self._hovered:
            color = self._COLOR_HOVER
        else:
            color = self._COLOR_IDLE
        self.setIcon(_render_tinted_svg(self._icon_path, color, self.iconSize()))


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
            btn = SideNavButton(path)
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
    _ARTIST_PAGE_INDEX = 5

    def _open_artist_profile(self, artist_name: str) -> None:
        name = (artist_name or "").strip()
        if not name:
            return
        cur = self._stack.currentIndex()
        self._artist_return_index = (
            cur if cur != self._ARTIST_PAGE_INDEX else self._HOME_PAGE_INDEX
        )
        self._artist_profile.load_artist(name)
        animate_stack_fade(self._stack, self._ARTIST_PAGE_INDEX)

    def _close_artist_profile(self) -> None:
        idx = self._artist_return_index
        if (
            idx == self._ARTIST_PAGE_INDEX
            or idx < 0
            or idx >= self._stack.count()
        ):
            idx = self._HOME_PAGE_INDEX
        animate_stack_fade(self._stack, idx)
        nav = (
            idx if idx <= self._SETTINGS_PAGE_INDEX else self._HOME_PAGE_INDEX
        )
        self._side_nav.set_current_index(nav)

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

        self._artist_return_index = 0

        def on_select_track(music_item: dict) -> None:
            self._player.set_track(music_item)
            animate_stack_fade(self._stack, self._PLAYER_PAGE_INDEX)
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
            animate_stack_fade(self._stack, self._PLAYER_PAGE_INDEX)
            self._side_nav.set_current_index(self._PLAYER_PAGE_INDEX)

        self._artist_profile = ArtistProfileTab(
            session,
            on_back=self._close_artist_profile,
            on_play_track=on_select_track,
            on_open_album=on_open_album_queue,
        )

        self._player = PlayerTab(
            session=session,
            on_open_artist=self._open_artist_profile,
        )
        self._mini_player = MiniPlayerBar(
            self._player,
            on_open_player=self._open_main_player_from_mini,
            on_open_artist=self._open_artist_profile,
        )
        self._ambient_host.set_overlay_widget(self._mini_player, height=94, margin=14)

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
            on_open_artist=self._open_artist_profile,
        )

        self._player.library_changed.connect(self._selected_tab.reload_content)
        self._artist_profile.library_changed.connect(self._selected_tab.reload_content)

        self._settings = SettingsTab(
            session=session,
            on_playback_changed=self._player.refresh_playback_settings,
            on_logout=self._do_logout,
        )

        self._popular_tab = PopularTab(
            session,
            on_play_track=on_select_track,
            on_open_album=on_open_album_queue,
            on_open_artist=self._open_artist_profile,
        )
        self._popular_tab.library_changed.connect(self._selected_tab.reload_content)

        self._reviews_tab = ReviewsTab(
            session,
            on_open_artist=self._open_artist_profile,
        )

        self._home_hub = HomeHubWidget(self._popular_tab, self._reviews_tab)

        self._search_tab = SearchTab(
            session=session,
            on_select_track=on_select_track,
            on_open_artist=self._open_artist_profile,
        )
        self._search_tab.library_changed.connect(self._selected_tab.reload_content)

        self._pages: list[QWidget] = [
            self._home_hub,
            self._search_tab,
            self._selected_tab,
            self._player,
            self._settings,
            self._artist_profile,
        ]
        for page in self._pages:
            page.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Expanding,
            )
            self._stack.addWidget(page)

        self._side_nav.page_selected.connect(self._on_side_nav_clicked)
        self._home_hub.sub_page_changed.connect(self._on_home_sub_changed)
        self._stack.currentChanged.connect(self._sync_mini_player_visibility)
        self._player.current_item_changed.connect(lambda _item: self._sync_mini_player_visibility())

        self._side_nav.set_current_index(self._HOME_PAGE_INDEX)
        self._stack.setCurrentIndex(self._HOME_PAGE_INDEX)
        self._home_hub.reset_to_popular()
        self._popular_tab.reload_content()
        self._sync_mini_player_visibility()

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

    def _open_main_player_from_mini(self) -> None:
        animate_stack_fade(self._stack, self._PLAYER_PAGE_INDEX)
        self._side_nav.set_current_index(self._PLAYER_PAGE_INDEX)

    def _sync_mini_player_visibility(self) -> None:
        hidden_pages = {self._PLAYER_PAGE_INDEX, self._SETTINGS_PAGE_INDEX}
        should_show = (
            self._stack.currentIndex() not in hidden_pages
            and self._mini_player.has_track()
        )
        self._mini_player.setVisible(should_show)
        if should_show:
            self._mini_player.raise_()

    def closeEvent(self, event: QCloseEvent) -> None:
        self._player.flush_listen_for_close()
        super().closeEvent(event)

    def _on_side_nav_clicked(self, index: int) -> None:
        animate_stack_fade(self._stack, index)
        if index == self._HOME_PAGE_INDEX:
            self._home_hub.reset_to_popular()
            self._popular_tab.reload_content()
        elif index == self._SELECTED_PAGE_INDEX:
            self._selected_tab.reset_to_favorites()
            self._selected_tab.reload_content()

    def _on_home_sub_changed(self, sub: int) -> None:
        if self._stack.currentIndex() != self._HOME_PAGE_INDEX:
            return
        if sub == 0:
            self._popular_tab.reload_content()
        else:
            self._reviews_tab.reload_content()
