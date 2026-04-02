import os
import json
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QListWidget, QListWidgetItem,
    QFrame,
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon

_FILTER_LABELS = ["альбомы", "рецензии", "исполнители"]

_PLACEHOLDER_HISTORY = [
    "предыдущий запрос.....",
    "предыдущий запрос.....",
]

_ICON_SEARCH = os.path.join(os.path.dirname(__file__), "..", "icons", "search.svg")


class SearchTab(QWidget):
    def __init__(self, on_select_track=None, parent=None):
        super().__init__(parent)
        self.setObjectName("searchPage")

        self._on_select_track = on_select_track
        self._backend_url = os.getenv("CRATES_BACKEND_URL", "http://127.0.0.1:8000").rstrip(
            "/"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 24)
        root.setSpacing(14)

        # --- Search bar ---
        search_frame = QFrame()
        search_frame.setObjectName("searchBarFrame")
        search_frame.setFixedHeight(54)

        bar_layout = QHBoxLayout(search_frame)
        bar_layout.setContentsMargins(0, 0, 0, 0)
        bar_layout.setSpacing(0)

        self._search_input = QLineEdit()
        self._search_input.setObjectName("searchInput")
        self._search_input.setPlaceholderText("поиск . . . .")
        bar_layout.addWidget(self._search_input, stretch=1)

        btn_search = QPushButton()
        btn_search.setObjectName("btnSearch")
        btn_search.setFixedSize(60, 54)
        btn_search.setIcon(QIcon(_ICON_SEARCH))
        btn_search.setIconSize(QSize(28, 26))

        bar_layout.addWidget(btn_search)
        btn_search.clicked.connect(self._on_search_clicked)
        root.addWidget(search_frame)

        # --- Filter buttons ---
        filter_row = QWidget()
        filter_row.setObjectName("filterRow")
        filter_layout = QHBoxLayout(filter_row)
        filter_layout.setContentsMargins(0, 0, 0, 0)
        filter_layout.setSpacing(10)

        self._filter_btns: list[QPushButton] = []
        for label in _FILTER_LABELS:
            btn = QPushButton(label)
            btn.setObjectName("btnFilter")
            btn.setCheckable(True)
            btn.clicked.connect(self._on_filter_clicked)
            filter_layout.addWidget(btn)
            self._filter_btns.append(btn)

        if self._filter_btns:
            self._filter_btns[0].setChecked(True)

        filter_layout.addStretch()
        root.addWidget(filter_row)

        # --- History label ---
        history_label = QLabel("недавние запросы")
        history_label.setObjectName("historyLabel")
        root.addWidget(history_label)

        # --- History list ---
        self._history_list = QListWidget()
        self._history_list.setObjectName("searchHistory")
        self._history_list.setSpacing(4)
        for item_text in _PLACEHOLDER_HISTORY:
            self._history_list.addItem(QListWidgetItem(item_text))
        n = len(_PLACEHOLDER_HISTORY)
        self._history_list.setFixedHeight(n * 44 + (n + 1) * 4)
        root.addWidget(self._history_list)

        # --- Search results ---
        results_label = QLabel("результаты")
        results_label.setObjectName("searchResultsLabel")
        root.addWidget(results_label)

        self._results_list = QListWidget()
        self._results_list.setObjectName("searchResults")
        self._results_list.setSpacing(4)
        self._results_list.itemClicked.connect(self._on_result_clicked)
        root.addWidget(self._results_list)

        root.addStretch()

    def _on_filter_clicked(self):
        sender = self.sender()
        for btn in self._filter_btns:
            if btn is not sender:
                btn.setChecked(False)

    def _on_search_clicked(self):
        q = self._search_input.text().strip()
        if not q:
            return
        self._results_list.clear()
        try:
            # Локальный запрос к backend обычно очень быстрый, а такой путь
            # гарантированно обновляет QListWidget в UI-потоке.
            url = f"{self._backend_url}/api/music-items/?q={quote_plus(q)}"
            req = Request(url, headers={"Accept": "application/json"})
            with urlopen(req, timeout=10) as resp:
                raw = resp.read().decode("utf-8")
                data = json.loads(raw)
            items = data.get("results", data) if isinstance(data, dict) else data
            if not isinstance(items, list):
                items = []
        except Exception:
            items = []

        for it in items:
            title = it.get("title") or "Без названия"
            artist = it.get("artist") or ""
            label = f"{title} — {artist}".strip(" —")
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, it)
            self._results_list.addItem(item)

    def _on_result_clicked(self, item: QListWidgetItem):
        if not self._on_select_track:
            return
        music_item = item.data(Qt.ItemDataRole.UserRole) or {}
        self._on_select_track(music_item)
