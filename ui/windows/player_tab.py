from __future__ import annotations

import copy
import json
import os
from typing import TYPE_CHECKING, Callable, Optional
from urllib.parse import parse_qs, urlparse

from PyQt6.QtCore import Qt, QUrl, QUrlQuery, QByteArray, QTimer, QSize, QCoreApplication, pyqtSignal, QRectF
from PyQt6.QtGui import QPixmap, QImage, QColor, QIcon
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
)
# WebEngine: версии PyQt6 и PyQt6-WebEngine должны совпадать.
QWebEngineView = None  # type: ignore[misc, assignment]
CratesWebEnginePage = None  # type: ignore[misc, assignment]
CratesYoutubeRequestInterceptor = None  # type: ignore[misc, assignment]
try:
    from PyQt6.QtWebEngineCore import QWebEnginePage as _QWebEnginePage
    from PyQt6.QtWebEngineCore import QWebEngineUrlRequestInterceptor
    from PyQt6.QtWebEngineWidgets import QWebEngineView as _QWebEngineView

    class CratesWebEnginePage(_QWebEnginePage):
        """Для части сетей/прокси Chromium ругается на сертификат — принимаем переопределяемые."""

        def certificateError(self, error):
            try:
                if error.isOverridable():
                    error.acceptCertificate()
            except Exception:
                pass
            return True

    class CratesYoutubeRequestInterceptor(QWebEngineUrlRequestInterceptor):
        """
        YouTube CDN (googlevideo, ytimg) ожидает нормальный Referer с youtube.com;
        без него часто ломается плеер (в т.ч. «ошибка 153» / настройка плеера).
        """

        def interceptRequest(self, info) -> None:
            try:
                host = (info.requestUrl().host() or "").lower()
                if not host:
                    return
                if (
                    "googlevideo.com" in host
                    or host == "ytimg.com"
                    or host.endswith(".ytimg.com")
                    or "ggpht.com" in host
                ):
                    info.setHttpHeader(b"Referer", b"https://www.youtube.com/")
            except Exception:
                pass

    QWebEngineView = _QWebEngineView
except (ImportError, OSError):
    pass

from ui import playback_settings
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
    return "ИМЯ АЛЬБОМА"


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


def _fmt_listen_total_sec(sec: int) -> str:
    if sec <= 0:
        return "0 с"
    if sec < 60:
        return f"{sec} с"
    m, s = divmod(sec, 60)
    if m < 60:
        return f"{m} мин {s:02d} с" if s else f"{m} мин"
    h, m = divmod(m, 60)
    return f"{h} ч {m} мин"


def _media_url_from_playback_ref(ref: str) -> QUrl:
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


def _is_page_playback_ref(ref: str) -> bool:
    r = (ref or "").strip().lower()
    if not r:
        return False
    # Streaming pages are not direct media streams for QMediaPlayer/FFmpeg.
    page_hosts = (
        "youtube.com",
        "youtu.be",
        "music.yandex",
        "vk.com/music",
        "music.vk.com",
    )
    return any(h in r for h in page_hosts)


def _web_embed_url(ref: str) -> str:
    """
    Converts known page URLs to embeddable player URLs.
    Falls back to original URL when conversion is not supported.
    """
    raw = (ref or "").strip()
    if not raw:
        return raw
    try:
        u = urlparse(raw)
        host = (u.netloc or "").lower()
        if "youtube.com" in host:
            if u.path == "/watch":
                vid = parse_qs(u.query).get("v", [None])[0]
                if vid:
                    return f"https://www.youtube.com/embed/{vid}?autoplay=1"
            if u.path.startswith("/shorts/"):
                vid = u.path.split("/shorts/", 1)[1].split("/", 1)[0]
                if vid:
                    return f"https://www.youtube.com/embed/{vid}?autoplay=1"
        if "youtu.be" in host:
            vid = (u.path or "").lstrip("/").split("/", 1)[0]
            if vid:
                return f"https://www.youtube.com/embed/{vid}?autoplay=1"
    except Exception:
        return raw
    return raw


def _youtube_embed_id(ref: str) -> Optional[str]:
    raw = (ref or "").strip()
    if not raw:
        return None
    try:
        u = urlparse(raw)
        host = (u.netloc or "").lower()
        if "youtube.com" in host:
            if u.path == "/watch":
                return parse_qs(u.query).get("v", [None])[0]
            if u.path.startswith("/shorts/"):
                return u.path.split("/shorts/", 1)[1].split("/", 1)[0]
        if "youtu.be" in host:
            return (u.path or "").lstrip("/").split("/", 1)[0]
    except Exception:
        return None
    return None


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
        self._web: Optional[QWebEngineView] = None
        self._yt_request_interceptor: Optional[object] = None
        self._last_youtube_embed = False

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
        lbl_trek = QLabel("ТРЕК")
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
        vol_row.addWidget(vol_ic)
        vol_row.addWidget(self._volume, stretch=1)
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
        self._album_title = QLabel("ИМЯ АЛЬБОМА")
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
        self._btn_like.setToolTip("В избранное")
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
        self._btn_review.setToolTip("Написать рецензию")
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

        # Built-in player surface for YouTube/Yandex/VK page links.
        if QWebEngineView is not None:
            from PyQt6.QtWebEngineCore import QWebEngineSettings

            self._web = QWebEngineView(self)
            self._web.setObjectName("playerWebView")
            if CratesWebEnginePage is not None:
                self._web.setPage(CratesWebEnginePage(self._web))
            ws = self._web.settings()
            ws.setAttribute(
                QWebEngineSettings.WebAttribute.PlaybackRequiresUserGesture, False
            )
            ws.setAttribute(
                QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True
            )
            prof = self._web.page().profile()
            prof.setHttpUserAgent(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            )
            if CratesYoutubeRequestInterceptor is not None:
                self._yt_request_interceptor = CratesYoutubeRequestInterceptor()
                prof.setUrlRequestInterceptor(self._yt_request_interceptor)
            self._web.setMinimumHeight(200)
            self._web.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Expanding,
            )
            self._web.loadFinished.connect(self._on_web_loaded)
            rv.addWidget(self._web, stretch=1)
            self._web.hide()

        root.addWidget(self._left_card, stretch=2)
        root.addWidget(self._right_card, stretch=5)

        self._apply_volume()
        self._sync_play_button_icon()
        self._rebuild_list()

    def _set_web_panel_visible(self, visible: bool) -> None:
        """WebEngine даёт белую область на локальных файлах — показываем только для YouTube/страниц."""
        if self._web is None:
            return
        if visible:
            self._web.setMinimumHeight(200)
            self._web.setMaximumHeight(16777215)
            self._web.show()
        else:
            self._web.hide()
            self._web.setMinimumHeight(0)
            self._web.setMaximumHeight(0)

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

    def _flush_listen_session(self) -> None:
        if not self._session or not self._playlist:
            self._listen_accum_ms = 0
            self._listen_last_pos_ms = None
            return
        item = self._playlist[self._index]
        mid = self._listen_target_music_item_id(item)
        ref = (item.get("playback_ref") or "").strip()
        if mid is None or _is_page_playback_ref(ref):
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
        item = self._playlist[self._index]
        ref = (item.get("playback_ref") or "").strip()
        if _is_page_playback_ref(ref):
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

    def _on_player_error(self, error, message: str = "") -> None:
        pass

    def _apply_volume(self) -> None:
        v = self._volume.value() / 100.0
        cap = playback_settings.quality_volume_cap()
        v = min(v * cap, cap)
        v *= playback_settings.normalization_factor()
        self._audio.setVolume(min(1.0, max(0.0, v)))
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

    def _toggle_play(self) -> None:
        if not self._playlist:
            return
        current = self._playlist[self._index] if self._playlist else {}
        ref = (current.get("playback_ref") or "").strip()
        if ref and _is_page_playback_ref(ref):
            if self._web is not None:
                self._set_web_panel_visible(True)
                self._load_web_ref(ref)
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
        ref = (item.get("playback_ref") or "").strip()
        pdur = int(self._player.duration())
        si = effective_duration_sec(item)
        item_ms = int(si * 1000) if si else 0
        if _is_page_playback_ref(ref):
            return item_ms
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
        ref = (item.get("playback_ref") or "").strip()
        if not ref:
            self._set_web_panel_visible(False)
            self._player.stop()
            self._load_artwork(None)
            self._refresh_track_sidebar()
            self._refresh_progress_time_labels(0)
            return
        if _is_page_playback_ref(ref):
            self._player.stop()
            self._set_web_panel_visible(True)
            if self._web is not None:
                self._load_web_ref(ref)
            self._load_artwork(self._artwork_url_for_current(item))
            self._refresh_track_sidebar()
            self._refresh_progress_time_labels(0)
            return
        self._set_web_panel_visible(False)
        self._player.stop()
        self._player.setSource(QUrl())
        QCoreApplication.processEvents()
        url = _media_url_from_playback_ref(ref)
        self._player.setSource(url)
        self._load_artwork(self._artwork_url_for_current(item))
        self._refresh_track_sidebar()
        self._refresh_progress_time_labels(0)

    def _load_web_ref(self, ref: str) -> None:
        if self._web is None:
            return
        self._last_youtube_embed = False
        vid = _youtube_embed_id(ref)
        if vid:
            self._last_youtube_embed = True
            # Прямой URL вместо setHtml+iframe: меньше проблем с TLS/QUIC к googlevideo.
            u = QUrl(f"https://www.youtube.com/embed/{vid}")
            q = QUrlQuery()
            q.addQueryItem("autoplay", "1")
            q.addQueryItem("rel", "0")
            q.addQueryItem("modestbranding", "1")
            q.addQueryItem("playsinline", "1")
            q.addQueryItem("enablejsapi", "1")
            # Для встроенного плеера YouTube сверяет origin страницы с параметром.
            q.addQueryItem("origin", "https://www.youtube.com")
            u.setQuery(q)
            dest = QUrl(u.toString())
            wv = self._web
            wv.load(QUrl("about:blank"))
            QTimer.singleShot(50, lambda: wv.load(dest))
            return
        embed = _web_embed_url(ref)
        self._last_youtube_embed = (
            "youtube.com" in embed.lower() or "youtu.be" in (ref or "").lower()
        )
        dest2 = QUrl.fromUserInput(embed)
        wv2 = self._web
        wv2.load(QUrl("about:blank"))
        QTimer.singleShot(50, lambda: wv2.load(dest2))

    def _on_web_loaded(self, ok: bool) -> None:
        pass

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
        kind_ru = {
            "track": "трек",
            "album": "альбом",
            "playlist": "плейлист",
        }.get(kind_raw, kind_raw)
        prov = (item.get("provider") or "").strip()
        bits: list[str] = []
        if dur != "—":
            bits.append(dur)
        if alb != "—":
            bits.append(f"альбом: {alb}")
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
            self._info_stats.setText(
                f"Слушателей: {lc}  ·  Наслушано всего: {_fmt_listen_total_sec(lt)}  ·  "
                f"В избранном: {fc}  ·  Рецензии: {rc}"
            )
        else:
            self._info_stats.setText(
                "Счётчики и избранное — после входа в аккаунт"
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
        title = str(item.get("title") or "трек")
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
            title = item.get("title") or "название песни"
            raw_artist = (item.get("artist") or "").strip()
            artist_show = raw_artist.lower() if raw_artist else "исполнитель"
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
        # Web-плейбек (YouTube/Яндекс/VK) нельзя проигрывать через QMediaPlayer,
        # иначе снова появятся FFmpeg/TLS ошибки.
        item = self._playlist[self._index] if self._playlist else {}
        ref = (item.get("playback_ref") or "").strip()
        if not _is_page_playback_ref(ref) and (was_playing or playback_settings.autoplay()):
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
        ref = (item.get("playback_ref") or "").strip()
        if _is_page_playback_ref(ref):
            self._player.stop()
            self._sync_play_button_icon()
            self._emit_current_item_changed()
            self._emit_playback_state()
            self._emit_progress_state()
            return
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
        ref = (item.get("playback_ref") or "").strip()
        if _is_page_playback_ref(ref):
            # Встроенный web-плеер уже загрузил ссылку в _load_current().
            self._player.stop()
            self._sync_play_button_icon()
            self._emit_current_item_changed()
            self._emit_playback_state()
            self._emit_progress_state()
            return
        if playback_settings.autoplay():
            self._player.play()
        else:
            self._player.stop()
            self._sync_play_button_icon()
        self._emit_current_item_changed()
        self._emit_playback_state()
        self._emit_progress_state()
