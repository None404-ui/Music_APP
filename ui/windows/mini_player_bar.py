from __future__ import annotations

import os

from PyQt6.QtCore import QEvent, QSize, Qt, QUrl
from PyQt6.QtGui import QColor, QImage, QMouseEvent, QPixmap
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QSlider,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui.artist_link_label import ArtistLinkLabel
from ui.cover_art import CoverArtWidget
from ui.interactive_fx import InteractiveRowFrame, StatefulIconButton
from ui import i18n

_ICONS_DIR = os.path.join(os.path.dirname(__file__), "..", "icons")
_mini_cover_nam: QNetworkAccessManager | None = None


def _mini_network() -> QNetworkAccessManager:
    global _mini_cover_nam
    if _mini_cover_nam is None:
        from PyQt6.QtWidgets import QApplication

        _mini_cover_nam = QNetworkAccessManager(QApplication.instance())
    return _mini_cover_nam


class MiniPlayerBar(InteractiveRowFrame):
    def __init__(self, player, on_open_player=None, on_open_artist=None, parent=None):
        super().__init__(radius=14, hover_alpha=22, press_alpha=36, active_alpha=12, parent=parent)
        self.setObjectName("miniPlayerBar")
        self._player = player
        self._on_open_player = on_open_player
        self._on_open_artist = on_open_artist
        self._cover_reply: QNetworkReply | None = None
        self._has_track = False
        self._play_icon = os.path.join(_ICONS_DIR, "player_play.svg")
        self._pause_icon = os.path.join(_ICONS_DIR, "player_pause.svg")
        self._volume_icon = os.path.join(_ICONS_DIR, "player_volume.svg")
        self._review_icon = os.path.join(_ICONS_DIR, "player_review_mono.svg")

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 10, 14, 10)
        root.setSpacing(8)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(12)

        left_wrap = QHBoxLayout()
        left_wrap.setContentsMargins(0, 0, 0, 0)
        left_wrap.setSpacing(12)

        self._cover = CoverArtWidget(
            radius=8,
            border_width=1,
            border_color=QColor("#CB883A"),
            fill_color=QColor("#BDB685"),
            mask_color=QColor(36, 33, 24, 240),
            placeholder_text="♪",
            placeholder_color=QColor("#A14016"),
            placeholder_px=18,
        )
        self._cover.setObjectName("miniPlayerCover")
        self._cover.setFixedSize(52, 52)
        self._cover.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cover.installEventFilter(self)
        self._apply_cover_placeholder()
        left_wrap.addWidget(self._cover, 0, Qt.AlignmentFlag.AlignVCenter)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        text_col.setContentsMargins(0, 0, 0, 0)

        self._title = QLabel("—")
        self._title.setObjectName("miniPlayerTitle")
        self._title.setWordWrap(False)
        self._title.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._title.setCursor(Qt.CursorShape.PointingHandCursor)
        self._title.installEventFilter(self)

        self._artist = ArtistLinkLabel()
        self._artist.setObjectName("miniPlayerArtist")
        self._artist.setWordWrap(False)
        self._artist.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        if self._on_open_artist:
            self._artist.artist_clicked.connect(self._on_open_artist)

        text_col.addWidget(self._title)
        text_col.addWidget(self._artist)
        left_wrap.addLayout(text_col, stretch=1)
        top.addLayout(left_wrap, stretch=1)

        controls = QHBoxLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setSpacing(8)

        self._btn_prev = StatefulIconButton(
            os.path.join(_ICONS_DIR, "player_prev.svg"),
            base_color="#CFC89A",
            hover_color="#CB883A",
            pressed_color="#A14016",
            checked_color="#CB883A",
            pulse_on_toggle=False,
            parent=self,
        )
        self._btn_prev.setObjectName("miniPlayerBtn")
        self._btn_prev.setFixedSize(34, 34)
        self._btn_prev.setIconSize(QSize(20, 20))
        self._btn_prev.clicked.connect(self._player.play_previous)

        self._btn_play = StatefulIconButton(
            self._play_icon,
            base_color="#312938",
            hover_color="#312938",
            pressed_color="#A14016",
            checked_color="#312938",
            pulse_on_toggle=False,
            parent=self,
        )
        self._btn_play.setObjectName("miniPlayerPlayBtn")
        self._btn_play.setFixedSize(42, 42)
        self._btn_play.setIconSize(QSize(22, 22))
        self._btn_play.clicked.connect(self._player.toggle_playback)

        self._btn_next = StatefulIconButton(
            os.path.join(_ICONS_DIR, "player_next.svg"),
            base_color="#CFC89A",
            hover_color="#CB883A",
            pressed_color="#A14016",
            checked_color="#CB883A",
            pulse_on_toggle=False,
            parent=self,
        )
        self._btn_next.setObjectName("miniPlayerBtn")
        self._btn_next.setFixedSize(34, 34)
        self._btn_next.setIconSize(QSize(20, 20))
        self._btn_next.clicked.connect(self._player.play_next)

        self._btn_like = StatefulIconButton(
            os.path.join(_ICONS_DIR, "player_like.svg"),
            checked_icon_path=os.path.join(_ICONS_DIR, "player_like_filled.svg"),
            base_color="#CFC89A",
            hover_color="#CB883A",
            pressed_color="#A14016",
            checked_color="#CB883A",
            parent=self,
        )
        self._btn_like.setObjectName("miniPlayerLikeBtn")
        self._btn_like.setCheckable(True)
        self._btn_like.setFixedSize(34, 34)
        self._btn_like.setIconSize(QSize(20, 20))
        self._btn_like.toggled.connect(self._on_like_toggled)

        self._btn_review = StatefulIconButton(
            self._review_icon,
            base_color="#CFC89A",
            hover_color="#2A7A8C",
            pressed_color="#A14016",
            checked_color="#2A7A8C",
            pulse_on_toggle=False,
            parent=self,
        )
        self._btn_review.setObjectName("miniPlayerBtn")
        self._btn_review.setFixedSize(34, 34)
        self._btn_review.setIconSize(QSize(20, 20))
        self._btn_review.setToolTip(i18n.tr("Написать рецензию"))
        self._btn_review.clicked.connect(self._on_review_clicked)

        self._btn_volume = StatefulIconButton(
            self._volume_icon,
            base_color="#CFC89A",
            hover_color="#CB883A",
            pressed_color="#A14016",
            checked_color="#CB883A",
            pulse_on_toggle=False,
            parent=self,
        )
        self._btn_volume.setObjectName("miniPlayerBtn")
        self._btn_volume.setFixedSize(34, 34)
        self._btn_volume.setIconSize(QSize(20, 20))
        self._btn_volume.clicked.connect(self._toggle_volume_popup)

        controls.addWidget(self._btn_prev)
        controls.addWidget(self._btn_play)
        controls.addWidget(self._btn_next)
        top.addLayout(controls, stretch=0)

        right_wrap = QVBoxLayout()
        right_wrap.setContentsMargins(0, 0, 0, 0)
        right_wrap.setSpacing(6)

        right_top = QHBoxLayout()
        right_top.setContentsMargins(0, 0, 0, 0)
        right_top.setSpacing(6)
        right_top.addStretch(1)
        right_top.addWidget(self._btn_volume, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        right_top.addWidget(self._btn_review, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        right_top.addWidget(self._btn_like, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        right_wrap.addLayout(right_top)
        top.addLayout(right_wrap, stretch=1)

        root.addLayout(top)

        self._progress = QProgressBar()
        self._progress.setObjectName("miniPlayerProgress")
        self._progress.setRange(0, 1000)
        self._progress.setValue(0)
        self._progress.setTextVisible(False)
        self._progress.setFixedHeight(6)
        root.addWidget(self._progress)

        self._volume_popup = QFrame(self, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self._volume_popup.setObjectName("miniPlayerVolumePopup")
        self._volume_popup.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        popup_layout = QVBoxLayout(self._volume_popup)
        popup_layout.setContentsMargins(10, 10, 10, 10)
        popup_layout.setSpacing(6)
        volume_label = QLabel("VOL")
        volume_label.setObjectName("miniPlayerVolumePopupLabel")
        volume_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        popup_layout.addWidget(volume_label)
        self._volume_popup_slider = QSlider(Qt.Orientation.Vertical)
        self._volume_popup_slider.setObjectName("miniPlayerVolumeSlider")
        self._volume_popup_slider.setRange(0, 100)
        self._volume_popup_slider.setInvertedAppearance(False)
        self._volume_popup_slider.setFixedSize(18, 86)
        self._volume_popup_slider.valueChanged.connect(self._on_volume_changed)
        popup_layout.addWidget(self._volume_popup_slider, 0, Qt.AlignmentFlag.AlignHCenter)
        self._volume_popup.hide()

        self.install_interaction_filters()
        self.hide()

        self._player.current_item_changed.connect(self.update_from_snapshot)
        self._player.playback_state_changed.connect(self._on_playback_state_changed)
        self._player.transport_state_changed.connect(self._on_transport_state_changed)
        self._player.progress_changed.connect(self._on_progress_changed)
        self._player.volume_changed.connect(self._sync_volume_slider)
        self._sync_volume_slider(self._player.current_volume_percent())
        self.update_from_snapshot(self._player.current_item_snapshot())

    def has_track(self) -> bool:
        return self._has_track

    def _interactive_widgets(self) -> list[QWidget]:
        return [
            self._btn_prev,
            self._btn_play,
            self._btn_next,
            self._btn_volume,
            self._volume_popup_slider,
            self._btn_review,
            self._btn_like,
        ]

    def _apply_cover_placeholder(self) -> None:
        self._cover.clear_cover()

    def _load_cover(self, url: str) -> None:
        if self._cover_reply is not None:
            prev = self._cover_reply
            self._cover_reply = None
            prev.abort()
        if not url.startswith(("http://", "https://")):
            self._apply_cover_placeholder()
            return
        self._cover_reply = _mini_network().get(QNetworkRequest(QUrl(url)))
        self._cover_reply.finished.connect(self._on_cover_finished)

    def _on_cover_finished(self) -> None:
        reply = self.sender()
        if not isinstance(reply, QNetworkReply):
            return
        if reply is not self._cover_reply:
            reply.deleteLater()
            return
        self._cover_reply = None
        try:
            if reply.error() != QNetworkReply.NetworkError.NoError:
                self._apply_cover_placeholder()
                return
            data = reply.readAll()
            img = QImage()
            if not img.loadFromData(data):
                self._apply_cover_placeholder()
                return
            self._cover.set_cover_pixmap(QPixmap.fromImage(img))
        finally:
            reply.deleteLater()

    def _on_playback_state_changed(self, playing: bool) -> None:
        self._btn_play.set_icon_paths(self._pause_icon if playing else self._play_icon)

    def _on_transport_state_changed(self, can_prev: bool, can_next: bool) -> None:
        self._btn_prev.setEnabled(can_prev)
        self._btn_next.setEnabled(can_next)

    def _on_progress_changed(self, pos_ms: int, dur_ms: int) -> None:
        if dur_ms <= 0:
            self._progress.setRange(0, 1000)
            self._progress.setValue(0)
            return
        self._progress.setRange(0, max(1, dur_ms))
        self._progress.setValue(max(0, min(pos_ms, dur_ms)))

    def _on_like_toggled(self, checked: bool) -> None:
        self._player.set_current_favorite_checked(checked)

    def _toggle_volume_popup(self) -> None:
        if self._volume_popup.isVisible():
            self._volume_popup.hide()
            return
        self._sync_volume_slider(self._player.current_volume_percent())
        self._volume_popup.adjustSize()
        popup_size = self._volume_popup.sizeHint()
        btn_top_left = self._btn_volume.mapToGlobal(self._btn_volume.rect().topLeft())
        btn_bottom_left = self._btn_volume.mapToGlobal(self._btn_volume.rect().bottomLeft())
        x = btn_top_left.x() + (self._btn_volume.width() - popup_size.width()) // 2
        y = btn_top_left.y() - popup_size.height() - 8
        if y < 8:
            y = btn_bottom_left.y() + 8
        self._volume_popup.move(x, y)
        self._volume_popup.show()
        self._volume_popup.raise_()

    def _sync_volume_slider(self, value: int) -> None:
        volume = max(0, min(100, int(value)))
        self._volume_popup_slider.blockSignals(True)
        self._volume_popup_slider.setValue(volume)
        self._volume_popup_slider.blockSignals(False)
        tip = i18n.volume_percent_tooltip(volume)
        self._btn_volume.setToolTip(tip)
        self._volume_popup_slider.setToolTip(tip)

    def _on_volume_changed(self, value: int) -> None:
        self._player.set_volume_percent(value)

    def _on_review_clicked(self) -> None:
        self._player.open_review_dialog()

    def eventFilter(self, watched, event):
        if (
            watched in (self._cover, self._title)
            and event.type() == QEvent.Type.MouseButtonRelease
            and isinstance(event, QMouseEvent)
        ):
            if (
                event.button() == Qt.MouseButton.LeftButton
                and self._has_track
                and self._on_open_player
            ):
                self._on_open_player()
                event.accept()
                return True
        return super().eventFilter(watched, event)

    def update_from_snapshot(self, snapshot: dict) -> None:
        has_track = bool(snapshot)
        self._has_track = has_track
        if not has_track:
            self._title.setText("—")
            self._artist.set_artist("")
            self._btn_prev.setEnabled(False)
            self._btn_next.setEnabled(False)
            self._btn_play.setEnabled(False)
            self._btn_review.setEnabled(False)
            self._btn_like.setEnabled(False)
            self._progress.setRange(0, 1000)
            self._progress.setValue(0)
            self._apply_cover_placeholder()
            return

        self._title.setText(str(snapshot.get("title") or "—"))
        self._artist.set_artist(str(snapshot.get("artist") or ""))
        self._title.setToolTip(self._title.text())
        self._btn_play.setEnabled(True)
        self._btn_prev.setEnabled(bool(snapshot.get("can_prev")))
        self._btn_next.setEnabled(bool(snapshot.get("can_next")))
        self._btn_review.setEnabled(True)
        self._btn_like.setEnabled(bool(snapshot.get("like_enabled")))
        self._btn_like.blockSignals(True)
        self._btn_like.setChecked(bool(snapshot.get("user_favorited")))
        self._btn_like.blockSignals(False)
        self._on_playback_state_changed(bool(snapshot.get("is_playing")))
        self._on_progress_changed(
            int(snapshot.get("position_ms") or 0),
            int(snapshot.get("duration_ms") or 0),
        )
        self._load_cover(str(snapshot.get("artwork_url_resolved") or ""))

