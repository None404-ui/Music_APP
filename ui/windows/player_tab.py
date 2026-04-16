from __future__ import annotations

import array
import copy
import json
import os
from typing import TYPE_CHECKING, Callable, Optional

from PyQt6.QtCore import Qt, QUrl, QByteArray, QIODevice, QTimer, QSize, QCoreApplication, pyqtSignal, QRectF
from PyQt6.QtGui import QPixmap, QImage, QColor, QIcon
from PyQt6.QtMultimedia import (
    QAudioBuffer,
    QAudioBufferOutput,
    QAudioFormat,
    QAudioSink,
    QMediaDevices,
    QMediaPlayer,
)
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
)

from ui import i18n, equalizer_settings, playback_resume, playback_settings
from ui.audio_eq import GraphicEQProcessor
from ui.equalizer_popup import EqualizerPopup
from ui.artist_link_label import ArtistLinkLabel
from ui.cover_art import CoverArtWidget
from ui.duration_util import effective_duration_sec, format_duration_mm_ss
from ui.interactive_fx import InteractiveRowFrame, StatefulIconButton
from backend.api_client import resolve_backend_media_url

if TYPE_CHECKING:
    from backend.session import UserSession

_ICONS_DIR = os.path.join(os.path.dirname(__file__), "..", "icons")


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
    return i18n.tr("ИМЯ АЛЬБОМА")


def _album_display(item: dict) -> str:
    meta = item.get("meta_json")
    if isinstance(meta, str) and meta.strip():
        try:
            j = json.loads(meta)
            if isinstance(j, dict) and j.get("album"):
                return str(j["album"])
        except json.JSONDecodeError:
            pass
    return "—"


def _media_url_from_audio_url(ref: str) -> QUrl:
    """
    Локальные файлы (Windows/Linux): QUrl.fromUserInput даёт сбои → FFmpeg «Permission denied».
    Надёжно открываем через fromLocalFile после normpath/expanduser.
    """
    r = (ref or "").strip()
    if not r:
        return QUrl()
    low = r.lower()
    if low.startswith(("http://", "https://")):
        return QUrl(r)
    if low.startswith("file:"):
        return QUrl(r)
    expanded = os.path.expandvars(os.path.expanduser(r))
    norm = os.path.normpath(expanded)
    if os.path.isfile(norm):
        return QUrl.fromLocalFile(norm)
    norm2 = os.path.normpath(expanded.replace("/", os.sep))
    if norm2 != norm and os.path.isfile(norm2):
        return QUrl.fromLocalFile(norm2)
    u_try = QUrl.fromUserInput(r)
    if u_try.isLocalFile():
        local = u_try.toLocalFile()
        local = os.path.normpath(local)
        if os.path.isfile(local):
            return QUrl.fromLocalFile(local)
    return QUrl.fromUserInput(r)


class _TrackRow(InteractiveRowFrame):
    def __init__(
        self,
        title: str,
        artist_display: str,
        active: bool,
        on_click=None,
        parent=None,
        subtitle: str = "",
        on_open_artist: Optional[Callable[[str], None]] = None,
        artist_catalog: str = "",
    ):
        super().__init__(radius=8, active_alpha=24, hover_alpha=28, press_alpha=46, parent=parent)
        self.setObjectName("playerTrackRowActive" if active else "playerTrackRow")
        self._on_click = on_click
        self.set_active(active)
        if on_click:
            self.setCursor(Qt.CursorShape.PointingHandCursor)

        row = QHBoxLayout(self)
        row.setContentsMargins(10, 8, 14, 8)
        row.setSpacing(12)

        thumb = QLabel()
        thumb.setFixedSize(36, 36)
        thumb.setObjectName("playerTrackThumb")
        thumb.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        row.addWidget(thumb)

        col = QVBoxLayout()
        col.setSpacing(2)
        t = QLabel(title)
        t.setObjectName("playerTrackTitle")
        t.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        cat = (artist_catalog or "").strip()
        if cat and on_open_artist:
            a = ArtistLinkLabel()
            a.setObjectName("playerTrackArtist")
            a.set_artist(cat)
            a.artist_clicked.connect(on_open_artist)
        else:
            a = QLabel(artist_display)
            a.setObjectName("playerTrackArtist")
        col.addWidget(t)
        col.addWidget(a)
        if subtitle:
            s = QLabel(subtitle)
            s.setObjectName("playerTrackMeta")
            s.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            col.addWidget(s)
        row.addLayout(col, stretch=1)
        self.install_interaction_filters()

    def mousePressEvent(self, event) -> None:
        if self._on_click:
            self._on_click()
        super().mousePressEvent(event)


class PlayerArtworkWidget(CoverArtWidget):
    """Обложка трека: квадратная область с маской и рамкой."""

    _RADIUS = 22
    _BORDER = 3

    def __init__(self, parent=None):
        super().__init__(
            radius=self._RADIUS,
            border_width=self._BORDER,
            border_color=QColor(49, 41, 56),
            fill_color=QColor(216, 228, 236),
            mask_color=QColor("#D4D4A8"),
            placeholder_text="♪",
            placeholder_color=QColor(0, 51, 102),
            placeholder_px=32,
            top_align_square=True,
            parent=parent,
        )
        self.setObjectName("playerArtPanel")
        self.setMinimumSize(160, 160)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        self.set_placeholder_scale(0.22, min_px=28, max_px=56)
        self.set_fill_gradient(QColor(216, 228, 236), QColor(184, 200, 212))


class PlayerTab(QWidget):
    """Изменения избранного / рецензий — для обновления вкладки «Моё»."""

    library_changed = pyqtSignal()
    current_item_changed = pyqtSignal(dict)
    playback_state_changed = pyqtSignal(bool)
    transport_state_changed = pyqtSignal(bool, bool)
    progress_changed = pyqtSignal(int, int)
    volume_changed = pyqtSignal(int)

    def __init__(
        self,
        session: Optional["UserSession"] = None,
        on_open_artist: Optional[Callable[[str], None]] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("playerPage")
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        self._session = session
        self._on_open_artist = on_open_artist
        # Обложка карточки альбома, если у треков в очереди своей нет
        self._queue_artwork_fallback: str = ""
        self._favorite_id: Optional[int] = None

        self._playlist: list[dict] = []
        self._index = 0
        self._context_music_item_id: Optional[int] = None
        self._context_stats: dict = {}
        self._listen_accum_ms = 0
        self._listen_last_pos_ms: Optional[int] = None
        self._user_seeking = False
        self._art_reply: Optional[QNetworkReply] = None

        self._player = QMediaPlayer(self)
        self._graphic_eq_channels = 2
        self._graphic_eq = GraphicEQProcessor(self._graphic_eq_channels)
        self._buf_out = QAudioBufferOutput(self)
        self._buf_out.audioBufferReceived.connect(self._on_eq_audio_buffer)
        self._player.setAudioBufferOutput(self._buf_out)
        self._player.setAudioOutput(None)
        self._eq_sink: Optional[QAudioSink] = None
        self._eq_sink_io: Optional[QIODevice] = None
        self._eq_sink_format: Optional[QAudioFormat] = None
        self.sync_equalizer_from_settings()
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
        self._left_card.setMinimumWidth(260)
        self._left_card.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Expanding,
        )
        lv = QVBoxLayout(self._left_card)
        lv.setContentsMargins(0, 0, 0, 0)
        lv.setSpacing(0)

        self._art = PlayerArtworkWidget()
        lv.addWidget(self._art, 0)

        band = QFrame()
        band.setObjectName("playerTrackBand")
        bl = QVBoxLayout(band)
        bl.setContentsMargins(14, 10, 14, 10)
        lbl_trek = QLabel(i18n.tr("ТРЕК"))
        lbl_trek.setObjectName("playerTrekLabel")
        bl.addWidget(lbl_trek)
        self._now_title = QLabel("—")
        self._now_title.setObjectName("playerNowTitle")
        self._now_title.setWordWrap(True)
        bl.addWidget(self._now_title)
        self._now_artist = ArtistLinkLabel()
        self._now_artist.setObjectName("playerNowArtist")
        if on_open_artist:
            self._now_artist.artist_clicked.connect(on_open_artist)
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
        self._progress.valueChanged.connect(self._on_progress_slider_moved)

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
        self._ico_player_prev = QIcon(os.path.join(_ICONS_DIR, "player_prev.svg"))
        self._ico_player_next = QIcon(os.path.join(_ICONS_DIR, "player_next.svg"))
        self._ico_player_play = QIcon(os.path.join(_ICONS_DIR, "player_play.svg"))
        self._ico_player_pause = QIcon(os.path.join(_ICONS_DIR, "player_pause.svg"))
        self._ico_player_volume = QIcon(os.path.join(_ICONS_DIR, "player_volume.svg"))
        self._ico_player_eq = QIcon(os.path.join(_ICONS_DIR, "player_equalizer.svg"))

        self._btn_prev = QPushButton()
        self._btn_prev.setObjectName("playerBtnPrev")
        self._btn_prev.setIcon(self._ico_player_prev)
        self._btn_prev.setIconSize(QSize(28, 28))
        self._btn_prev.setFlat(True)
        self._btn_prev.setFixedSize(44, 44)
        self._btn_prev.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_prev.clicked.connect(self._prev_track)

        self._btn_play = QPushButton()
        self._btn_play.setObjectName("playerBtnPlayCircle")
        self._btn_play.setIcon(self._ico_player_play)
        self._btn_play.setIconSize(QSize(32, 32))
        self._btn_play.setFlat(True)
        self._btn_play.setFixedSize(52, 52)
        self._btn_play.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_play.clicked.connect(self._toggle_play)

        self._btn_next = QPushButton()
        self._btn_next.setObjectName("playerBtnNext")
        self._btn_next.setIcon(self._ico_player_next)
        self._btn_next.setIconSize(QSize(28, 28))
        self._btn_next.setFlat(True)
        self._btn_next.setFixedSize(44, 44)
        self._btn_next.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_next.clicked.connect(self._next_track)
        btn_row.addWidget(self._btn_prev)
        btn_row.addWidget(self._btn_play)
        btn_row.addWidget(self._btn_next)
        btn_row.addStretch()
        cvl.addLayout(btn_row)

        vol_row = QHBoxLayout()
        vol_ic = QPushButton()
        vol_ic.setObjectName("playerVolumeIcon")
        vol_ic.setIcon(self._ico_player_volume)
        vol_ic.setIconSize(QSize(22, 22))
        vol_ic.setFlat(True)
        vol_ic.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        vol_ic.setFixedSize(28, 28)
        vol_ic.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._volume = QSlider(Qt.Orientation.Horizontal)
        self._volume.setObjectName("playerVolume")
        self._volume.setRange(0, 100)
        self._volume.setValue(75)
        self._volume.valueChanged.connect(self._apply_volume)
        self._btn_playback_settings = QPushButton()
        self._btn_playback_settings.setObjectName("playerEqBtn")
        self._btn_playback_settings.setIcon(self._ico_player_eq)
        self._btn_playback_settings.setIconSize(QSize(22, 22))
        self._btn_playback_settings.setFlat(True)
        self._btn_playback_settings.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_playback_settings.setFixedSize(28, 28)
        self._btn_playback_settings.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_playback_settings.setToolTip(i18n.tr("Эквалайзер"))
        self._btn_playback_settings.clicked.connect(self._toggle_equalizer_popup)
        self._equalizer_popup = EqualizerPopup(
            self,
            on_changed=self.sync_equalizer_from_settings,
        )
        vol_row.addWidget(vol_ic)
        vol_row.addWidget(self._volume, stretch=1)
        vol_row.addWidget(self._btn_playback_settings)
        cvl.addLayout(vol_row)

        lv.addWidget(ctrl_block, stretch=0)

        # --- Правая карточка: альбом и треклист ---
        self._right_card = QFrame()
        self._right_card.setObjectName("playerRightCard")
        self._right_card.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        rv = QVBoxLayout(self._right_card)
        rv.setContentsMargins(0, 0, 0, 0)
        rv.setSpacing(0)

        tab_header = QFrame()
        tab_header.setObjectName("playerAlbumTab")
        th_lay = QHBoxLayout(tab_header)
        th_lay.setContentsMargins(20, 12, 20, 10)
        self._album_title = QLabel(i18n.tr("ИМЯ АЛЬБОМА"))
        self._album_title.setObjectName("playerAlbumTitle")
        th_lay.addWidget(self._album_title)
        th_lay.addStretch()
        rv.addWidget(tab_header)

        self._info_panel = QFrame()
        self._info_panel.setObjectName("playerTrackInfoPanel")
        info_lay = QVBoxLayout(self._info_panel)
        info_lay.setContentsMargins(16, 10, 16, 12)
        info_lay.setSpacing(8)

        self._info_line_title = QLabel("")
        self._info_line_title.setObjectName("playerInfoTitleLine")
        self._info_line_title.setWordWrap(True)
        info_lay.addWidget(self._info_line_title)

        self._info_line_artist = ArtistLinkLabel()
        self._info_line_artist.setObjectName("playerInfoArtistLine")
        self._info_line_artist.setWordWrap(True)
        if on_open_artist:
            self._info_line_artist.artist_clicked.connect(on_open_artist)
        info_lay.addWidget(self._info_line_artist)

        self._info_line_extra = QLabel("")
        self._info_line_extra.setObjectName("playerInfoTitleLine")
        self._info_line_extra.setWordWrap(True)
        info_lay.addWidget(self._info_line_extra)

        self._info_stats = QLabel("")
        self._info_stats.setObjectName("playerInfoStats")
        self._info_stats.setWordWrap(True)
        info_lay.addWidget(self._info_stats)

        tools = QHBoxLayout()
        tools.setSpacing(10)
        like_ic = os.path.join(_ICONS_DIR, "player_like.svg")
        like_ic_checked = os.path.join(_ICONS_DIR, "player_like_filled.svg")
        rev_ic = os.path.join(_ICONS_DIR, "player_review_mono.svg")
        self._btn_like = StatefulIconButton(
            like_ic,
            checked_icon_path=like_ic_checked,
            base_color="#312938",
            hover_color="#A14016",
            pressed_color="#CB883A",
            checked_color="#CB883A",
            parent=self,
        )
        self._btn_like.setObjectName("playerLikeBtn")
        self._btn_like.setCheckable(True)
        self._btn_like.setFixedSize(40, 36)
        self._btn_like.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_like.setIconSize(QSize(22, 22))
        self._btn_like.setToolTip(i18n.tr("В избранное"))
        self._btn_like.toggled.connect(self._on_like_toggled)

        self._btn_review = StatefulIconButton(
            rev_ic,
            base_color="#312938",
            hover_color="#004766",
            pressed_color="#2A7A8C",
            checked_color="#2A7A8C",
            pulse_on_toggle=False,
            parent=self,
        )
        self._btn_review.setObjectName("playerReviewBtn")
        self._btn_review.setFixedSize(40, 36)
        self._btn_review.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_review.setIconSize(QSize(22, 22))
        self._btn_review.setToolTip(i18n.tr("Написать рецензию"))
        self._btn_review.clicked.connect(self._on_review_clicked)

        tools.addWidget(self._btn_like)
        tools.addWidget(self._btn_review)
        tools.addStretch()
        info_lay.addLayout(tools)
        rv.addWidget(self._info_panel)

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

        root.addWidget(self._left_card, stretch=2)
        root.addWidget(self._right_card, stretch=5)

        self._apply_volume()
        self._sync_play_button_icon()
        self._rebuild_list()

    def _context_is_album_or_catalog_playlist(self) -> bool:
        if not self._context_stats:
            return False
        k = (self._context_stats.get("kind") or "").strip().lower()
        return k in ("album", "playlist")

    def _favorite_target_mid(self, item: dict) -> Optional[int]:
        """Избранное и рецензии: в очереди альбома/плейлиста — id карточки, иначе id трека."""
        if self._context_music_item_id is not None and self._context_is_album_or_catalog_playlist():
            return int(self._context_music_item_id)
        tid = item.get("id")
        if tid is not None:
            return int(tid)
        if self._context_music_item_id is not None:
            return int(self._context_music_item_id)
        return None

    def _listen_target_music_item_id(self, item: dict) -> Optional[int]:
        """Засчёт прослушивания — только реальный трек, не запись альбома."""
        tid = item.get("id")
        if tid is not None:
            return int(tid)
        return None

    def has_active_track(self) -> bool:
        return bool(self._playlist)

    def is_playing(self) -> bool:
        return self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState

    def can_play_previous(self) -> bool:
        return bool(self._playlist) and self._index > 0

    def can_play_next(self) -> bool:
        return bool(self._playlist) and self._index + 1 < len(self._playlist)

    def current_progress(self) -> tuple[int, int]:
        if not self._playlist:
            return 0, 0
        item = self._playlist[self._index]
        pos = int(self._player.position())
        dur = int(self._duration_ms_for_ui(item))
        return pos, dur

    def _stats_source_for_item(self, item: dict) -> dict:
        if (
            self._context_music_item_id
            and self._context_stats
            and self._context_is_album_or_catalog_playlist()
        ):
            merged = dict(item)
            for key in (
                "listens_count",
                "listen_time_total_sec",
                "favorites_count",
                "reviews_count",
                "user_favorited",
            ):
                merged[key] = self._context_stats.get(key)
            return merged
        if item.get("id") is None and self._context_music_item_id and self._context_stats:
            merged = dict(item)
            for key in (
                "listens_count",
                "listen_time_total_sec",
                "favorites_count",
                "reviews_count",
                "user_favorited",
            ):
                merged[key] = self._context_stats.get(key)
            return merged
        return dict(item)

    def current_item_snapshot(self) -> dict:
        if not self._playlist or self._index >= len(self._playlist):
            return {}
        item = dict(self._playlist[self._index])
        stats_src = self._stats_source_for_item(item)
        item.update(stats_src)
        item["artwork_url_resolved"] = self._artwork_url_for_current(item) or ""
        item["album_display"] = _album_display(item)
        item["duration_ms"] = self._duration_ms_for_ui(item)
        item["position_ms"] = int(self._player.position())
        item["is_playing"] = self.is_playing()
        item["can_prev"] = self.can_play_previous()
        item["can_next"] = self.can_play_next()
        item["like_enabled"] = (
            self._favorite_target_mid(item) is not None and self._session is not None
        )
        return item

    def _emit_current_item_changed(self) -> None:
        self.current_item_changed.emit(self.current_item_snapshot())
        self.transport_state_changed.emit(
            self.can_play_previous(),
            self.can_play_next(),
        )

    def _emit_playback_state(self) -> None:
        self.playback_state_changed.emit(self.is_playing())

    def _emit_progress_state(self) -> None:
        pos, dur = self.current_progress()
        self.progress_changed.emit(pos, dur)

    def toggle_playback(self) -> None:
        self._toggle_play()

    def play_previous(self) -> None:
        self._prev_track()

    def play_next(self) -> None:
        self._next_track()

    def set_current_favorite_checked(self, checked: bool) -> None:
        if not self._playlist or not self._btn_like.isEnabled():
            return
        checked = bool(checked)
        if self._btn_like.isChecked() == checked:
            return
        self._btn_like.setChecked(checked)

    def flush_listen_for_close(self) -> None:
        """Перед закрытием окна — отправить накопленное прослушивание текущего трека."""
        self._flush_listen_session()

    def build_language_restart_snapshot(self) -> Optional[dict]:
        if not self._playlist:
            return None
        return {
            "playlist": copy.deepcopy(self._playlist),
            "index": int(self._index),
            "position_ms": int(self._player.position()),
            "was_playing": self.is_playing(),
            "volume_percent": self.current_volume_percent(),
            "context_music_item_id": self._context_music_item_id,
            "queue_artwork_fallback": (self._queue_artwork_fallback or "").strip(),
        }

    def save_language_restart_snapshot(self) -> None:
        data = self.build_language_restart_snapshot()
        if data:
            playback_resume.save_language_restart_snapshot(data)

    def shutdown_audio_for_close(self) -> None:
        """Остановить декодер и вывод, чтобы при пересоздании окна звук не «висел» в фоне."""
        self._player.stop()
        self._player.setSource(QUrl())
        self._release_eq_sink()
        QCoreApplication.processEvents()

    def apply_language_restart_snapshot(self, data: dict) -> bool:
        """Восстановить очередь и позицию после перезапуска окна (смена языка)."""
        pl = data.get("playlist")
        if not isinstance(pl, list) or not pl:
            return False
        clean: list[dict] = []
        for t in pl:
            if isinstance(t, dict):
                clean.append(copy.deepcopy(dict(t)))
        if not clean:
            return False

        ctx = data.get("context_music_item_id")
        if ctx is not None:
            try:
                self._context_music_item_id = int(ctx)
            except (TypeError, ValueError):
                self._context_music_item_id = None
        else:
            self._context_music_item_id = None

        self._queue_artwork_fallback = str(data.get("queue_artwork_fallback") or "").strip()
        self._context_stats = {}
        self._playlist = clean
        idx = int(data.get("index", 0))
        self._index = max(0, min(idx, len(self._playlist) - 1))
        item = self._playlist[self._index]

        self._listen_accum_ms = 0
        self._listen_last_pos_ms = None

        self._sync_now_playing_labels(item)
        self._apply_item_to_info_panel(item)
        self._player.stop()
        self._player.setSource(QUrl())
        QCoreApplication.processEvents()

        self._t_elapsed.setText("0:00")
        self._t_total.setText("—")
        self._progress.blockSignals(True)
        self._progress.setRange(0, 1000)
        self._progress.setValue(0)
        self._progress.blockSignals(False)

        try:
            self.set_volume_percent(int(data.get("volume_percent", 75)))
        except (TypeError, ValueError):
            pass

        self._load_current()
        self._rebuild_list()

        cid = self._context_music_item_id
        if cid is not None and self._session:
            QTimer.singleShot(0, lambda m=int(cid): self._pull_context_stats(m))

        pos_ms = int(data.get("position_ms", 0))
        was_playing = bool(data.get("was_playing", False))
        self._schedule_restore_transport(pos_ms, was_playing)
        return True

    def _schedule_restore_transport(self, pos_ms: int, play: bool) -> None:
        pos_ms = max(0, int(pos_ms))
        play = bool(play)

        def tick(attempt: int) -> None:
            if attempt > 80:
                self._apply_volume()
                self._sync_play_button_icon()
                self._emit_current_item_changed()
                self._emit_playback_state()
                self._emit_progress_state()
                return
            dur = int(self._player.duration())
            if dur <= 0:
                QTimer.singleShot(50, lambda: tick(attempt + 1))
                return
            self._player.setPosition(min(pos_ms, max(0, dur - 1)))
            self._apply_volume()
            if play:
                self._player.play()
            else:
                self._player.pause()
            self._sync_play_button_icon()
            self._emit_current_item_changed()
            self._emit_playback_state()
            self._emit_progress_state()

        QTimer.singleShot(0, lambda: tick(0))

    def _flush_listen_session(self) -> None:
        if not self._session or not self._playlist:
            self._listen_accum_ms = 0
            self._listen_last_pos_ms = None
            return
        item = self._playlist[self._index]
        mid = self._listen_target_music_item_id(item)
        if mid is None:
            self._listen_accum_ms = 0
            self._listen_last_pos_ms = None
            return
        dur = self._player.duration()
        ed = effective_duration_sec(item)
        duration_ms = (
            int(dur) if dur and dur > 0 else int((ed or 0) * 1000)
        )
        threshold_ms = min(30_000, duration_ms // 2) if duration_ms > 0 else 30_000
        if self._listen_accum_ms >= threshold_ms:
            st, _ = self._session.client.post_json(
                f"/api/music-items/{mid}/record-listen/",
                {
                    "listened_ms": int(self._listen_accum_ms),
                    "duration_ms": duration_ms,
                },
            )
            if st in (200, 201):
                sm = self._listen_target_music_item_id(item)
                if sm is not None:
                    QTimer.singleShot(
                        80, lambda m=sm: self._refresh_stats_after_listen(m)
                    )
        self._listen_accum_ms = 0
        self._listen_last_pos_ms = None

    def _refresh_stats_after_listen(self, mid: int) -> None:
        if not self._playlist or self._index >= len(self._playlist):
            return
        item = self._playlist[self._index]
        if item.get("id") is None and mid == self._context_music_item_id:
            self._pull_context_stats(mid)
        elif item.get("id") is not None and int(item["id"]) == mid:
            self._pull_music_item(mid)

    def _pull_context_stats(self, mid: int) -> None:
        if not self._session:
            return
        st, data = self._session.client.get_json(f"/api/music-items/{mid}/")
        if st != 200 or not isinstance(data, dict):
            return
        if mid != self._context_music_item_id:
            return
        self._context_stats = data
        if self._playlist and self._index < len(self._playlist):
            self._apply_item_to_info_panel(self._playlist[self._index])
            self._emit_current_item_changed()

    def _tick_listen_accum(self, pos: int) -> None:
        if not self._playlist or not self._session:
            return
        if self._player.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
            self._listen_last_pos_ms = pos
            return
        if self._listen_last_pos_ms is not None and pos >= self._listen_last_pos_ms:
            d = pos - self._listen_last_pos_ms
            if 0 < d < 5000:
                self._listen_accum_ms += d
        self._listen_last_pos_ms = pos

    def _sync_play_button_icon(self) -> None:
        st = self._player.playbackState()
        if st == QMediaPlayer.PlaybackState.PlayingState:
            self._btn_play.setIcon(self._ico_player_pause)
        else:
            self._btn_play.setIcon(self._ico_player_play)

    def _on_state_changed(self, state) -> None:
        self._sync_play_button_icon()
        self._emit_playback_state()
        self._emit_current_item_changed()
        self._emit_progress_state()

    def _on_media_status(self, status: QMediaPlayer.MediaStatus) -> None:
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self._flush_listen_session()
            if self._index + 1 < len(self._playlist):
                self._index += 1
                self._load_current()
                self._rebuild_list()
                self._player.play()
                return
            # Последний трек: при автовоспроизведении — снова с начала очереди (один трек = повтор)
            if playback_settings.autoplay() and self._playlist:
                self._index = 0
                self._load_current()
                self._rebuild_list()
                self._player.play()

    def _on_player_error(self, error, message: str = "") -> None:
        pass

    def _compute_master_linear(self) -> float:
        v = self._volume.value() / 100.0
        cap = playback_settings.quality_volume_cap()
        v = min(v * cap, cap)
        cur = (
            self._playlist[self._index]
            if self._playlist and 0 <= self._index < len(self._playlist)
            else None
        )
        v *= playback_settings.normalization_gain_for_item(cur)
        return min(1.0, max(0.0, v))

    def _apply_volume(self) -> None:
        ml = self._compute_master_linear()
        if self._eq_sink is not None:
            self._eq_sink.setVolume(ml)
        self.volume_changed.emit(int(self._volume.value()))

    def current_volume_percent(self) -> int:
        return int(self._volume.value())

    def set_volume_percent(self, value: int) -> None:
        self._volume.setValue(max(0, min(100, int(value))))

    def cycle_volume_preset(self) -> int:
        presets = (0, 25, 50, 75, 100)
        current = self.current_volume_percent()
        for level in presets:
            if current < level:
                self.set_volume_percent(level)
                return level
        self.set_volume_percent(presets[0])
        return presets[0]

    def refresh_playback_settings(self) -> None:
        self._apply_volume()

    def sync_equalizer_from_settings(self) -> None:
        gains = equalizer_settings.band_gains_db()
        self._graphic_eq.set_gains_db(gains)

    def _release_eq_sink(self) -> None:
        if self._eq_sink is not None:
            self._eq_sink.stop()
            self._eq_sink.deleteLater()
            self._eq_sink = None
        self._eq_sink_io = None
        self._eq_sink_format = None

    def _ensure_eq_sink(self, fmt: QAudioFormat) -> bool:
        if self._eq_sink is not None and self._eq_sink_format is not None:
            if (
                fmt.sampleRate() == self._eq_sink_format.sampleRate()
                and fmt.channelCount() == self._eq_sink_format.channelCount()
                and fmt.sampleFormat() == self._eq_sink_format.sampleFormat()
            ):
                return self._eq_sink_io is not None
        self._release_eq_sink()
        dev = QMediaDevices.defaultAudioOutput()
        if dev.isNull():
            return False
        self._eq_sink = QAudioSink(dev, fmt, self)
        self._eq_sink_io = self._eq_sink.start()
        if self._eq_sink_io is None:
            self._eq_sink = None
            return False
        self._eq_sink_format = fmt
        self._eq_sink.setVolume(self._compute_master_linear())
        return True

    def _write_all_sink(self, data: bytes) -> None:
        if not self._eq_sink_io:
            return
        off = 0
        b = data
        while off < len(b):
            n = self._eq_sink_io.write(b[off:])
            if n is None or n <= 0:
                break
            off += int(n)

    def _eq_process_int16(self, raw: bytes, n_ch: int) -> bytes:
        a = array.array("h")
        a.frombytes(raw)
        for i in range(0, len(a), n_ch):
            for c in range(n_ch):
                x = a[i + c] / 32768.0
                y = self._graphic_eq.process_sample(x, c)
                if y > 1.0:
                    y = 1.0
                elif y < -1.0:
                    y = -1.0
                iv = int(round(y * 32767.0))
                a[i + c] = max(-32768, min(32767, iv))
        return a.tobytes()

    def _eq_process_float32(self, raw: bytes, n_ch: int) -> bytes:
        a = array.array("f")
        a.frombytes(raw)
        for i in range(0, len(a), n_ch):
            for c in range(n_ch):
                y = self._graphic_eq.process_sample(float(a[i + c]), c)
                if y > 1.0:
                    y = 1.0
                elif y < -1.0:
                    y = -1.0
                a[i + c] = y
        return a.tobytes()

    def _on_eq_audio_buffer(self, buffer: QAudioBuffer) -> None:
        if not buffer.isValid() or buffer.frameCount() == 0:
            return
        fmt = buffer.format()
        if not fmt.isValid():
            return
        n_ch = fmt.channelCount()
        if n_ch < 1:
            return
        if self._graphic_eq_channels != n_ch:
            self._graphic_eq_channels = n_ch
            self._graphic_eq = GraphicEQProcessor(n_ch)
            self._graphic_eq.set_gains_db(equalizer_settings.band_gains_db())
        self._graphic_eq.set_sample_rate(float(fmt.sampleRate()))

        raw = bytes(buffer.data())
        bpf = fmt.bytesPerFrame()
        expected = buffer.frameCount() * bpf
        if len(raw) < expected:
            return
        raw = raw[:expected]

        if not self._ensure_eq_sink(fmt):
            return

        sf = fmt.sampleFormat()
        if sf == QAudioFormat.SampleFormat.Int16:
            out = self._eq_process_int16(raw, n_ch)
        elif sf == QAudioFormat.SampleFormat.Float:
            out = self._eq_process_float32(raw, n_ch)
        else:
            out = raw
        self._write_all_sink(out)

    def _toggle_equalizer_popup(self) -> None:
        self._equalizer_popup.toggle_near(self._btn_playback_settings)

    def open_review_dialog(self) -> None:
        self._on_review_clicked()

    def _on_position_changed(self, pos: int) -> None:
        if self._user_seeking:
            self._listen_last_pos_ms = pos
            self._tick_listen_accum(pos)
            self._refresh_progress_time_labels()
            self._emit_progress_state()
            return
        self._tick_listen_accum(pos)
        self._refresh_progress_time_labels(int(pos))
        self._emit_progress_state()

    def _on_duration_changed(self, dur: int) -> None:
        if dur > 0:
            self._refresh_progress_time_labels()
        self._emit_progress_state()

    def _on_progress_slider_moved(self, v: int) -> None:
        if self._user_seeking:
            self._refresh_progress_time_labels(int(v))

    def _on_seek_released(self) -> None:
        self._user_seeking = False
        self._player.setPosition(self._progress.value())
        self._graphic_eq.reset()

    def _toggle_play(self) -> None:
        if not self._playlist:
            return
        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._player.pause()
        else:
            if self._player.playbackState() == QMediaPlayer.PlaybackState.StoppedState:
                self._load_current()
            self._player.play()

    def _prev_track(self) -> None:
        if self._index > 0:
            self._flush_listen_session()
            self._index -= 1
            self._load_current()
            self._rebuild_list()
            if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                self._player.play()

    def _next_track(self) -> None:
        if self._index + 1 < len(self._playlist):
            self._flush_listen_session()
            self._index += 1
            self._load_current()
            self._rebuild_list()
            if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                self._player.play()

    def _sync_now_playing_labels(self, item: dict) -> None:
        """Всегда обновляет левую колонку и шапку альбома из словаря трека."""
        title = item.get("title") or "—"
        artist = item.get("artist") or ""
        self._album_title.setText(_album_name(item))
        self._now_title.setText(str(title))
        self._now_artist.set_artist(str(artist).strip())
        self._art.setToolTip(f"{title}\n{artist}")
        self._emit_current_item_changed()

    def _duration_ms_for_ui(self, item: dict) -> int:
        """Длительность для шкалы: из плеера, иначе из данных трека (как на главной)."""
        pdur = int(self._player.duration())
        si = effective_duration_sec(item)
        item_ms = int(si * 1000) if si else 0
        if pdur > 0:
            return pdur
        return item_ms

    def _refresh_progress_time_labels(self, pos_ms: Optional[int] = None) -> None:
        if not self._playlist:
            self._t_elapsed.setText("0:00")
            self._t_total.setText("—")
            self._progress.blockSignals(True)
            self._progress.setRange(0, 1000)
            self._progress.setValue(0)
            self._progress.blockSignals(False)
            self._emit_progress_state()
            return
        item = self._playlist[self._index]
        dur_ms = self._duration_ms_for_ui(item)
        if self._user_seeking and pos_ms is None:
            pos_ms = int(self._progress.value())
        elif pos_ms is None:
            pos_ms = int(self._player.position())
        self._progress.blockSignals(True)
        if dur_ms > 0:
            self._progress.setRange(0, dur_ms)
            if not self._user_seeking:
                self._progress.setValue(min(int(pos_ms), dur_ms))
        else:
            self._progress.setRange(0, 1000)
            if not self._user_seeking:
                self._progress.setValue(0)
        self._progress.blockSignals(False)
        self._t_elapsed.setText(_fmt_ms(int(pos_ms)))
        self._t_total.setText(_fmt_ms(dur_ms) if dur_ms > 0 else "—")
        self._emit_progress_state()

    def _artwork_url_for_current(self, item: dict) -> Optional[str]:
        base = self._session.client.base_url if self._session else ""
        for raw in (
            (item.get("artwork_url") or "").strip(),
            (self._queue_artwork_fallback or "").strip(),
        ):
            if not raw:
                continue
            u = resolve_backend_media_url(base, raw)
            if u.startswith(("http://", "https://")):
                return u
        return None

    def _load_current(self) -> None:
        if not self._playlist:
            return
        self._listen_accum_ms = 0
        self._listen_last_pos_ms = None
        item = self._playlist[self._index]
        self._sync_now_playing_labels(item)
        base = self._session.client.base_url if self._session else ""
        ref = resolve_backend_media_url(base, (item.get("audio_url") or "").strip())
        if not ref:
            self._player.stop()
            self._load_artwork(None)
            self._refresh_track_sidebar()
            self._refresh_progress_time_labels(0)
            self._apply_volume()
            self._graphic_eq.reset()
            return
        self._player.stop()
        self._player.setSource(QUrl())
        QCoreApplication.processEvents()
        url = _media_url_from_audio_url(ref)
        self._player.setSource(url)
        self._load_artwork(self._artwork_url_for_current(item))
        self._refresh_track_sidebar()
        self._refresh_progress_time_labels(0)
        self._apply_volume()
        self._graphic_eq.reset()

    def _load_artwork(self, url: Optional[str]) -> None:
        if self._art_reply is not None:
            prev = self._art_reply
            self._art_reply = None
            # abort() сразу шлёт finished → _on_art_finished снимет prev с deleteLater
            prev.abort()
        if not url:
            self._art.clear_cover()
            return
        req = QNetworkRequest(QUrl(url))
        self._art_reply = self._nam.get(req)
        self._art_reply.finished.connect(self._on_art_finished)

    def _on_art_finished(self) -> None:
        reply = self.sender()
        if not isinstance(reply, QNetworkReply):
            return
        # Уже заменили запрос в _load_artwork (после abort) — только освобождаем reply.
        if reply is not self._art_reply:
            reply.deleteLater()
            return
        self._art_reply = None
        if reply.error() != QNetworkReply.NetworkError.NoError:
            reply.deleteLater()
            return
        data = reply.readAll()
        reply.deleteLater()
        img = QImage()
        if img.loadFromData(QByteArray(data)):
            self._art.set_cover_pixmap(QPixmap.fromImage(img))
        else:
            self._art.clear_cover()

    def _refresh_track_sidebar(self) -> None:
        if not self._playlist:
            self._info_line_title.setText("")
            self._info_line_artist.set_artist("")
            self._info_line_extra.setText("")
            self._info_stats.setText("")
            self._btn_like.setEnabled(False)
            self._btn_review.setEnabled(False)
            self._emit_current_item_changed()
            return
        item = self._playlist[self._index]
        self._apply_item_to_info_panel(item)
        tid = item.get("id")
        if tid is not None and self._session:
            QTimer.singleShot(0, lambda m=int(tid): self._pull_music_item(m))
        elif self._context_music_item_id is not None and self._session:
            QTimer.singleShot(
                0, lambda m=self._context_music_item_id: self._pull_context_stats(m)
            )

    def _apply_item_to_info_panel(self, item: dict) -> None:
        ks = (
            "listens_count",
            "listen_time_total_sec",
            "favorites_count",
            "reviews_count",
            "user_favorited",
        )
        stats_src = item
        if (
            self._context_music_item_id
            and self._context_stats
            and self._context_is_album_or_catalog_playlist()
        ):
            stats_src = {**item, **{k: self._context_stats.get(k) for k in ks}}
        elif (
            item.get("id") is None
            and self._context_music_item_id
            and self._context_stats
        ):
            stats_src = {**item, **{k: self._context_stats.get(k) for k in ks}}
        title = item.get("title") or "—"
        artist = (item.get("artist") or "").strip()
        self._info_line_title.setText(str(title))
        self._info_line_artist.set_artist(artist)
        alb = _album_display(item)
        dur = format_duration_mm_ss(effective_duration_sec(item))
        kind_raw = (item.get("kind") or "").strip()
        kind_ru = i18n.music_kind_label(kind_raw) if kind_raw else ""
        prov = (item.get("provider") or "").strip()
        bits: list[str] = []
        if dur != "—":
            bits.append(dur)
        if alb != "—":
            bits.append(f"{i18n.tr('альбом:')} {alb}")
        if kind_ru:
            bits.append(kind_ru)
        if prov:
            bits.append(prov)
        self._info_line_extra.setText(" · ".join(bits) if bits else "")
        lc = int(stats_src.get("listens_count") or 0)
        lt = int(stats_src.get("listen_time_total_sec") or 0)
        fc = int(stats_src.get("favorites_count") or 0)
        rc = int(stats_src.get("reviews_count") or 0)
        mid = self._favorite_target_mid(item)
        if mid is not None and self._session:
            self._info_stats.setText(i18n.player_stats_line(lc, lt, fc, rc))
        else:
            self._info_stats.setText(
                i18n.tr("Счётчики и избранное — после входа в аккаунт")
                if not self._session
                else ""
            )
        can = mid is not None and self._session is not None
        self._btn_like.setEnabled(can)
        self._btn_review.setEnabled(can)
        self._btn_like.blockSignals(True)
        self._btn_like.setChecked(bool(stats_src.get("user_favorited")))
        self._btn_like.blockSignals(False)
        self._favorite_id = None
        if can and stats_src.get("user_favorited") and mid is not None:
            QTimer.singleShot(0, lambda m=int(mid): self._resolve_favorite_id(m))
        self._emit_current_item_changed()

    def _resolve_favorite_id(self, mid: int) -> None:
        if not self._session:
            return
        st, data = self._session.client.get_json(f"/api/favorites/?music_item={mid}")
        if st != 200:
            return
        rows = (
            data
            if isinstance(data, list)
            else (data.get("results") if isinstance(data, dict) else None)
        )
        if isinstance(rows, list) and rows:
            fid = rows[0].get("id")
            if fid is not None:
                self._favorite_id = int(fid)

    def _pull_music_item(self, mid: int) -> None:
        if not self._session:
            return
        st, data = self._session.client.get_json(f"/api/music-items/{mid}/")
        if st != 200 or not isinstance(data, dict):
            return
        if not self._playlist or self._index >= len(self._playlist):
            return
        if self._playlist[self._index].get("id") != mid:
            return
        self._playlist[self._index].update(data)
        self._sync_now_playing_labels(self._playlist[self._index])
        self._apply_item_to_info_panel(self._playlist[self._index])
        self._apply_volume()
        self._emit_current_item_changed()

    def _on_like_toggled(self, checked: bool) -> None:
        if not self._session or not self._playlist:
            return
        item = self._playlist[self._index]
        mid = self._favorite_target_mid(item)
        if mid is None:
            return
        mid = int(mid)
        store: dict = item
        if self._context_is_album_or_catalog_playlist() and self._context_stats:
            store = self._context_stats
        elif item.get("id") is None and self._context_stats:
            store = self._context_stats
        if checked:
            st, body = self._session.client.post_json("/api/favorites/", {"music_item": mid})
            if st in (200, 201) and isinstance(body, dict):
                fid = body.get("id")
                if fid is not None:
                    self._favorite_id = int(fid)
                store["user_favorited"] = True
                store["favorites_count"] = int(store.get("favorites_count") or 0) + 1
                self._apply_item_to_info_panel(item)
                self._emit_current_item_changed()
                self.library_changed.emit()
            else:
                self._btn_like.blockSignals(True)
                self._btn_like.setChecked(False)
                self._btn_like.blockSignals(False)
        else:
            if self._favorite_id is None:
                self._resolve_favorite_id(mid)
            fid = self._favorite_id
            if fid is not None:
                st, _ = self._session.client.request_json(
                    "DELETE", f"/api/favorites/{fid}/"
                )
                if st in (200, 204):
                    self._favorite_id = None
                    store["user_favorited"] = False
                    store["favorites_count"] = max(
                        0, int(store.get("favorites_count") or 0) - 1
                    )
                    self._apply_item_to_info_panel(item)
                    self._emit_current_item_changed()
                    self.library_changed.emit()
                    return
            self._btn_like.blockSignals(True)
            self._btn_like.setChecked(True)
            self._btn_like.blockSignals(False)

    def _on_review_clicked(self) -> None:
        from PyQt6.QtWidgets import QDialog

        from ui.windows.write_review_dialog import WriteReviewDialog

        if not self._session or not self._playlist:
            return
        item = self._playlist[self._index]
        mid = self._favorite_target_mid(item)
        if mid is None:
            return
        mid = int(mid)
        title = str(item.get("title") or i18n.tr("трек"))
        if self._context_is_album_or_catalog_playlist() and self._context_stats:
            title = str(self._context_stats.get("title") or title)
        elif item.get("id") is None and self._context_stats:
            title = str(self._context_stats.get("title") or title)
        dlg = WriteReviewDialog(
            self._session.client,
            mid,
            title,
            self,
        )
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.submitted():
            self.library_changed.emit()
            if item.get("id") is None and mid == self._context_music_item_id:
                QTimer.singleShot(150, lambda m=mid: self._pull_context_stats(m))
            else:
                QTimer.singleShot(150, lambda: self._pull_music_item(mid))
            self._emit_current_item_changed()

    def _rebuild_list(self) -> None:
        while self._list_layout.count():
            it = self._list_layout.takeAt(0)
            w = it.widget()
            if w:
                w.deleteLater()
        for i, item in enumerate(self._playlist):
            title = item.get("title") or i18n.tr("название песни")
            raw_artist = (item.get("artist") or "").strip()
            artist_show = raw_artist.lower() if raw_artist else i18n.tr("исполнитель")
            alb = _album_display(item)
            dur = format_duration_mm_ss(effective_duration_sec(item))
            sub = " · ".join(x for x in (alb, dur) if x and x != "—")
            row = _TrackRow(
                str(title).lower(),
                artist_show,
                i == self._index,
                on_click=lambda idx=i: self._select_track(idx),
                subtitle=sub,
                on_open_artist=self._on_open_artist,
                artist_catalog=raw_artist,
            )
            self._list_layout.addWidget(row)
        self._list_layout.addStretch()
        self.transport_state_changed.emit(
            self.can_play_previous(),
            self.can_play_next(),
        )

    def _select_track(self, idx: int) -> None:
        if idx < 0 or idx >= len(self._playlist):
            return
        if idx != self._index:
            self._flush_listen_session()
        self._index = idx
        was_playing = self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
        self._load_current()
        self._rebuild_list()
        if was_playing or playback_settings.autoplay():
            self._player.play()
        self._emit_current_item_changed()
        self._emit_playback_state()
        self._emit_progress_state()

    def set_queue(
        self,
        tracks: list[dict],
        start_index: int = 0,
        context_music_item_id: Optional[int] = None,
        source_card: Optional[dict] = None,
    ) -> None:
        """Очередь из нескольких треков (карточка альбома / подборка на «Популярное»)."""
        self._flush_listen_session()
        self._context_music_item_id = context_music_item_id
        self._context_stats = {}
        self._queue_artwork_fallback = ""
        if isinstance(source_card, dict):
            self._queue_artwork_fallback = (source_card.get("artwork_url") or "").strip()
        self._context_stats = {}
        clean: list[dict] = []
        for t in tracks:
            if isinstance(t, dict):
                clean.append(copy.deepcopy(dict(t)))
        if not clean:
            return
        self._playlist = clean
        self._index = max(0, min(int(start_index), len(self._playlist) - 1))
        item = self._playlist[self._index]
        self._sync_now_playing_labels(item)
        self._apply_item_to_info_panel(item)
        self._player.stop()
        self._player.setSource(QUrl())
        QCoreApplication.processEvents()
        self._t_elapsed.setText("0:00")
        self._t_total.setText("—")
        self._progress.blockSignals(True)
        self._progress.setRange(0, 1000)
        self._progress.setValue(0)
        self._progress.blockSignals(False)
        self._load_current()
        self._rebuild_list()
        if context_music_item_id is not None and self._session:
            QTimer.singleShot(
                0,
                lambda m=context_music_item_id: self._pull_context_stats(m),
            )
        if playback_settings.autoplay():
            self._player.play()
        else:
            self._player.stop()
            self._sync_play_button_icon()
        self._emit_current_item_changed()
        self._emit_playback_state()
        self._emit_progress_state()

    def set_track(self, music_item: dict) -> None:
        """Задаёт текущий трек (из поиска); очередь = один трек, пока нет альбома из API."""
        self._flush_listen_session()
        self._queue_artwork_fallback = ""
        self._context_music_item_id = None
        self._context_stats = {}
        item = copy.deepcopy(dict(music_item))
        self._playlist = [item]
        self._index = 0
        self._sync_now_playing_labels(item)
        self._apply_item_to_info_panel(item)
        self._player.stop()
        self._player.setSource(QUrl())
        QCoreApplication.processEvents()
        self._t_elapsed.setText("0:00")
        self._t_total.setText("—")
        self._progress.blockSignals(True)
        self._progress.setRange(0, 1000)
        self._progress.setValue(0)
        self._progress.blockSignals(False)
        self._load_current()
        self._rebuild_list()
        if playback_settings.autoplay():
            self._player.play()
        else:
            self._player.stop()
            self._sync_play_button_icon()
        self._emit_current_item_changed()
        self._emit_playback_state()
        self._emit_progress_state()
