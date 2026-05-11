"""Горизонтальный ползунок прогресса: дорожка из QSS/цветов, бегунок — SVG или пиксельный запасной."""

from __future__ import annotations

import os
from typing import Optional

from PyQt6.QtCore import QRectF, Qt, QSize
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QSlider, QStyle, QStyleOptionSlider


class SvgSeekSlider(QSlider):
    """
    Рисует sub-page/groove/add-page вручную; бегунок — из SVG (если путь валиден) или прямоугольник.
    """

    def __init__(
        self,
        compact: bool = False,
        parent=None,
    ):
        super().__init__(Qt.Orientation.Horizontal, parent)
        self._compact = compact
        self._thumb_svg_path: Optional[str] = None
        self._groove = QColor(207, 200, 154)
        self._filled = QColor(161, 64, 22)
        self._border = QColor(49, 41, 56)
        self._thumb_fill = QColor(49, 41, 56)
        self._thumb_border = QColor(203, 136, 58)
        self._renderer: Optional[QSvgRenderer] = None
        self.setMouseTracking(True)

    def set_thumb_svg_path(self, path: Optional[str]) -> None:
        p = (path or "").strip()
        if p and os.path.isfile(p):
            p = os.path.normpath(p)
            if p != self._thumb_svg_path:
                self._thumb_svg_path = p
                self._renderer = QSvgRenderer(p)
        else:
            self._thumb_svg_path = None
            self._renderer = None
        self.update()

    def apply_colors(
        self,
        groove: QColor,
        filled: QColor,
        border: QColor,
        thumb_fill: QColor,
        thumb_border: QColor,
    ) -> None:
        self._groove = groove
        self._filled = filled
        self._border = border
        self._thumb_fill = thumb_fill
        self._thumb_border = thumb_border
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        opt = QStyleOptionSlider()
        self.initStyleOption(opt)
        groove_rect = self.style().subControlRect(
            QStyle.ComplexControl.CC_Slider,
            opt,
            QStyle.SubControl.SC_SliderGroove,
            self,
        )
        handle_rect = self.style().subControlRect(
            QStyle.ComplexControl.CC_Slider,
            opt,
            QStyle.SubControl.SC_SliderHandle,
            self,
        )

        if self._compact:
            gh = 4
        else:
            gh = 8
        gy = groove_rect.center().y() - gh // 2
        gx = groove_rect.x()
        gw = groove_rect.width()

        pen_w = 1 if self._compact else 2
        pen = QPen(self._border)
        pen.setWidth(pen_w)
        painter.setPen(pen)
        painter.setBrush(self._groove)
        painter.drawRect(gx, gy, gw, gh)

        min_v, max_v = self.minimum(), self.maximum()
        span = max(1, max_v - min_v)
        frac = (self.value() - min_v) / span
        filled_w = max(0, int(round(gw * frac)))
        if filled_w > 0:
            painter.setPen(pen)
            painter.setBrush(self._filled)
            painter.drawRect(gx, gy, filled_w, gh)

        cx = handle_rect.center().x()
        cy = groove_rect.center().y()

        if self._renderer is not None and self._renderer.isValid():
            if self._compact:
                size = QSize(16, 12)
            else:
                size = QSize(20, 22)
            x = int(cx - size.width() / 2)
            y = int(cy - size.height() / 2)
            target = QRectF(x, y, size.width(), size.height())
            self._renderer.render(painter, target)
        else:
            if self._compact:
                hw, hh = 8, 10
            else:
                hw, hh = 10, 18
            x = int(cx - hw / 2)
            y = int(cy - hh / 2)
            painter.setPen(QPen(self._thumb_border, 2))
            painter.setBrush(self._thumb_fill)
            painter.drawRect(x, y, hw, hh)
