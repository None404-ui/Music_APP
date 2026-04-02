"""
Абстрактный статичный фон: тёмная база, мягкие пятна, линии, лёгкий grain.
Под всеми вкладками (без анимации — один пересчёт при resize).
"""

from __future__ import annotations

import random
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPainter, QPen, QRadialGradient
from PyQt6.QtWidgets import QStackedWidget, QWidget, QSizePolicy


class AmbientBackground(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        random.seed(42)
        self._grain: list[tuple[int, int, int]] = [
            (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
            for _ in range(900)
        ]

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        if w < 2 or h < 2:
            p.end()
            return

        p.fillRect(self.rect(), QColor(18, 12, 28))

        blobs = [
            (w * 0.22, h * 0.35, max(w, h) * 0.55, QColor(255, 120, 40, 55)),
            (w * 0.78, h * 0.28, max(w, h) * 0.5, QColor(40, 200, 190, 45)),
            (w * 0.55, h * 0.72, max(w, h) * 0.6, QColor(60, 90, 220, 40)),
            (w * 0.1, h * 0.85, max(w, h) * 0.45, QColor(200, 80, 30, 35)),
            (w * 0.9, h * 0.65, max(w, h) * 0.4, QColor(30, 140, 180, 38)),
        ]
        for cx, cy, r, col in blobs:
            grad = QRadialGradient(cx, cy, r)
            grad.setColorAt(0.0, col)
            grad.setColorAt(0.45, QColor(col.red(), col.green(), col.blue(), col.alpha() // 3))
            grad.setColorAt(1.0, QColor(0, 0, 0, 0))
            p.setBrush(grad)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(int(cx - r), int(cy - r), int(r * 2), int(r * 2))

        p.setPen(QPen(QColor(255, 160, 80, 25), 3))
        for i in range(5):
            y = int(h * (0.15 + i * 0.18))
            p.drawLine(0, y, w, y + int(12 + i * 4))

        p.setPen(QPen(QColor(50, 200, 200, 18), 2))
        for i in range(4):
            x = int(w * (0.1 + i * 0.22))
            p.drawLine(x, 0, x + 40, h)

        p.setPen(Qt.PenStyle.NoPen)
        step = 6
        idx = 0
        for y in range(0, h, step):
            for x in range(0, w, step):
                r, g, b = self._grain[idx % len(self._grain)]
                idx += 1
                p.setBrush(QColor(r, g, b, 14))
                p.drawRect(x, y, 2, 2)

        p.end()


class ContentWithAmbient(QWidget):
    """Стек вкладок поверх AmbientBackground."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._bg = AmbientBackground(self)
        self.page_stack = QStackedWidget(self)
        self.page_stack.setObjectName("pageStack")
        self.page_stack.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        r = self.rect()
        self._bg.setGeometry(r)
        self.page_stack.setGeometry(r)
        self.page_stack.raise_()
