from typing import TYPE_CHECKING, Callable, Optional

if TYPE_CHECKING:
    from backend.session import UserSession

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QFrame,
    QSizePolicy,
    QComboBox,
    QPushButton,
    QFileDialog,
)
from PyQt6.QtCore import Qt, QUrl, pyqtProperty, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QPainter, QColor, QImage, QPainterPath, QPixmap
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

from backend.api_client import resolve_backend_media_url
from ui import playback_settings

# Слева подпись — #89A194; справа значение — тёплый беж #CFC89A (как в палитре CRATES).
_SETTINGS_ROW_LABEL_COLOR = "#89A194"
_SETTINGS_ROW_VALUE_COLOR = "#CFC89A"


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


class ClickableAvatarLabel(QLabel):
    clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)


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
        lbl.setStyleSheet(f"color: {_SETTINGS_ROW_LABEL_COLOR};")
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
            val.setStyleSheet(f"color: {_SETTINGS_ROW_VALUE_COLOR};")
            val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            layout.addWidget(val)


_SECTIONS_OTHER = {
    "ИНТЕРФЕЙС": [
        ("Тёмная тема", None, "toggle"),
        ("Язык", "Русский", "text"),
    ],
}


class SettingsTab(QWidget):
    def __init__(
        self,
        session: Optional["UserSession"] = None,
        on_playback_changed=None,
        on_logout: Optional[Callable[[], None]] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("settingsPage")
        self._session = session
        self._on_playback_changed = on_playback_changed
        self._on_logout = on_logout

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 20, 24, 24)
        outer.setSpacing(0)

        profile_card = QFrame()
        profile_card.setObjectName("profileCard")
        profile_layout = QHBoxLayout(profile_card)
        profile_layout.setContentsMargins(20, 16, 20, 16)
        profile_layout.setSpacing(20)

        self._avatar_reply: QNetworkReply | None = None
        self._avatar_nam = QNetworkAccessManager(self)

        avatar = ClickableAvatarLabel()
        avatar.setObjectName("profileAvatar")
        avatar.setFixedSize(90, 90)
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar.setText("♪")
        if session is not None:
            avatar.setToolTip("Нажмите, чтобы выбрать фото профиля")
            avatar.clicked.connect(self._pick_avatar)
        else:
            avatar.setToolTip("")

        name_col = QVBoxLayout()
        name_col.setSpacing(4)
        if session is not None:
            email = (session.email or "").strip()
            nick = (session.nickname or "").strip()
            display = nick or (email.split("@", 1)[0] if email else "") or "Пользователь"
            name_lbl = QLabel(display)
            handle_lbl = QLabel(email or "—")
        else:
            name_lbl = QLabel("Пользователь")
            handle_lbl = QLabel("—")
        name_lbl.setObjectName("profileName")
        handle_lbl.setObjectName("profileHandle")
        self._name_lbl = name_lbl
        self._handle_lbl = handle_lbl
        name_col.addWidget(name_lbl)
        name_col.addWidget(handle_lbl)
        name_col.addStretch()

        self._avatar = avatar
        profile_layout.addWidget(avatar)
        profile_layout.addLayout(name_col, stretch=1)

        if on_logout is not None:
            btn_out = QPushButton("Выйти из аккаунта")
            btn_out.setObjectName("settingsLogoutBtn")
            btn_out.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_out.setSizePolicy(
                QSizePolicy.Policy.Maximum,
                QSizePolicy.Policy.Fixed,
            )
            btn_out.clicked.connect(on_logout)
            corner = QVBoxLayout()
            corner.setContentsMargins(0, 0, 0, 0)
            corner.setSpacing(0)
            corner.addWidget(
                btn_out,
                alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight,
            )
            corner.addStretch()
            profile_layout.addLayout(corner)
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

        acc_lbl = QLabel("АККАУНТ")
        acc_lbl.setObjectName("settingsSectionLabel")
        col.addWidget(acc_lbl)
        if session is not None:
            email_acc = (session.email or "").strip()
            nick_acc = (session.nickname or "").strip()
            name_row = nick_acc or (email_acc.split("@", 1)[0] if email_acc else "") or "—"
            mail_row = email_acc or "—"
        else:
            name_row, mail_row = "—", "—"
        col.addWidget(SettingsRow("Имя пользователя", name_row, "text"))
        col.addWidget(SettingsRow("Электронная почта", mail_row, "text"))
        col.addWidget(SettingsRow("Сменить пароль", "", "text"))

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
        q_lab.setStyleSheet(f"color: {_SETTINGS_ROW_LABEL_COLOR};")
        ql.addWidget(q_lab)
        ql.addStretch()
        ql.addWidget(self._quality_combo)
        idx = self._quality_combo.findText(playback_settings.quality_label())
        self._quality_combo.blockSignals(True)
        self._quality_combo.setCurrentIndex(max(0, idx))
        self._quality_combo.blockSignals(False)
        self._quality_combo.currentIndexChanged.connect(self._on_quality_index_changed)
        col.addWidget(qrow)
        q_hint = QLabel(
            "Меняет максимальную громкость: «Низкое» тише, «Высокое» — полный уровень ползунка."
        )
        q_hint.setObjectName("settingsHint")
        q_hint.setWordWrap(True)
        col.addWidget(q_hint)

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

    def showEvent(self, event):
        super().showEvent(event)
        if self._session:
            self._reload_profile_header()

    def _round_avatar_pixmap(self, src: QPixmap) -> QPixmap:
        size = 90
        if src.isNull():
            return src
        scaled = src.scaled(
            size,
            size,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        out = QPixmap(size, size)
        out.fill(Qt.GlobalColor.transparent)
        p = QPainter(out)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addEllipse(0, 0, size, size)
        p.setClipPath(path)
        sw, sh = scaled.width(), scaled.height()
        p.drawPixmap((size - sw) // 2, (size - sh) // 2, scaled)
        p.end()
        return out

    def _abort_avatar_reply(self) -> None:
        if self._avatar_reply is None:
            return
        r = self._avatar_reply
        self._avatar_reply = None
        r.abort()

    def _on_avatar_downloaded(self) -> None:
        reply = self.sender()
        if not isinstance(reply, QNetworkReply):
            return
        if reply is not self._avatar_reply:
            reply.deleteLater()
            return
        self._avatar_reply = None
        try:
            if reply.error() != QNetworkReply.NetworkError.NoError:
                return
            data = reply.readAll()
            img = QImage()
            if not img.loadFromData(data):
                return
            pix = self._round_avatar_pixmap(QPixmap.fromImage(img))
            self._avatar.setPixmap(pix)
            self._avatar.setText("")
        finally:
            reply.deleteLater()

    def _fetch_avatar_from_url(self, url: str) -> None:
        if not url or not url.startswith(("http://", "https://")):
            return
        self._abort_avatar_reply()
        self._avatar_reply = self._avatar_nam.get(QNetworkRequest(QUrl(url)))
        self._avatar_reply.finished.connect(self._on_avatar_downloaded)

    def _reload_profile_header(self) -> None:
        if not self._session:
            return
        st, body = self._session.client.get_json("/api/profile/me/")
        if st != 200 or not isinstance(body, dict):
            return
        nick = (body.get("nickname") or "").strip()
        email = (self._session.email or "").strip()
        display = nick or (email.split("@", 1)[0] if email else "") or "Пользователь"
        self._name_lbl.setText(display)
        self._handle_lbl.setText(email or "—")
        url = resolve_backend_media_url(
            self._session.client.base_url,
            (body.get("avatar_url") or "").strip(),
        )
        if url.startswith(("http://", "https://")):
            self._fetch_avatar_from_url(url)
        else:
            self._avatar.clear()
            self._avatar.setPixmap(QPixmap())
            self._avatar.setText("♪")

    def _pick_avatar(self) -> None:
        if not self._session:
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Изображение для аватара",
            "",
            "Изображения (*.png *.jpg *.jpeg *.webp *.bmp);;Все файлы (*.*)",
        )
        if not path:
            return
        prev = QPixmap(path)
        if not prev.isNull():
            self._avatar.setPixmap(self._round_avatar_pixmap(prev))
            self._avatar.setText("")
        st, body = self._session.client.patch_multipart_file(
            "/api/profile/me/", "avatar_file", path
        )
        if st == 200 and isinstance(body, dict):
            au = resolve_backend_media_url(
                self._session.client.base_url,
                (body.get("avatar_url") or "").strip(),
            )
            if au.startswith(("http://", "https://")):
                self._fetch_avatar_from_url(au)
        else:
            self._reload_profile_header()

    def _emit_playback(self) -> None:
        if self._on_playback_changed:
            self._on_playback_changed()

    def _on_quality_index_changed(self, index: int) -> None:
        text = self._quality_combo.itemText(index)
        playback_settings.set_quality_label(text)
        self._emit_playback()

    def _on_autoplay_toggled(self, checked: bool) -> None:
        playback_settings.set_autoplay(checked)
        self._emit_playback()

    def _on_norm_toggled(self, checked: bool) -> None:
        playback_settings.set_normalization(checked)
        self._emit_playback()
