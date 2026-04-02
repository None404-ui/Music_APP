import os

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
    def __init__(self, parent=None, on_select_track=None):
        super().__init__(parent)
        self.setObjectName("searchPage")
        self._on_select_track = on_select_track

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

        root.addStretch()

    def _on_filter_clicked(self):
        sender = self.sender()
        for btn in self._filter_btns:
            if btn is not sender:
                btn.setChecked(False)
