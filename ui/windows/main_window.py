from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabBar, QStackedWidget, QSizePolicy,
)
from PyQt6.QtCore import Qt

from ui.windows.popular_tab import PopularTab
from ui.windows.reviews_tab import ReviewsTab
from ui.windows.search_tab import SearchTab
from ui.windows.player_tab import PlayerTab
from ui.windows.settings_tab import SettingsTab


_TAB_NAMES = [
    "популярное",
    "рецензии",
    "поиск",
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
    def __init__(self):
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

        self._stack = QStackedWidget()
        self._stack.setObjectName("pageStack")
        root_layout.addWidget(self._stack, stretch=1)

        self._pages: list[QWidget] = [
            PopularTab(),
            ReviewsTab(),
            SearchTab(),
            PlayerTab(),
            SettingsTab(),
        ]
        for page in self._pages:
            self._stack.addWidget(page)

        self._top_bar.tab_bar.currentChanged.connect(self._stack.setCurrentIndex)
        self._top_bar.tab_bar.setCurrentIndex(0)
