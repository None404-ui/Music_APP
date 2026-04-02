from __future__ import annotations

import json
from typing import Optional

from PyQt6.QtCore import Qt, QUrl, QSize, QByteArray
from PyQt6.QtGui import QPixmap, QImage, QPainter, QColor
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QSizePolicy,
    QFrame,
    QScrollArea,
    QGraphicsDropShadowEffect,
)

from ui import playback_settings


def _fmt_ms(ms: int) -> str:
    if ms < 0:
        ms = 0
    s = ms // 1000
    m, s = s // 60, s % 60
    return f"{m:d}:{s:02d}"


def _album_name(item: dict) -> str:
    meta = item.get("meta_json")
    if isinstance(meta, str) and meta.strip():
        try:
            j = json.loads(meta)
            if isinstance(j, dict) and j.get("album"):
                return str(j["album"])
        except json.JSONDecodeError:
            pass
    artist = (item.get("artist") or "").strip()
    if artist:
        return artist.upper()
    return "ИМЯ АЛЬБОМА"


class _TrackRow(QFrame):
    def __init__(
        self,
        title: str,
        artist: str,
        active: bool,
        on_click=None,
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("playerTrackRowActive" if active else "playerTrackRow")
        self._on_click = on_click
        if on_click:
            self.setCursor(Qt.CursorShape.PointingHandCursor)

        row = QHBoxLayout(self)
        row.setContentsMargins(10, 8, 14, 8)
        row.setSpacing(12)

        thumb = QLabel()
        thumb.setFixedSize(36, 36)
        thumb.setObjectName("playerTrackThumb")
        row.addWidget(thumb)

        col = QVBoxLayout()
        col.setSpacing(2)
        t = QLabel(title)
        t.setObjectName("playerTrackTitle")
        a = QLabel(artist)
        a.setObjectName("playerTrackArtist")
        col.addWidget(t)
        col.addWidget(a)
        row.addLayout(col, stretch=1)

    def mousePressEvent(self, event) -> None:
        if self._on_click:
            self._on_click()
        super().mousePressEvent(event)


class PlayerTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("playerPage")

        self._playlist: list[dict] = []
        self._index = 0
        self._user_seeking = False
        self._art_reply: Optional[QNetworkReply] = None

        self._audio = QAudioOutput(self)
        self._audio.setVolume(0.75)
        self._player = QMediaPlayer(self)
        self._player.setAudioOutput(self._audio)
        self._player.positionChanged.connect(self._on_position_changed)
        self._player.durationChanged.connect(self._on_duration_changed)
        self._player.playbackStateChanged.connect(self._on_state_changed)
        self._player.mediaStatusChanged.connect(self._on_media_status)
        self._player.errorOccurred.connect(self._on_player_error)

        self._nam = QNetworkAccessManager(self)

        root = QHBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(18)

        # --- Левая карточка: сейчас играет ---
        self._left_card = QFrame()
        self._left_card.setObjectName("playerLeftCard")
        self._left_card.setFixedWidth(300)
        lv = QVBoxLayout(self._left_card)
        lv.setContentsMargins(0, 0, 0, 0)
        lv.setSpacing(0)

        self._art = QLabel()
        self._art.setObjectName("playerArtPanel")
        self._art.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._art.setMinimumHeight(220)
        self._art.setText("♪")
        lv.addWidget(self._art)

        band = QFrame()
        band.setObjectName("playerTrackBand")
        bl = QVBoxLayout(band)
        bl.setContentsMargins(14, 10, 14, 10)
        lbl_trek = QLabel("ТРЕК")
        lbl_trek.setObjectName("playerTrekLabel")
        bl.addWidget(lbl_trek)
        self._now_title = QLabel("—")
        self._now_title.setObjectName("playerNowTitle")
        self._now_title.setWordWrap(True)
        bl.addWidget(self._now_title)
        self._now_artist = QLabel("")
        self._now_artist.setObjectName("playerNowArtist")
        bl.addWidget(self._now_artist)
        lv.addWidget(band)

        ctrl_block = QWidget()
        cvl = QVBoxLayout(ctrl_block)
        cvl.setContentsMargins(16, 14, 16, 16)
        cvl.setSpacing(12)

        self._progress = QSlider(Qt.Orientation.Horizontal)
        self._progress.setObjectName("playerProgressMock")
        self._progress.setRange(0, 1000)
        self._progress.setValue(0)
        self._progress.sliderPressed.connect(lambda: setattr(self, "_user_seeking", True))
        self._progress.sliderReleased.connect(self._on_seek_released)

        times = QHBoxLayout()
        self._t_elapsed = QLabel("0:00")
        self._t_elapsed.setObjectName("playerTimeElapsed")
        self._t_total = QLabel("0:00")
        self._t_total.setObjectName("playerTimeRemain")
        times.addWidget(self._t_elapsed)
        times.addStretch()
        times.addWidget(self._t_total)
        cvl.addWidget(self._progress)
        cvl.addLayout(times)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(18)
        btn_row.addStretch()
        self._btn_prev = QPushButton("⏮")
        self._btn_prev.setObjectName("playerBtnPrev")
        self._btn_prev.setFixedSize(44, 44)
        self._btn_prev.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_prev.clicked.connect(self._prev_track)

        self._btn_play = QPushButton("▶")
        self._btn_play.setObjectName("playerBtnPlayCircle")
        self._btn_play.setFixedSize(52, 52)
        self._btn_play.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_play.clicked.connect(self._toggle_play)

        self._btn_next = QPushButton("⏭")
        self._btn_next.setObjectName("playerBtnNext")
        self._btn_next.setFixedSize(44, 44)
        self._btn_next.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_next.clicked.connect(self._next_track)
        btn_row.addWidget(self._btn_prev)
        btn_row.addWidget(self._btn_play)
        btn_row.addWidget(self._btn_next)
        btn_row.addStretch()
        cvl.addLayout(btn_row)

        vol_row = QHBoxLayout()
        vol_ic = QLabel("🔈")
        vol_ic.setObjectName("playerVolumeIcon")
        self._volume = QSlider(Qt.Orientation.Horizontal)
        self._volume.setObjectName("playerVolume")
        self._volume.setRange(0, 100)
        self._volume.setValue(75)
        self._volume.valueChanged.connect(self._apply_volume)
        vol_row.addWidget(vol_ic)
        vol_row.addWidget(self._volume, stretch=1)
        cvl.addLayout(vol_row)

        self._status = QLabel("")
        self._status.setObjectName("playerStatusHint")
        self._status.setWordWrap(True)
        cvl.addWidget(self._status)

        lv.addWidget(ctrl_block)
        root.addWidget(self._left_card, alignment=Qt.AlignmentFlag.AlignTop)

        # --- Правая карточка: альбом и треклист ---
        self._right_card = QFrame()
        self._right_card.setObjectName("playerRightCard")
        self._right_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        rv = QVBoxLayout(self._right_card)
        rv.setContentsMargins(0, 0, 0, 0)
        rv.setSpacing(0)

        tab_header = QFrame()
        tab_header.setObjectName("playerAlbumTab")
        th_lay = QHBoxLayout(tab_header)
        th_lay.setContentsMargins(20, 12, 20, 10)
        self._album_title = QLabel("ИМЯ АЛЬБОМА")
        self._album_title.setObjectName("playerAlbumTitle")
        th_lay.addWidget(self._album_title)
        th_lay.addStretch()
        rv.addWidget(tab_header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setObjectName("playerAlbumScroll")
        self._list_host = QWidget()
        self._list_host.setStyleSheet("background: transparent;")
        self._list_layout = QVBoxLayout(self._list_host)
        self._list_layout.setContentsMargins(12, 8, 12, 12)
        self._list_layout.setSpacing(4)
        scroll.setWidget(self._list_host)
        rv.addWidget(scroll, stretch=1)

        root.addWidget(self._right_card, stretch=1)

        sh = QGraphicsDropShadowEffect(self._left_card)
        sh.setBlurRadius(28)
        sh.setOffset(4, 6)
        sh.setColor(QColor(0, 0, 0, 90))
        self._left_card.setGraphicsEffect(sh)
        sh2 = QGraphicsDropShadowEffect(self._right_card)
        sh2.setBlurRadius(28)
        sh2.setOffset(4, 6)
        sh2.setColor(QColor(0, 0, 0, 90))
        self._right_card.setGraphicsEffect(sh2)

        self._apply_volume()
        self._sync_play_button_icon()
        self._rebuild_list()

    def _sync_play_button_icon(self) -> None:
        st = self._player.playbackState()
        if st == QMediaPlayer.PlaybackState.PlayingState:
            self._btn_play.setText("❚❚")
        else:
            self._btn_play.setText("▶")

    def _on_state_changed(self, state) -> None:
        self._sync_play_button_icon()

    def _on_media_status(self, status: QMediaPlayer.MediaStatus) -> None:
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            if self._index + 1 < len(self._playlist):
                self._index += 1
                self._load_current()
                self._rebuild_list()
                self._player.play()

    def _on_player_error(self, error, message: str = "") -> None:
        self._status.setText(f"Ошибка воспроизведения: {message or str(error)}")

    def _apply_volume(self) -> None:
        v = self._volume.value() / 100.0
        cap = playback_settings.quality_volume_cap()
        v = min(v * cap, cap)
        v *= playback_settings.normalization_factor()
        self._audio.setVolume(min(1.0, max(0.0, v)))

    def refresh_playback_settings(self) -> None:
        self._apply_volume()

    def _on_position_changed(self, pos: int) -> None:
        if self._user_seeking:
            return
        dur = self._player.duration()
        if dur > 0:
            self._progress.blockSignals(True)
            self._progress.setRange(0, int(dur))
            self._progress.setValue(int(pos))
            self._progress.blockSignals(False)
        self._t_elapsed.setText(_fmt_ms(pos))
        td = self._player.duration()
        self._t_total.setText(_fmt_ms(td) if td > 0 else "—")

    def _on_duration_changed(self, dur: int) -> None:
        if dur > 0:
            self._progress.setRange(0, int(dur))

    def _on_seek_released(self) -> None:
        self._user_seeking = False
        self._player.setPosition(self._progress.value())

    def _toggle_play(self) -> None:
        if not self._playlist:
            self._status.setText("Выберите трек в поиске.")
            return
        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._player.pause()
        else:
            if self._player.playbackState() == QMediaPlayer.PlaybackState.StoppedState:
                self._load_current()
            self._player.play()

    def _prev_track(self) -> None:
        if self._index > 0:
            self._index -= 1
            self._load_current()
            self._rebuild_list()
            if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                self._player.play()

    def _next_track(self) -> None:
        if self._index + 1 < len(self._playlist):
            self._index += 1
            self._load_current()
            self._rebuild_list()
            if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                self._player.play()

    def _load_current(self) -> None:
        if not self._playlist:
            return
        item = self._playlist[self._index]
        ref = (item.get("playback_ref") or "").strip()
        self._status.setText("")
        if not ref:
            self._status.setText("Нет ссылки на аудио (playback_ref).")
            self._player.stop()
            return
        url = QUrl.fromUserInput(ref)
        self._player.setSource(url)
        self._load_artwork(item.get("artwork_url"))
        title = item.get("title") or "—"
        artist = item.get("artist") or ""
        self._album_title.setText(_album_name(item))
        self._now_title.setText(str(title))
        self._now_artist.setText(str(artist))
        self._art.setToolTip(f"{title}\n{artist}")

    def _load_artwork(self, url: Optional[str]) -> None:
        if self._art_reply:
            self._art_reply.abort()
            self._art_reply.deleteLater()
            self._art_reply = None
        if not url:
            self._art.clear()
            self._art.setText("♪")
            return
        req = QNetworkRequest(QUrl(url))
        self._art_reply = self._nam.get(req)
        self._art_reply.finished.connect(self._on_art_finished)

    def _on_art_finished(self) -> None:
        reply = self.sender()
        if not isinstance(reply, QNetworkReply) or reply.error() != QNetworkReply.NetworkError.NoError:
            if reply:
                reply.deleteLater()
            self._art_reply = None
            return
        data = reply.readAll()
        reply.deleteLater()
        self._art_reply = None
        img = QImage()
        if img.loadFromData(QByteArray(data)):
            pm = QPixmap.fromImage(img.scaled(220, 220, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation))
            self._art.setPixmap(pm)
            self._art.setText("")
        else:
            self._art.clear()
            self._art.setText("♪")

    def _rebuild_list(self) -> None:
        while self._list_layout.count():
            it = self._list_layout.takeAt(0)
            w = it.widget()
            if w:
                w.deleteLater()
        for i, item in enumerate(self._playlist):
            title = item.get("title") or "название песни"
            artist = item.get("artist") or "исполнитель"
            row = _TrackRow(
                str(title).lower(),
                str(artist).lower(),
                i == self._index,
                on_click=lambda idx=i: self._select_track(idx),
            )
            self._list_layout.addWidget(row)
        for _ in range(max(0, 7 - len(self._playlist))):
            row = _TrackRow("—", "", False, on_click=None)
            row.setEnabled(False)
            self._list_layout.addWidget(row)
        self._list_layout.addStretch()

    def _select_track(self, idx: int) -> None:
        if idx < 0 or idx >= len(self._playlist):
            return
        self._index = idx
        was_playing = self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
        self._load_current()
        self._rebuild_list()
        if was_playing or playback_settings.autoplay():
            self._player.play()

    def set_track(self, music_item: dict) -> None:
        """Задаёт текущий трек (из поиска); очередь = один трек, пока нет альбома из API."""
        self._playlist = [dict(music_item)]
        self._index = 0
        self._load_current()
        self._rebuild_list()
        title = music_item.get("title") or "Название трека"
        artist = music_item.get("artist") or "Исполнитель"
        self._status.setText("")
        if playback_settings.autoplay():
            self._player.play()
        else:
            self._player.stop()
            self._sync_play_button_icon()
