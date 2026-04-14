from __future__ import annotations

from functools import lru_cache

from PyQt6.QtCore import QEasingCurve, QEvent, QPropertyAnimation, QSize, Qt, QTimer, QVariantAnimation
from PyQt6.QtGui import QColor, QCursor, QPainter, QPainterPath, QPen, QPixmap, QIcon
from PyQt6.QtWidgets import QFrame, QGraphicsOpacityEffect, QPushButton, QScrollBar, QStackedWidget, QWidget

try:
    from PyQt6.QtSvg import QSvgRenderer
except ImportError:
    QSvgRenderer = None  # type: ignore[assignment]


def _keep_animation(owner: object, key: str, animation) -> None:
    bucket = getattr(owner, "_fx_animations", None)
    if bucket is None:
        bucket = {}
        setattr(owner, "_fx_animations", bucket)
    prev = bucket.get(key)
    if prev is not None:
        try:
            prev.stop()
        except Exception:
            pass
    bucket[key] = animation

    def _cleanup() -> None:
        cur = getattr(owner, "_fx_animations", {})
        if cur.get(key) is animation:
            cur.pop(key, None)

    animation.finished.connect(_cleanup)


@lru_cache(maxsize=128)
def _svg_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


@lru_cache(maxsize=512)
def _colored_icon_cache(path: str, color_hex: str, width: int, height: int) -> QIcon:
    if QSvgRenderer is None:
        return QIcon(path)
    svg = _svg_text(path).replace("currentColor", color_hex)
    renderer = QSvgRenderer(svg.encode("utf-8"))
    pix = QPixmap(max(1, width), max(1, height))
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    renderer.render(p)
    p.end()
    return QIcon(pix)


def colored_svg_icon(path: str, color: QColor | str, size: QSize) -> QIcon:
    qcolor = QColor(color)
    return _colored_icon_cache(
        path,
        qcolor.name(QColor.NameFormat.HexRgb),
        max(1, int(size.width())),
        max(1, int(size.height())),
    )


class StatefulIconButton(QPushButton):
    """SVG-кнопка с явными icon-state и коротким pulse вместо ненадёжной QSS-перекраски."""

    def __init__(
        self,
        icon_path: str,
        *,
        checked_icon_path: str | None = None,
        base_color: str = "#312938",
        hover_color: str = "#A14016",
        pressed_color: str = "#CB883A",
        checked_color: str = "#CB883A",
        disabled_color: str = "#7E776B",
        pulse_on_click: bool = True,
        pulse_on_toggle: bool = True,
        parent=None,
    ):
        super().__init__(parent)
        self._icon_path = icon_path
        self._checked_icon_path = checked_icon_path or icon_path
        self._base_color = QColor(base_color)
        self._hover_color = QColor(hover_color)
        self._pressed_color = QColor(pressed_color)
        self._checked_color = QColor(checked_color)
        self._disabled_color = QColor(disabled_color)
        self._pulse_on_click = pulse_on_click
        self._pulse_on_toggle = pulse_on_toggle
        self._hovered = False
        self._pressed = False
        self._base_icon_size = QSize(22, 22)

        self._pulse = QVariantAnimation(self)
        self._pulse.setDuration(150)
        self._pulse.setStartValue(0.0)
        self._pulse.setEndValue(1.0)
        self._pulse.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._pulse.valueChanged.connect(self._apply_pulse_frame)
        self._pulse.finished.connect(self._restore_base_icon)

        self.toggled.connect(self._on_toggled)
        self.clicked.connect(self._on_clicked)
        self._refresh_icon()

    def setIconSize(self, size: QSize) -> None:
        self._base_icon_size = QSize(size)
        super().setIconSize(size)
        self._refresh_icon()

    def setChecked(self, checked: bool) -> None:
        super().setChecked(checked)
        self._refresh_icon()

    def setEnabled(self, enabled: bool) -> None:
        super().setEnabled(enabled)
        self._refresh_icon()

    def set_icon_paths(
        self,
        icon_path: str,
        checked_icon_path: str | None = None,
    ) -> None:
        self._icon_path = icon_path
        self._checked_icon_path = checked_icon_path or icon_path
        self._refresh_icon()

    def changeEvent(self, event) -> None:
        super().changeEvent(event)
        if event.type() == QEvent.Type.EnabledChange:
            self._refresh_icon()

    def enterEvent(self, event) -> None:
        self._hovered = True
        self._refresh_icon()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovered = False
        self._pressed = False
        self._refresh_icon()
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._pressed = True
            self._refresh_icon()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._pressed = False
        self._refresh_icon()
        super().mouseReleaseEvent(event)

    def _icon_path_for_state(self) -> str:
        if self.isCheckable() and self.isChecked():
            return self._checked_icon_path
        return self._icon_path

    def _color_for_state(self) -> QColor:
        if not self.isEnabled():
            return QColor(self._disabled_color)
        if self._pressed:
            return QColor(self._pressed_color)
        if self.isCheckable() and self.isChecked():
            return QColor(self._checked_color)
        if self._hovered:
            return QColor(self._hover_color)
        return QColor(self._base_color)

    def _refresh_icon(self) -> None:
        size = self.iconSize()
        if size.width() <= 0 or size.height() <= 0:
            size = QSize(self._base_icon_size)
            super().setIconSize(size)
        self.setIcon(colored_svg_icon(self._icon_path_for_state(), self._color_for_state(), size))

    def _apply_pulse_frame(self, value) -> None:
        t = float(value)
        peak = 1.0 - abs(1.0 - 2.0 * t)
        scale = 1.0 + 0.18 * peak
        size = QSize(
            max(12, int(round(self._base_icon_size.width() * scale))),
            max(12, int(round(self._base_icon_size.height() * scale))),
        )
        super().setIconSize(size)
        self._refresh_icon()

    def _restore_base_icon(self) -> None:
        super().setIconSize(QSize(self._base_icon_size))
        self._refresh_icon()

    def _start_pulse(self) -> None:
        self._pulse.stop()
        self._pulse.start()

    def _on_toggled(self, _checked: bool) -> None:
        self._refresh_icon()
        if self._pulse_on_toggle:
            self._start_pulse()

    def _on_clicked(self, _checked: bool = False) -> None:
        if not self.isCheckable() and self._pulse_on_click:
            self._start_pulse()


class InteractiveRowFrame(QFrame):
    """QFrame со сглаженным hover/press/active overlay, не зависящим от дочерних виджетов."""

    def __init__(
        self,
        *,
        radius: int = 8,
        hover_color: str = "#CB883A",
        press_color: str = "#A14016",
        active_color: str = "#CB883A",
        hover_alpha: int = 34,
        press_alpha: int = 58,
        active_alpha: int = 28,
        parent=None,
    ):
        super().__init__(parent)
        self.setMouseTracking(True)
        self._radius = radius
        self._hover_color = QColor(hover_color)
        self._press_color = QColor(press_color)
        self._active_color = QColor(active_color)
        self._hover_alpha = hover_alpha
        self._press_alpha = press_alpha
        self._active_alpha = active_alpha
        self._feedback = 0.0
        self._hovered = False
        self._pressed = False
        self._active = False

        self._feedback_anim = QVariantAnimation(self)
        self._feedback_anim.setDuration(140)
        self._feedback_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._feedback_anim.valueChanged.connect(self._on_feedback_changed)

    def install_interaction_filters(self) -> None:
        for child in self.findChildren(QWidget):
            if child is self:
                continue
            child.installEventFilter(self)
            child.setMouseTracking(True)

    def set_active(self, active: bool) -> None:
        self._active = bool(active)
        self.update()

    def _target_feedback(self) -> float:
        if self._pressed:
            return 1.0
        if self._hovered:
            return 0.66
        return 0.0

    def _animate_feedback(self) -> None:
        self._feedback_anim.stop()
        self._feedback_anim.setStartValue(self._feedback)
        self._feedback_anim.setEndValue(self._target_feedback())
        self._feedback_anim.start()

    def _on_feedback_changed(self, value) -> None:
        self._feedback = float(value)
        self.update()

    def _refresh_hover_from_cursor(self) -> None:
        local = self.mapFromGlobal(QCursor.pos())
        self._hovered = self.rect().contains(local)
        self._animate_feedback()

    def enterEvent(self, event) -> None:
        self._hovered = True
        self._animate_feedback()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovered = False
        self._pressed = False
        self._animate_feedback()
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._pressed = True
            self._animate_feedback()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._pressed = False
        self._hovered = self.rect().contains(event.position().toPoint())
        self._animate_feedback()
        super().mouseReleaseEvent(event)

    def eventFilter(self, obj, event):
        if isinstance(obj, QWidget) and obj is not self:
            tp = event.type()
            if tp in (QEvent.Type.Enter, QEvent.Type.HoverEnter):
                self._hovered = True
                self._animate_feedback()
            elif tp in (QEvent.Type.Leave, QEvent.Type.HoverLeave):
                QTimer.singleShot(0, self._refresh_hover_from_cursor)
            elif tp == QEvent.Type.MouseButtonPress and getattr(event, "button", lambda: None)() == Qt.MouseButton.LeftButton:
                self._pressed = True
                self._animate_feedback()
            elif tp == QEvent.Type.MouseButtonRelease and getattr(event, "button", lambda: None)() == Qt.MouseButton.LeftButton:
                self._pressed = False
                QTimer.singleShot(0, self._refresh_hover_from_cursor)
        return super().eventFilter(obj, event)

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        if self._feedback <= 0.001 and not self._active:
            return
        rect = self.rect().adjusted(1, 1, -2, -2)
        if rect.width() <= 2 or rect.height() <= 2:
            return
        path = QPainterPath()
        path.addRoundedRect(float(rect.x()), float(rect.y()), float(rect.width()), float(rect.height()), float(self._radius), float(self._radius))
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self._active:
            fill = QColor(self._active_color)
            fill.setAlpha(self._active_alpha)
            p.fillPath(path, fill)
            pen = QPen(QColor(self._active_color))
            pen.setWidth(2)
            p.setPen(pen)
            p.drawPath(path)
        if self._feedback > 0.001:
            color = QColor(self._press_color if self._pressed else self._hover_color)
            max_alpha = self._press_alpha if self._pressed else self._hover_alpha
            color.setAlpha(int(round(max_alpha * self._feedback)))
            p.fillPath(path, color)
        p.end()


def animate_stack_fade(stack: QStackedWidget, index: int, duration: int = 170) -> None:
    if stack.currentIndex() == index:
        return
    stack.setCurrentIndex(index)
    page = stack.currentWidget()
    if page is None:
        return
    effect = QGraphicsOpacityEffect(page)
    effect.setOpacity(0.0)
    page.setGraphicsEffect(effect)
    animation = QPropertyAnimation(effect, b"opacity", page)
    animation.setDuration(duration)
    animation.setStartValue(0.0)
    animation.setEndValue(1.0)
    animation.setEasingCurve(QEasingCurve.Type.OutCubic)

    def _cleanup() -> None:
        if page.graphicsEffect() is effect:
            page.setGraphicsEffect(None)

    animation.finished.connect(_cleanup)
    _keep_animation(stack, "stack_fade", animation)
    animation.start()


def fade_in_widget(widget: QWidget, duration: int = 170) -> None:
    effect = QGraphicsOpacityEffect(widget)
    effect.setOpacity(0.0)
    widget.setGraphicsEffect(effect)
    animation = QPropertyAnimation(effect, b"opacity", widget)
    animation.setDuration(duration)
    animation.setStartValue(0.0)
    animation.setEndValue(1.0)
    animation.setEasingCurve(QEasingCurve.Type.OutCubic)

    def _cleanup() -> None:
        if widget.graphicsEffect() is effect:
            widget.setGraphicsEffect(None)

    animation.finished.connect(_cleanup)
    _keep_animation(widget, "fade_in", animation)
    animation.start()


def animate_scrollbar_to(bar: QScrollBar, target: int, duration: int = 180) -> None:
    animation = QPropertyAnimation(bar, b"value", bar)
    animation.setDuration(duration)
    animation.setStartValue(bar.value())
    animation.setEndValue(max(bar.minimum(), min(bar.maximum(), int(target))))
    animation.setEasingCurve(QEasingCurve.Type.OutCubic)
    _keep_animation(bar, "scroll_to", animation)
    animation.start()
