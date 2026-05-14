"""Скрытие вертикального скроллбара у страничного QScrollArea до взаимодействия."""

from __future__ import annotations

from PyQt6.QtCore import QEvent, QObject, QTimer, Qt
from PyQt6.QtWidgets import QScrollArea


class _TransientVerticalScrollController(QObject):
    """Полоса скрыта, пока нет прокрутки; показ по колесу / ползунку / наведению на полосу."""

    def __init__(self, area: QScrollArea, *, hide_delay_ms: int = 1200) -> None:
        super().__init__(area)
        self._area = area
        self._hide_delay_ms = hide_delay_ms
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._on_hide_timeout)

        area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        vbar = area.verticalScrollBar()
        vbar.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        vbar.rangeChanged.connect(self._on_range_changed)
        vbar.sliderPressed.connect(self._on_slider_pressed)
        vbar.sliderReleased.connect(self._on_slider_released)

        area.viewport().installEventFilter(self)
        vbar.installEventFilter(self)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        et = event.type()
        if watched is self._area.viewport() and et == QEvent.Type.Wheel:
            self._reveal()
            self._schedule_hide()
        elif watched is self._area.verticalScrollBar():
            if et == QEvent.Type.HoverEnter:
                self._reveal()
                self._timer.stop()
            elif et == QEvent.Type.HoverLeave:
                self._schedule_hide()
        return False

    def _scrollable(self) -> bool:
        bar = self._area.verticalScrollBar()
        return bar.maximum() > bar.minimum()

    def _on_range_changed(self, _min: int, _max: int) -> None:
        bar = self._area.verticalScrollBar()
        if not self._scrollable():
            self._timer.stop()
            bar.hide()
        elif not bar.isSliderDown():
            bar.hide()

    def _reveal(self) -> None:
        if self._scrollable():
            self._area.verticalScrollBar().show()

    def _schedule_hide(self) -> None:
        if self._scrollable():
            self._timer.start(self._hide_delay_ms)

    def _on_hide_timeout(self) -> None:
        bar = self._area.verticalScrollBar()
        if bar.isSliderDown():
            self._schedule_hide()
            return
        bar.hide()

    def _on_slider_pressed(self) -> None:
        self._reveal()
        self._timer.stop()

    def _on_slider_released(self) -> None:
        self._schedule_hide()


def enable_transient_vertical_page_scroll(
    area: QScrollArea, *, hide_delay_ms: int = 1200
) -> None:
    """Вешает контроллер на корневой QScrollArea вкладки (один раз на виджет)."""
    if getattr(area, "_transient_page_scroll_installed", False):
        return
    area._transient_page_scroll_installed = True  # type: ignore[attr-defined]
    _TransientVerticalScrollController(area, hide_delay_ms=hide_delay_ms)
