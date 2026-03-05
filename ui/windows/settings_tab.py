from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QScrollArea, QFrame, QSizePolicy, QComboBox,
)
from PyQt6.QtCore import Qt, pyqtProperty, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QPainter, QColor


class ToggleSwitch(QWidget):
    """Animated toggle: circle slides right on activation, track fills beige, circle is blue."""

    toggled = pyqtSignal(bool)

    _OFF_X = 14.0
    _ON_X = 36.0

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(50, 28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._checked = False
        self._circle_x = self._OFF_X

        self._anim = QPropertyAnimation(self, b"circle_x")
        self._anim.setDuration(220)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutCubic)

    # ----- pyqtProperty for QPropertyAnimation -----
    def _get_circle_x(self):
        return self._circle_x

    def _set_circle_x(self, value: float):
        self._circle_x = value
        self.update()

    circle_x = pyqtProperty(float, _get_circle_x, _set_circle_x)

    # ----- public API -----
    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, checked: bool):
        if self._checked != checked:
            self._checked = checked
            self._start_animation(checked)

    # ----- internals -----
    def _start_animation(self, checked: bool):
        self._anim.stop()
        self._anim.setStartValue(self._circle_x)
        self._anim.setEndValue(self._ON_X if checked else self._OFF_X)
        self._anim.start()

    def mousePressEvent(self, event):
        self._checked = not self._checked
        self._start_animation(self._checked)
        self.toggled.emit(self._checked)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        r = h // 2          # 14 — track corner radius
        circle_r = r - 4    # 10 — circle radius

        # Interpolation factor 0.0 (off) → 1.0 (on)
        t = max(0.0, min(1.0, (self._circle_x - self._OFF_X) / (self._ON_X - self._OFF_X)))

        # Track: sage #89A194 (137,161,148) → amber #CB883A (203,136,58)
        br = int(137 + t * (203 - 137))
        bg = int(161 + t * (136 - 161))
        bb = int(148 + t * (58  - 148))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(br, bg, bb))
        p.drawRoundedRect(0, 0, w, h, r, r)

        # Dark circle #312938
        cx = int(self._circle_x)
        p.setBrush(QColor("#312938"))
        p.drawEllipse(cx - circle_r, h // 2 - circle_r, circle_r * 2, circle_r * 2)

        p.end()


class SettingsRow(QFrame):
    """
    row_type:
      "text"   — shows a label with value + arrow
      "toggle" — shows ToggleSwitch
      "combo"  — shows QComboBox (row_data = list of option strings)
    """

    def __init__(self, label: str, row_data=None, row_type: str = "text", parent=None):
        super().__init__(parent)
        self.setObjectName("settingsRow")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(52)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(10)

        lbl = QLabel(label)
        lbl.setObjectName("settingsRowLabel")
        layout.addWidget(lbl, stretch=1)

        if row_type == "toggle":
            toggle = ToggleSwitch()
            layout.addWidget(toggle)

        elif row_type == "combo":
            combo = QComboBox()
            combo.setObjectName("settingsCombo")
            for opt in (row_data or []):
                combo.addItem(opt)
            combo.setCurrentIndex(1)   # default "Высокое"
            layout.addWidget(combo)

        elif row_type == "text" and row_data:
            val = QLabel(str(row_data) + "  ›")
            val.setObjectName("settingsRowValue")
            val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            layout.addWidget(val)


_SECTIONS = {
    "АККАУНТ": [
        ("Имя пользователя", "crates_user", "text"),
        ("Электронная почта", "user@mail.com", "text"),
        ("Сменить пароль", "", "text"),
    ],
    "ИНТЕРФЕЙС": [
        ("Тёмная тема", None, "toggle"),
        ("Язык", "Русский", "text"),
    ],
    "ВОСПРОИЗВЕДЕНИЕ": [
        ("Качество звука", ["Авто", "Высокое", "Среднее", "Низкое"], "combo"),
        ("Автовоспроизведение", None, "toggle"),
        ("Нормализация громкости", None, "toggle"),
    ],
}


class SettingsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("settingsPage")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 20, 24, 24)
        outer.setSpacing(0)

        profile_card = QFrame()
        profile_card.setObjectName("profileCard")
        profile_layout = QHBoxLayout(profile_card)
        profile_layout.setContentsMargins(20, 16, 20, 16)
        profile_layout.setSpacing(20)

        avatar = QLabel()
        avatar.setObjectName("profileAvatar")
        avatar.setFixedSize(90, 90)
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar.setText("♪")
        avatar.setStyleSheet("font-size: 28px; color: #A14016;")

        name_col = QVBoxLayout()
        name_col.setSpacing(4)
        name_lbl = QLabel("Пользователь")
        name_lbl.setObjectName("profileName")
        handle_lbl = QLabel("@crates_user")
        handle_lbl.setObjectName("profileHandle")
        name_col.addWidget(name_lbl)
        name_col.addWidget(handle_lbl)
        name_col.addStretch()

        profile_layout.addWidget(avatar)
        profile_layout.addLayout(name_col, stretch=1)
        outer.addWidget(profile_card)

        scroll = QScrollArea()
        scroll.setObjectName("settingsScroll")
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        col = QVBoxLayout(container)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(6)

        for section_name, rows in _SECTIONS.items():
            section_lbl = QLabel(section_name)
            section_lbl.setObjectName("settingsSectionLabel")
            col.addWidget(section_lbl)
            for row_label, row_data, row_type in rows:
                col.addWidget(SettingsRow(row_label, row_data, row_type))

        col.addStretch()
        scroll.setWidget(container)
        outer.addWidget(scroll, stretch=1)
