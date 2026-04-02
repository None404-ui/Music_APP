from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QScrollArea, QFrame, QSizePolicy, QComboBox,
)
from PyQt6.QtCore import Qt, pyqtProperty, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QPainter, QColor

from ui import playback_settings


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

    def _get_circle_x(self):
        return self._circle_x

    def _set_circle_x(self, value: float):
        self._circle_x = value
        self.update()

    circle_x = pyqtProperty(float, _get_circle_x, _set_circle_x)

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, checked: bool):
        if self._checked != checked:
            self._checked = checked
            self._start_animation(checked)

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
        r = h // 2
        circle_r = r - 4

        t = max(0.0, min(1.0, (self._circle_x - self._OFF_X) / (self._ON_X - self._OFF_X)))

        br = int(137 + t * (203 - 137))
        bg = int(161 + t * (136 - 161))
        bb = int(148 + t * (58 - 148))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(br, bg, bb))
        p.drawRoundedRect(0, 0, w, h, r, r)

        cx = int(self._circle_x)
        p.setBrush(QColor("#312938"))
        p.drawEllipse(cx - circle_r, h // 2 - circle_r, circle_r * 2, circle_r * 2)

        p.end()


class SettingsRow(QFrame):
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
            layout.addWidget(combo)

        elif row_type == "text" and row_data:
            val = QLabel(str(row_data) + "  ›")
            val.setObjectName("settingsRowValue")
            val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            layout.addWidget(val)


_SECTIONS_OTHER = {
    "АККАУНТ": [
        ("Имя пользователя", "crates_user", "text"),
        ("Электронная почта", "user@mail.com", "text"),
        ("Сменить пароль", "", "text"),
    ],
    "ИНТЕРФЕЙС": [
        ("Тёмная тема", None, "toggle"),
        ("Язык", "Русский", "text"),
    ],
}


class SettingsTab(QWidget):
    def __init__(self, on_playback_changed=None, parent=None):
        super().__init__(parent)
        self.setObjectName("settingsPage")
        self._on_playback_changed = on_playback_changed

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

        for section_name, rows in _SECTIONS_OTHER.items():
            section_lbl = QLabel(section_name)
            section_lbl.setObjectName("settingsSectionLabel")
            col.addWidget(section_lbl)
            for row_label, row_data, row_type in rows:
                col.addWidget(SettingsRow(row_label, row_data, row_type))

        pb_lbl = QLabel("ВОСПРОИЗВЕДЕНИЕ")
        pb_lbl.setObjectName("settingsSectionLabel")
        col.addWidget(pb_lbl)

        self._quality_combo = QComboBox()
        self._quality_combo.setObjectName("settingsCombo")
        for opt in ["Авто", "Высокое", "Среднее", "Низкое"]:
            self._quality_combo.addItem(opt)
        qrow = QFrame()
        qrow.setObjectName("settingsRow")
        qrow.setFixedHeight(52)
        ql = QHBoxLayout(qrow)
        ql.setContentsMargins(16, 0, 16, 0)
        q_lab = QLabel("Качество звука")
        q_lab.setObjectName("settingsRowLabel")
        ql.addWidget(q_lab)
        ql.addStretch()
        ql.addWidget(self._quality_combo)
        idx = self._quality_combo.findText(playback_settings.quality_label())
        self._quality_combo.setCurrentIndex(max(0, idx))
        self._quality_combo.currentTextChanged.connect(self._on_quality_changed)
        col.addWidget(qrow)

        self._autoplay_toggle = ToggleSwitch()
        self._autoplay_toggle.setChecked(playback_settings.autoplay())
        self._autoplay_toggle.toggled.connect(self._on_autoplay_toggled)
        arow = QFrame()
        arow.setObjectName("settingsRow")
        arow.setFixedHeight(52)
        al = QHBoxLayout(arow)
        al.setContentsMargins(16, 0, 16, 0)
        a_lab = QLabel("Автовоспроизведение")
        a_lab.setObjectName("settingsRowLabel")
        al.addWidget(a_lab)
        al.addStretch()
        al.addWidget(self._autoplay_toggle)
        col.addWidget(arow)

        self._norm_toggle = ToggleSwitch()
        self._norm_toggle.setChecked(playback_settings.normalization())
        self._norm_toggle.toggled.connect(self._on_norm_toggled)
        nrow = QFrame()
        nrow.setObjectName("settingsRow")
        nrow.setFixedHeight(52)
        nl = QHBoxLayout(nrow)
        nl.setContentsMargins(16, 0, 16, 0)
        n_lab = QLabel("Нормализация громкости")
        n_lab.setObjectName("settingsRowLabel")
        nl.addWidget(n_lab)
        nl.addStretch()
        nl.addWidget(self._norm_toggle)
        col.addWidget(nrow)

        col.addStretch()
        scroll.setWidget(container)
        outer.addWidget(scroll, stretch=1)

    def _emit_playback(self) -> None:
        if self._on_playback_changed:
            self._on_playback_changed()

    def _on_quality_changed(self, text: str) -> None:
        playback_settings.set_quality_label(text)
        self._emit_playback()

    def _on_autoplay_toggled(self, checked: bool) -> None:
        playback_settings.set_autoplay(checked)
        self._emit_playback()

    def _on_norm_toggled(self, checked: bool) -> None:
        playback_settings.set_normalization(checked)
        self._emit_playback()
