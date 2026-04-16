from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ui.interactive_fx import animate_stack_fade
from ui import i18n


class HomeHubWidget(QWidget):
    """Популярное и рецензии: переключатель сверху, общий стек контента."""

    sub_page_changed = pyqtSignal(int)

    _SUB_POPULAR = 0
    _SUB_REVIEWS = 1

    def __init__(self, popular_tab: QWidget, reviews_tab: QWidget, parent=None):
        super().__init__(parent)
        self.setObjectName("homeHubPage")

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 8)
        root.setSpacing(8)

        toggle_row = QHBoxLayout()
        toggle_row.setSpacing(8)

        self._btn_popular = QPushButton(i18n.tr("популярное"))
        self._btn_popular.setObjectName("btnNav")
        self._btn_popular.setCheckable(True)

        self._btn_reviews = QPushButton(i18n.tr("рецензии"))
        self._btn_reviews.setObjectName("btnNav")
        self._btn_reviews.setCheckable(True)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._group.addButton(self._btn_popular, self._SUB_POPULAR)
        self._group.addButton(self._btn_reviews, self._SUB_REVIEWS)

        toggle_row.addWidget(self._btn_popular)
        toggle_row.addWidget(self._btn_reviews)
        toggle_row.addStretch()
        root.addLayout(toggle_row)

        self._stack = QStackedWidget()
        self._stack.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self._stack.addWidget(popular_tab)
        self._stack.addWidget(reviews_tab)
        root.addWidget(self._stack, stretch=1)

        self._btn_popular.clicked.connect(self._sync_stack_from_buttons)
        self._btn_reviews.clicked.connect(self._sync_stack_from_buttons)
        self._stack.currentChanged.connect(self.sub_page_changed.emit)

        self._btn_popular.setChecked(True)
        self._stack.setCurrentIndex(self._SUB_POPULAR)

    def _sync_stack_from_buttons(self) -> None:
        if self._btn_popular.isChecked():
            animate_stack_fade(self._stack, self._SUB_POPULAR)
        elif self._btn_reviews.isChecked():
            animate_stack_fade(self._stack, self._SUB_REVIEWS)

    def reset_to_popular(self) -> None:
        self._group.blockSignals(True)
        try:
            self._btn_popular.setChecked(True)
            self._btn_reviews.setChecked(False)
        finally:
            self._group.blockSignals(False)
        self._stack.setCurrentIndex(self._SUB_POPULAR)

    def current_sub_index(self) -> int:
        return self._stack.currentIndex()
