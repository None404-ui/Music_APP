from __future__ import annotations

import os

from PyQt6.QtCore import QSize, Qt, QUrl
from PyQt6.QtGui import QImage, QMouseEvent, QPixmap
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui.interactive_fx import InteractiveRowFrame, StatefulIconButton

_ICONS_DIR = os.path.join(os.path.dirname(__file__), "..", "icons")
_mini_cover_nam: QNetworkAccessManager | None = None


def _mini_network() -> QNetworkAccessManager:
    global _mini_cover_nam
    if _mini_cover_nam is None:
        from PyQt6.QtWidgets import QApplication

        _mini_cover_nam = QNetworkAccessManager(QApplication.instance())
    return _mini_cover_nam


class MiniPlayerBar(InteractiveRowFrame):
    def __init__(self, player, on_open_player=None, parent=None):
        super().__init__(radius=14, hover_alpha=22, press_alpha=36, active_alpha=12, parent=parent)
        self.setObjectName("miniPlayerBar")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._player = player
        self._on_open_player = on_open_player
        self._cover_reply: QNetworkReply | None = None
        self._has_track = False
        self._play_icon = os.path.join(_ICONS_DIR, "player_play.svg")
        self._pause_icon = os.path.join(_ICONS_DIR, "player_pause.svg")

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 10, 14, 10)
        root.setSpacing(8)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(12)

        self._cover = QLabel()
        self._cover.setObjectName("miniPlayerCover")
        self._cover.setFixedSize(52, 52)
        self._cover.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._cover.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._apply_cover_placeholder()
        top.addWidget(self._cover, 0, Qt.AlignmentFlag.AlignVCenter)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        text_col.setContentsMargins(0, 0, 0, 0)

        self._title = QLabel("—")
        self._title.setObjectName("miniPlayerTitle")
        self._title.setWordWrap(False)
        self._title.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        self._artist = QLabel("")
        self._artist.setObjectName("miniPlayerArtist")
        self._artist.setWordWrap(False)
        self._artist.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        text_col.addWidget(self._title)
        text_col.addWidget(self._artist)
        top.addLayout(text_col, stretch=1)

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

        controls.addWidget(self._btn_prev)
        controls.addWidget(self._btn_play)
        controls.addWidget(self._btn_next)
        controls.addSpacing(6)
        controls.addWidget(self._btn_like)
        top.addLayout(controls)

        root.addLayout(top)

        self._progress = QProgressBar()
        self._progress.setObjectName("miniPlayerProgress")
        self._progress.setRange(0, 1000)
        self._progress.setValue(0)
        self._progress.setTextVisible(False)
        self._progress.setFixedHeight(6)
        root.addWidget(self._progress)

        self.install_interaction_filters()
        self.hide()

        self._player.current_item_changed.connect(self.update_from_snapshot)
        self._player.playback_state_changed.connect(self._on_playback_state_changed)
        self._player.transport_state_changed.connect(self._on_transport_state_changed)
        self._player.progress_changed.connect(self._on_progress_changed)
        self.update_from_snapshot(self._player.current_item_snapshot())

    def has_track(self) -> bool:
        return self._has_track

    def _interactive_widgets(self) -> list[QWidget]:
        return [self._btn_prev, self._btn_play, self._btn_next, self._btn_like]

    def _apply_cover_placeholder(self) -> None:
        self._cover.clear()
        self._cover.setPixmap(QPixmap())
        self._cover.setText("♪")
        self._cover.setStyleSheet(
            "font-size: 18px; color: #A14016; font-family: 'Courier New';"
        )

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
            pix = QPixmap.fromImage(img).scaled(
                52,
                52,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._cover.setPixmap(pix)
            self._cover.setText("")
            self._cover.setStyleSheet("")
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

    def update_from_snapshot(self, snapshot: dict) -> None:
        has_track = bool(snapshot)
        self._has_track = has_track
        if not has_track:
            self._title.setText("—")
            self._artist.setText("")
            self._btn_prev.setEnabled(False)
            self._btn_next.setEnabled(False)
            self._btn_play.setEnabled(False)
            self._btn_like.setEnabled(False)
            self._progress.setRange(0, 1000)
            self._progress.setValue(0)
            self._apply_cover_placeholder()
            return

        self._title.setText(str(snapshot.get("title") or "—"))
        self._artist.setText(str(snapshot.get("artist") or ""))
        self._title.setToolTip(self._title.text())
        self._artist.setToolTip(self._artist.text())
        self._btn_play.setEnabled(True)
        self._btn_prev.setEnabled(bool(snapshot.get("can_prev")))
        self._btn_next.setEnabled(bool(snapshot.get("can_next")))
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

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            p = event.position().toPoint()
            for widget in self._interactive_widgets():
                if widget.geometry().contains(p):
                    super().mouseReleaseEvent(event)
                    return
            if self._on_open_player and self.rect().contains(p):
                self._on_open_player()
        super().mouseReleaseEvent(event)
