"""
Абстрактный статичный фон: тёмная база, мягкие пятна, линии, лёгкий grain.
Под всеми вкладками (без анимации — один пересчёт при resize).
"""

from __future__ import annotations

import os
import random
from PyQt6.QtCore import QEvent, Qt, QTimer, QSize, pyqtProperty
from PyQt6.QtGui import QColor, QPainter, QPen, QPixmap, QRadialGradient
from PyQt6.QtWidgets import QStackedWidget, QWidget, QSizePolicy


class AmbientBackground(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ambientBackground")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._base_color = QColor(18, 12, 28)
        self._blob_warm_color = QColor(255, 120, 40, 55)
        self._blob_cool_color = QColor(40, 200, 190, 45)
        self._blob_deep_color = QColor(60, 90, 220, 40)
        self._blob_rust_color = QColor(200, 80, 30, 35)
        self._blob_blue_color = QColor(30, 140, 180, 38)
        self._line_warm_color = QColor(255, 160, 80, 25)
        self._line_cool_color = QColor(50, 200, 200, 18)
        self._grain_alpha = 14
        random.seed(42)
        self._grain: list[tuple[int, int, int]] = [
            (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
            for _ in range(900)
        ]
        self._cache = QPixmap()
        self._rebuild_timer = QTimer(self)
        self._rebuild_timer.setSingleShot(True)
        self._rebuild_timer.setInterval(120)
        self._rebuild_timer.timeout.connect(self._rebuild_cache)

    def _render_size(self, w: int, h: int) -> tuple[int, int]:
        area = max(1, int(w) * int(h))
        if area <= 1_200_000:
            return int(w), int(h)
        scale = (1_200_000 / area) ** 0.5
        return max(1, int(w * scale)), max(1, int(h * scale))

    def _rebuild_cache(self) -> None:
        w, h = self.width(), self.height()
        if w < 2 or h < 2:
            self._cache = QPixmap()
            return

        rw, rh = self._render_size(w, h)
        pm = QPixmap(rw, rh)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        p.fillRect(pm.rect(), self._base_color)

        blobs = [
            (rw * 0.22, rh * 0.35, max(rw, rh) * 0.55, self._blob_warm_color),
            (rw * 0.78, rh * 0.28, max(rw, rh) * 0.5, self._blob_cool_color),
            (rw * 0.55, rh * 0.72, max(rw, rh) * 0.6, self._blob_deep_color),
            (rw * 0.1, rh * 0.85, max(rw, rh) * 0.45, self._blob_rust_color),
            (rw * 0.9, rh * 0.65, max(rw, rh) * 0.4, self._blob_blue_color),
        ]
        for cx, cy, r, col in blobs:
            grad = QRadialGradient(cx, cy, r)
            grad.setColorAt(0.0, col)
            grad.setColorAt(
                0.45, QColor(col.red(), col.green(), col.blue(), col.alpha() // 3)
            )
            grad.setColorAt(1.0, QColor(0, 0, 0, 0))
            p.setBrush(grad)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(int(cx - r), int(cy - r), int(r * 2), int(r * 2))

        p.setPen(QPen(self._line_warm_color, 3))
        for i in range(5):
            y = int(rh * (0.15 + i * 0.18))
            p.drawLine(0, y, rw, y + int(12 + i * 4))

        p.setPen(QPen(self._line_cool_color, 2))
        for i in range(4):
            x = int(rw * (0.1 + i * 0.22))
            p.drawLine(x, 0, x + 40, rh)

        p.setPen(Qt.PenStyle.NoPen)
        step = 6
        idx = 0
        for y in range(0, rh, step):
            for x in range(0, rw, step):
                r, g, b = self._grain[idx % len(self._grain)]
                idx += 1
                p.setBrush(QColor(r, g, b, self._grain_alpha))
                p.drawRect(x, y, 2, 2)

        p.end()
        self._cache = pm

    def _set_theme_color(self, attr: str, color: QColor) -> None:
        setattr(self, attr, QColor(color))
        self._rebuild_cache()
        self.update()

    def _get_base_color(self) -> QColor:
        return QColor(self._base_color)

    def _set_base_color(self, color: QColor) -> None:
        self._set_theme_color("_base_color", color)

    def _get_blob_warm_color(self) -> QColor:
        return QColor(self._blob_warm_color)

    def _set_blob_warm_color(self, color: QColor) -> None:
        self._set_theme_color("_blob_warm_color", color)

    def _get_blob_cool_color(self) -> QColor:
        return QColor(self._blob_cool_color)

    def _set_blob_cool_color(self, color: QColor) -> None:
        self._set_theme_color("_blob_cool_color", color)

    def _get_blob_deep_color(self) -> QColor:
        return QColor(self._blob_deep_color)

    def _set_blob_deep_color(self, color: QColor) -> None:
        self._set_theme_color("_blob_deep_color", color)

    def _get_blob_rust_color(self) -> QColor:
        return QColor(self._blob_rust_color)

    def _set_blob_rust_color(self, color: QColor) -> None:
        self._set_theme_color("_blob_rust_color", color)

    def _get_blob_blue_color(self) -> QColor:
        return QColor(self._blob_blue_color)

    def _set_blob_blue_color(self, color: QColor) -> None:
        self._set_theme_color("_blob_blue_color", color)

    def _get_line_warm_color(self) -> QColor:
        return QColor(self._line_warm_color)

    def _set_line_warm_color(self, color: QColor) -> None:
        self._set_theme_color("_line_warm_color", color)

    def _get_line_cool_color(self) -> QColor:
        return QColor(self._line_cool_color)

    def _set_line_cool_color(self, color: QColor) -> None:
        self._set_theme_color("_line_cool_color", color)

    def _get_grain_alpha(self) -> int:
        return int(self._grain_alpha)

    def _set_grain_alpha(self, alpha: int) -> None:
        self._grain_alpha = max(0, min(255, int(alpha)))
        self._rebuild_cache()
        self.update()

    baseColor = pyqtProperty(QColor, _get_base_color, _set_base_color)
    blobWarmColor = pyqtProperty(QColor, _get_blob_warm_color, _set_blob_warm_color)
    blobCoolColor = pyqtProperty(QColor, _get_blob_cool_color, _set_blob_cool_color)
    blobDeepColor = pyqtProperty(QColor, _get_blob_deep_color, _set_blob_deep_color)
    blobRustColor = pyqtProperty(QColor, _get_blob_rust_color, _set_blob_rust_color)
    blobBlueColor = pyqtProperty(QColor, _get_blob_blue_color, _set_blob_blue_color)
    lineWarmColor = pyqtProperty(QColor, _get_line_warm_color, _set_line_warm_color)
    lineCoolColor = pyqtProperty(QColor, _get_line_cool_color, _set_line_cool_color)
    grainAlpha = pyqtProperty(int, _get_grain_alpha, _set_grain_alpha)

    def paintEvent(self, event) -> None:
        del event
        if self._cache.isNull():
            return
        p = QPainter(self)
        p.drawPixmap(self.rect(), self._cache)
        p.end()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._cache.isNull():
            self._rebuild_cache()
            return
        self._rebuild_timer.start()


class PlayerBackgroundFill(QWidget):
    """Full-page player background: color or image, drawn without Qt stylesheet."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._color = QColor(0, 0, 0, 0)
        self._image_path = ""
        self._pixmap = QPixmap()
        self._scaled_cache = QPixmap()
        self._last_scaled_for = QSize(0, 0)
        self._scale_timer = QTimer(self)
        self._scale_timer.setSingleShot(True)
        self._scale_timer.setInterval(80)
        self._scale_timer.timeout.connect(self._rebuild_scaled_cache)

    def apply_state(self, state) -> None:
        self._image_path = ""
        self._pixmap = QPixmap()
        self._scaled_cache = QPixmap()
        self._last_scaled_for = QSize(0, 0)
        rgba = getattr(state, "page_color_rgba", (0, 0, 0, 0))
        self._color = QColor(rgba[0], rgba[1], rgba[2], rgba[3])
        if getattr(state, "page_mode", "") == "image":
            path = (getattr(state, "page_image_path", "") or "").strip()
            if path and os.path.isfile(path):
                pm = QPixmap(path)
                if not pm.isNull():
                    self._image_path = os.path.normpath(path)
                    self._pixmap = pm
        if not self._pixmap.isNull():
            self._rebuild_scaled_cache_for_size(self.size())
        self.update()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if not self._pixmap.isNull():
            self._scale_timer.start()

    def _rebuild_scaled_cache(self) -> None:
        self._rebuild_scaled_cache_for_size(self.size())

    def _rebuild_scaled_cache_for_size(self, size: QSize) -> None:
        if (
            not self._scaled_cache.isNull()
            and size == self._last_scaled_for
        ):
            return
        if self._pixmap.isNull() or size.width() < 2 or size.height() < 2:
            self._scaled_cache = QPixmap()
            self._last_scaled_for = QSize(0, 0)
            return
        self._scaled_cache = self._pixmap.scaled(
            size,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._last_scaled_for = QSize(size)

    def paintEvent(self, event) -> None:
        del event
        p = QPainter(self)
        if not self._pixmap.isNull():
            if not self._scaled_cache.isNull():
                scaled = self._scaled_cache
                x = int((self.width() - scaled.width()) / 2)
                y = int((self.height() - scaled.height()) / 2)
                p.drawPixmap(x, y, scaled)
        elif self._color.alpha() > 0:
            p.fillRect(self.rect(), self._color)
        p.end()


class ContentWithAmbient(QWidget):
    """Стек вкладок поверх AmbientBackground; опционально слой ambientPlayerFill (свой фон вкладки «Плеер»)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._bg = AmbientBackground(self)
        self._bg_fill = PlayerBackgroundFill(self)
        self._bg_fill.setObjectName("ambientPlayerFill")
        self._bg_fill.hide()
        self.page_stack = QStackedWidget(self)
        self._top_banner: QWidget | None = None
        self._top_banner_height = 124
        self._top_banner_margin = 16
        self._overlay: QWidget | None = None
        self._overlay_height = 94
        self._overlay_margin = 16
        self.page_stack.setObjectName("pageStack")
        self.page_stack.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        # Прозрачность стека задаётся в QSS, чтобы тема могла управлять фоном.
        self.page_stack.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

    def apply_player_background(self, state) -> None:
        """Подменяет фон за плеером (цвет/картинка) вместо оранжево-синего ambient."""
        if state.page_mode == "default":
            self._bg_fill.hide()
            self._bg.show()
            return
        self._bg_fill.apply_state(state)
        self._bg_fill.show()
        # Градиентный ambient остаётся под слоем: при полупрозрачном цвете страницы (по умолчанию)
        # он снова виден; непрозрачный цвет или картинка на ambientPlayerFill всё равно перекроют его.
        self._bg.show()

    def clear_player_background(self) -> None:
        """Снова показывать стандартный ambient (другие вкладки)."""
        self._bg_fill.hide()
        self._bg.show()

    def set_top_banner_widget(
        self,
        widget: QWidget,
        *,
        height: int = 124,
        margin: int = 16,
    ) -> None:
        if self._top_banner is not None:
            self._top_banner.removeEventFilter(self)
        self._top_banner = widget
        self._top_banner_height = height
        self._top_banner_margin = margin
        widget.setParent(self)
        widget.installEventFilter(self)
        widget.hide()
        self._layout_layers()

    def set_overlay_widget(self, widget: QWidget, *, height: int = 94, margin: int = 16) -> None:
        if self._overlay is not None:
            self._overlay.removeEventFilter(self)
        self._overlay = widget
        self._overlay_height = height
        self._overlay_margin = margin
        widget.setParent(self)
        widget.installEventFilter(self)
        widget.hide()
        self._layout_layers()

    def overlay_widget(self) -> QWidget | None:
        return self._overlay

    def set_overlay_visible(self, visible: bool) -> None:
        if self._overlay is None:
            return
        self._overlay.setVisible(visible)
        self._layout_layers()

    def eventFilter(self, watched, event) -> bool:
        if watched in (self._overlay, self._top_banner) and event.type() in (
            QEvent.Type.Show,
            QEvent.Type.Hide,
        ):
            QTimer.singleShot(0, self._layout_layers)
        return super().eventFilter(watched, event)

    def _content_top_reserve(self) -> int:
        if self._top_banner is None or self._top_banner.isHidden():
            return 0
        return self._top_banner_height + self._top_banner_margin

    def _content_bottom_reserve(self) -> int:
        if self._overlay is None or self._overlay.isHidden():
            return 0
        return self._overlay_height + self._overlay_margin

    def _layout_layers(self) -> None:
        r = self.rect()
        self._bg.setGeometry(r)
        self._bg_fill.setGeometry(r)
        top_reserve = self._content_top_reserve()
        bottom_reserve = self._content_bottom_reserve()
        self.page_stack.setGeometry(
            0,
            top_reserve,
            r.width(),
            max(0, r.height() - top_reserve - bottom_reserve),
        )
        self._bg_fill.raise_()
        self.page_stack.raise_()
        self._layout_top_banner()
        self._layout_overlay()

    def _layout_top_banner(self) -> None:
        if self._top_banner is None:
            return
        w = max(180, self.width() - self._top_banner_margin * 2)
        h = self._top_banner_height
        x = self._top_banner_margin
        y = self._top_banner_margin
        self._top_banner.setGeometry(x, y, w, h)
        if self._top_banner.isVisible():
            self._top_banner.raise_()

    def _layout_overlay(self) -> None:
        if self._overlay is None:
            return
        w = max(180, self.width() - self._overlay_margin * 2)
        h = self._overlay_height
        x = self._overlay_margin
        y = max(self._overlay_margin, self.height() - h - self._overlay_margin)
        self._overlay.setGeometry(x, y, w, h)
        if self._overlay.isVisible():
            self._overlay.raise_()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._layout_layers()
