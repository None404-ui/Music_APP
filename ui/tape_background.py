"""
Фон в духе бумажной вставки кассеты (J-card): тёплый беж, мягкие бирюзовые пятна, лёгкое зерно.
"""

from __future__ import annotations

from PyQt6.QtCore import QPointF, QRect, QRectF
from PyQt6.QtGui import QColor, QImage, QLinearGradient, QPainter, QPen, QPixmap, QRadialGradient

_noise_tile: QPixmap | None = None


def _get_noise_tile() -> QPixmap:
    global _noise_tile
    if _noise_tile is None:
        img = QImage(96, 96, QImage.Format.Format_ARGB32)
        img.fill(QColor(0, 0, 0, 0))
        for y in range(96):
            for x in range(96):
                n = ((x * 47 + y * 83) ^ (x * y + 13)) & 0xFF
                a = 8 + (n % 22)
                img.setPixelColor(x, y, QColor(45, 38, 28, a))
        _noise_tile = QPixmap.fromImage(img)
    return _noise_tile


def paint_cassette_jcard(painter: QPainter, rect: QRect | QRectF) -> None:
    """Залить rect фоном: градиент «бумаги», органические пятна, зерно."""
    if isinstance(rect, QRectF):
        r = rect
    else:
        r = QRectF(rect)

    w, h = r.width(), r.height()
    if w <= 0 or h <= 0:
        return

    # База — тёплая кремовая «бумага» J-card
    base = QLinearGradient(r.topLeft(), r.bottomRight())
    base.setColorAt(0.0, QColor("#EDE6CC"))
    base.setColorAt(0.45, QColor("#E2D8B8"))
    base.setColorAt(1.0, QColor("#D8CEA8"))
    painter.fillRect(r, base)

    # Мягкие «разводы» 70-х: мята / морская волна, полупрозрачные
    blobs: list[tuple[float, float, float, QColor]] = [
        (0.12 * w, 0.08 * h, 0.55 * max(w, h), QColor(110, 168, 158, 42)),
        (0.82 * w, 0.18 * h, 0.45 * max(w, h), QColor(130, 185, 175, 38)),
        (0.55 * w, 0.62 * h, 0.65 * max(w, h), QColor(95, 150, 145, 34)),
        (0.25 * w, 0.75 * h, 0.40 * max(w, h), QColor(120, 175, 165, 28)),
        (0.92 * w, 0.85 * h, 0.35 * max(w, h), QColor(100, 155, 148, 26)),
    ]
    for cx, cy, rad, col in blobs:
        grad = QRadialGradient(QPointF(r.x() + cx, r.y() + cy), rad)
        grad.setColorAt(0.0, col)
        grad.setColorAt(0.55, QColor(col.red(), col.green(), col.blue(), col.alpha() // 3))
        grad.setColorAt(1.0, QColor(col.red(), col.green(), col.blue(), 0))
        painter.fillRect(r, grad)

    # Лёгкий виньетирующий крем (глубина)
    vignette = QRadialGradient(r.center(), max(w, h) * 0.72)
    vignette.setColorAt(0.0, QColor(255, 248, 230, 0))
    vignette.setColorAt(1.0, QColor(120, 100, 70, 28))
    painter.fillRect(r, vignette)

    # Плёночное зерно (тайл)
    painter.setOpacity(0.85)
    tile = _get_noise_tile()
    left, top = int(r.left()), int(r.top())
    tw, th = tile.width(), tile.height()
    y = top
    while y < r.bottom():
        x = left
        while x < r.right():
            painter.drawPixmap(x, y, tile)
            x += tw
        y += th
    painter.setOpacity(1.0)

    # Тонкая линия «печати» — едва заметная сетка эпохи
    pen = QPen(QColor(90, 120, 115, 18))
    pen.setWidth(1)
    painter.setPen(pen)
    step = 48
    yy = int(r.top()) + step
    while yy < r.bottom():
        painter.drawLine(int(r.left()), yy, int(r.right()), yy)
        yy += step


class CassetteBackgroundMixin:
    """Подмешать в класс вкладки (первым базовым классом): рисует J-card под дочерними виджетами."""

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        paint_cassette_jcard(p, self.rect())
        p.end()
