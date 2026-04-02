from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabBar, QSizePolicy,
)
from PyQt6.QtCore import Qt

from backend.session import UserSession
from ui.ambient_background import ContentWithAmbient
from ui.windows.popular_tab import PopularTab
from ui.windows.reviews_tab import ReviewsTab
from ui.windows.search_tab import SearchTab
from ui.windows.selected_tab import SelectedTab
from ui.windows.player_tab import PlayerTab
from ui.windows.settings_tab import SettingsTab


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
    def __init__(self, session: UserSession):
        super().__init__()
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

        PLAYER_PAGE_INDEX = 4
        self._player = PlayerTab()

        def on_select_track(music_item: dict) -> None:
            self._player.set_track(music_item)
            self._stack.setCurrentIndex(PLAYER_PAGE_INDEX)
            self._top_bar.tab_bar.setCurrentIndex(PLAYER_PAGE_INDEX)

        self._settings = SettingsTab(on_playback_changed=self._player.refresh_playback_settings)

        self._pages: list[QWidget] = [
            PopularTab(),
            ReviewsTab(),
            SearchTab(on_select_track=on_select_track),
            SelectedTab(session),
            self._player,
            self._settings,
        ]
        for page in self._pages:
            self._stack.addWidget(page)

        self._top_bar.tab_bar.currentChanged.connect(self._stack.setCurrentIndex)
        self._top_bar.tab_bar.setCurrentIndex(0)
