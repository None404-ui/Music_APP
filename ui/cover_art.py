from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt, QRectF, QSize
from PyQt6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap, QBrush
from PyQt6.QtWidgets import QWidget


class CoverArtWidget(QWidget):
    """Обложка с квадратной областью и маской, перекрывающей углы."""

    def __init__(
        self,
        *,
        radius: int = 6,
        border_width: int = 1,
        border_color: QColor | None = None,
        fill_color: QColor | None = None,
        mask_color: QColor | None = None,
        placeholder_text: str = "♪",
        placeholder_color: QColor | None = None,
        placeholder_px: int = 20,
        placeholder_font: str = "Courier New",
        top_align_square: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAutoFillBackground(False)
        self._pm: Optional[QPixmap] = None
        self._radius = radius
        self._border_width = border_width
        self._border_color = border_color or QColor("#000000")
        self._fill_color = fill_color
        self._mask_color = mask_color
        self._placeholder_text = placeholder_text
        self._placeholder_color = placeholder_color or QColor("#000000")
        self._placeholder_font = QFont(placeholder_font)
        self._placeholder_px = placeholder_px
        self._placeholder_scale: Optional[float] = None
        self._placeholder_min: Optional[int] = None
        self._placeholder_max: Optional[int] = None
        self._fill_gradient: Optional[tuple[QColor, QColor]] = None
        self._top_align_square = top_align_square

    def set_cover_pixmap(self, pm: Optional[QPixmap]) -> None:
        self._pm = None if pm is None or pm.isNull() else pm
        self.update()

    def clear_cover(self) -> None:
        self._pm = None
        self.update()

    def set_placeholder(
        self,
        text: str,
        *,
        color: Optional[QColor] = None,
        font_px: Optional[int] = None,
        font_family: Optional[str] = None,
    ) -> None:
        self._placeholder_text = text
        if color is not None:
            self._placeholder_color = color
        if font_px is not None:
            self._placeholder_px = font_px
        if font_family is not None:
            self._placeholder_font = QFont(font_family)
        self.update()

    def set_placeholder_scale(
        self,
        scale: float,
        *,
        min_px: Optional[int] = None,
        max_px: Optional[int] = None,
    ) -> None:
        self._placeholder_scale = scale
        self._placeholder_min = min_px
        self._placeholder_max = max_px
        self.update()

    def set_fill_gradient(self, start: QColor, end: QColor) -> None:
        self._fill_gradient = (start, end)
        self.update()

    def set_style_colors(
        self,
        *,
        border_color: Optional[QColor] = None,
        fill_color: Optional[QColor] = None,
        mask_color: Optional[QColor] = None,
    ) -> None:
        if border_color is not None:
            self._border_color = border_color
        if fill_color is not None:
            self._fill_color = fill_color
        if mask_color is not None:
            self._mask_color = mask_color
        self.update()

    def set_radius(self, radius: int) -> None:
        self._radius = radius
        self.update()

    def set_border_width(self, width: int) -> None:
        self._border_width = width
        self.update()

    def set_top_align_square(self, enabled: bool) -> None:
        self._top_align_square = enabled
        self.update()

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return width

    def sizeHint(self) -> QSize:
        base = self.minimumSize()
        side = max(64, base.width(), base.height())
        return QSize(side, side)

    def minimumSizeHint(self) -> QSize:
        base = self.minimumSize()
        side = max(0, base.width(), base.height())
        return QSize(side, side)

    def _square_rect(self) -> QRectF:
        rect = QRectF(self.rect())
        side = min(rect.width(), rect.height())
        if side <= 0:
            return QRectF()
        x = rect.x() + (rect.width() - side) / 2.0
        if self._top_align_square:
            y = rect.y()
        else:
            y = rect.y() + (rect.height() - side) / 2.0
        return QRectF(x, y, side, side)

    def _fill_cover_rect(self, painter: QPainter, rect: QRectF) -> None:
        if self._fill_gradient is not None:
            grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
            grad.setColorAt(0, self._fill_gradient[0])
            grad.setColorAt(1, self._fill_gradient[1])
            painter.fillRect(rect, QBrush(grad))
        elif self._fill_color is not None:
            painter.fillRect(rect, self._fill_color)

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        full = QRectF(self.rect())
        if full.width() < 2 or full.height() < 2:
            painter.end()
            return

        outer = self._square_rect()
        if outer.isNull():
            painter.end()
            return

        bw = max(0.0, float(self._border_width))
        inset = bw / 2.0
        inner = outer.adjusted(inset, inset, -inset, -inset)
        radius = float(self._radius)
        if inner.width() > 0 and inner.height() > 0:
            max_radius = min(inner.width(), inner.height()) / 2.0
            radius = min(radius, max_radius)

        clip = QPainterPath()
        clip.addRoundedRect(inner, radius, radius)
        painter.save()
        painter.setClipPath(clip)
        self._fill_cover_rect(painter, inner)

        if self._pm is not None:
            tw, th = max(1, int(inner.width())), max(1, int(inner.height()))
            scaled = self._pm.scaled(
                tw,
                th,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = int(inner.x() + (inner.width() - scaled.width()) / 2)
            y = int(inner.y() + (inner.height() - scaled.height()) / 2)
            painter.drawPixmap(x, y, scaled)
        else:
            font = QFont(self._placeholder_font)
            font_px = self._placeholder_px
            if self._placeholder_scale is not None:
                font_px = int(inner.width() * self._placeholder_scale)
                if self._placeholder_min is not None:
                    font_px = max(font_px, self._placeholder_min)
                if self._placeholder_max is not None:
                    font_px = min(font_px, self._placeholder_max)
            font.setPixelSize(max(8, font_px))
            painter.setFont(font)
            painter.setPen(self._placeholder_color)
            painter.drawText(inner.toRect(), Qt.AlignmentFlag.AlignCenter, self._placeholder_text)
        painter.restore()

        if bw > 0:
            pen = QPen(self._border_color)
            pen.setWidthF(bw)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(inner, radius, radius)

        painter.end()
