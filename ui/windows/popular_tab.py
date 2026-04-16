from __future__ import annotations

from typing import Callable, Optional

from PyQt6.QtCore import QEvent, Qt, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QColor, QImage, QMouseEvent, QPixmap
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PyQt6.QtWidgets import QApplication, QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget

from backend.api_client import resolve_backend_media_url
from backend.session import UserSession
from ui.artist_link_label import ArtistLinkLabel
from ui.cover_art import CoverArtWidget
from ui.interactive_fx import InteractiveRowFrame, animate_scrollbar_to
from ui.track_like_review import TrackLikeReviewBar
from ui.duration_util import effective_duration_sec, format_duration_mm_ss

_album_cover_nam: QNetworkAccessManager | None = None


def _album_cover_network() -> QNetworkAccessManager:
    global _album_cover_nam
    if _album_cover_nam is None:
        app = QApplication.instance()
        _album_cover_nam = QNetworkAccessManager(app)
    return _album_cover_nam


class AlbumCard(QFrame):
    _CARD_SIZE = 140
    _CARD_PAD = 2
    _COVER_SIZE = _CARD_SIZE - _CARD_PAD * 2

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("albumCard")
        self.setFixedSize(self._CARD_SIZE, 210)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cover_reply: QNetworkReply | None = None
        self._on_open = None
        self._on_open_artist = None
        self._payload: dict = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(self._CARD_PAD, self._CARD_PAD, self._CARD_PAD, 4)
        layout.setSpacing(2)

        self._cover_normal_border = QColor("#89A194")
        self._cover_normal_fill = QColor("#BDB685")
        self._cover_normal_mask = QColor("#5c5748")
        self._cover_hover_border = QColor("#CB883A")
        self._cover_hover_fill = QColor("#d1c996")
        self._cover_hover_mask = QColor("#6d6756")

        self._cover = CoverArtWidget(
            radius=8,
            border_width=1,
            border_color=self._cover_normal_border,
            fill_color=self._cover_normal_fill,
            mask_color=self._cover_normal_mask,
            placeholder_text="♪",
            placeholder_color=QColor("#A14016"),
            placeholder_px=32,
        )
        self._cover.setFixedSize(self._COVER_SIZE, self._COVER_SIZE)
        self._cover.setObjectName("albumCover")
        self._cover.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._apply_cover_style(False)
        self._apply_cover_placeholder()

        self._artist = ArtistLinkLabel()
        self._artist.setObjectName("albumArtist")
        self._artist.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._name = QLabel("—")
        self._name.setObjectName("albumTitle")
        self._name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._name.setWordWrap(True)
        self._name.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        self._artist.artist_clicked.connect(self._on_artist_clicked)

        layout.addWidget(self._cover, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self._artist)
        layout.addWidget(self._name)

    def _abort_cover_load(self) -> None:
        if self._cover_reply is None:
            return
        reply = self._cover_reply
        self._cover_reply = None
        reply.abort()

    def _apply_cover_placeholder(self) -> None:
        self._cover.clear_cover()
        self._cover.setToolTip("Обложка не указана")

    def _apply_cover_style(self, hovered: bool) -> None:
        if hovered:
            self._cover.set_style_colors(
                border_color=self._cover_hover_border,
                fill_color=self._cover_hover_fill,
                mask_color=self._cover_hover_mask,
            )
        else:
            self._cover.set_style_colors(
                border_color=self._cover_normal_border,
                fill_color=self._cover_normal_fill,
                mask_color=self._cover_normal_mask,
            )

    def _on_cover_finished(self) -> None:
        reply = self.sender()
        if not isinstance(reply, QNetworkReply):
            return
        if self._cover_reply is not reply:
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
            self._cover.setToolTip("")
        finally:
            reply.deleteLater()

    def set_item(self, item: dict) -> None:
        self._abort_cover_load()
        self._payload = dict(item) if isinstance(item, dict) else {}
        title = (item.get("title") or "").strip() or "Без названия"
        self._name.setText(title)
        artist = (item.get("artist") or "").strip()
        self._artist.set_artist(artist)
        url = (item.get("artwork_url") or "").strip()
        self._apply_cover_placeholder()
        if url.startswith(("http://", "https://")):
            self._cover_reply = _album_cover_network().get(QNetworkRequest(QUrl(url)))
            self._cover_reply.finished.connect(self._on_cover_finished)

    def set_on_open(self, cb) -> None:
        self._on_open = cb

    def set_on_open_artist(self, cb) -> None:
        self._on_open_artist = cb

    def _on_artist_clicked(self, name: str) -> None:
        if self._on_open_artist and (name or "").strip():
            self._on_open_artist(name.strip())

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._on_open:
            self._on_open(self._payload)
        super().mouseReleaseEvent(event)

    def enterEvent(self, event) -> None:
        self._apply_cover_style(True)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._apply_cover_style(False)
        super().leaveEvent(event)


class ArtistWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._on_open_artist = None
        self._name_key = ""
        self._avatar_reply: QNetworkReply | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)
        layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self._avatar = QLabel()
        self._avatar.setObjectName("artistAvatar")
        self._avatar.setFixedSize(80, 80)
        self._avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._avatar.setText("♫")
        self._avatar.setStyleSheet("font-size: 24px; color: #A14016;")
        self._avatar.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        self._label = QLabel("—")
        self._label.setObjectName("artistName")
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setWordWrap(True)
        self._label.setFixedWidth(90)
        self._label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        layout.addWidget(self._avatar, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self._label, alignment=Qt.AlignmentFlag.AlignHCenter)

    def _abort_avatar_load(self) -> None:
        if self._avatar_reply is None:
            return
        reply = self._avatar_reply
        self._avatar_reply = None
        reply.abort()

    def _apply_avatar_placeholder(self) -> None:
        self._avatar.clear()
        self._avatar.setPixmap(QPixmap())
        self._avatar.setText("♫")

    def _on_avatar_finished(self) -> None:
        reply = self.sender()
        if not isinstance(reply, QNetworkReply):
            return
        if self._avatar_reply is not reply:
            reply.deleteLater()
            return
        self._avatar_reply = None
        try:
            if reply.error() != QNetworkReply.NetworkError.NoError:
                self._apply_avatar_placeholder()
                return
            data = reply.readAll()
            img = QImage()
            if not img.loadFromData(data):
                self._apply_avatar_placeholder()
                return
            pix = QPixmap.fromImage(img).scaled(
                80,
                80,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._avatar.setPixmap(pix)
            self._avatar.setText("")
        finally:
            reply.deleteLater()

    def set_on_open_artist(self, cb) -> None:
        self._on_open_artist = cb
        if self._name_key and self._on_open_artist:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def set_name(self, name: str) -> None:
        self._name_key = name.strip()
        self._label.setText(self._name_key or "—")
        if self._name_key and self._on_open_artist:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def set_avatar_url(self, url: str) -> None:
        self._abort_avatar_load()
        self._apply_avatar_placeholder()
        raw = (url or "").strip()
        if not raw.startswith(("http://", "https://")):
            return
        self._avatar_reply = _album_cover_network().get(QNetworkRequest(QUrl(raw)))
        self._avatar_reply.finished.connect(self._on_avatar_finished)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self._name_key
            and self._on_open_artist
        ):
            self._on_open_artist(self._name_key)
        super().mouseReleaseEvent(event)


class CarouselSection(QWidget):
    """Горизонтальная полоса: заголовок и стрелки справа; стрелки только при переполнении."""

    _SCROLL_STEP = 160

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setObjectName("carouselSection")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        header_row = QWidget()
        hl = QHBoxLayout(header_row)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(8)

        tl = QLabel(title)
        tl.setObjectName("subSectionHeading")
        hl.addWidget(tl, 0, Qt.AlignmentFlag.AlignVCenter)
        hl.addStretch(1)

        self._btn_left = QPushButton("‹")
        self._btn_left.setObjectName("btnCarouselArrow")
        self._btn_left.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_left.clicked.connect(self._scroll_left)
        self._btn_left.hide()

        self._btn_right = QPushButton("›")
        self._btn_right.setObjectName("btnCarouselArrow")
        self._btn_right.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_right.clicked.connect(self._scroll_right)
        self._btn_right.hide()

        hl.addWidget(self._btn_left, 0, Qt.AlignmentFlag.AlignVCenter)
        hl.addWidget(self._btn_right, 0, Qt.AlignmentFlag.AlignVCenter)
        root.addWidget(header_row)

        self._scroll = QScrollArea()
        self._scroll.setObjectName("carouselScroll")
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setWidgetResizable(False)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)

        self._inner = QWidget()
        self._inner.setObjectName("carouselInner")
        self._inner.setStyleSheet("background: transparent;")
        self._ilayout = QHBoxLayout(self._inner)
        self._ilayout.setContentsMargins(8, 0, 8, 0)
        self._ilayout.setSpacing(14)

        self._scroll.setWidget(self._inner)
        self._scroll.setMinimumHeight(208)
        self._scroll.viewport().installEventFilter(self)
        self._scroll.horizontalScrollBar().valueChanged.connect(self._sync_arrows)

        panel = QFrame()
        panel.setObjectName("carouselPanel")
        pl = QVBoxLayout(panel)
        pl.setContentsMargins(0, 0, 0, 0)
        pl.setSpacing(0)
        pl.addWidget(self._scroll)
        root.addWidget(panel)

    def set_items(self, items: list[QWidget]) -> None:
        while self._ilayout.count():
            it = self._ilayout.takeAt(0)
            w = it.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        for w in items:
            self._ilayout.addWidget(w)
        # После deleteLater размеры лейаута часто верны только в следующем цикле событий.
        QTimer.singleShot(0, self._finalize_carousel_geometry)

    def _finalize_carousel_geometry(self) -> None:
        self._ilayout.activate()
        hint = self._ilayout.sizeHint()
        w = max(hint.width(), 1)
        h = max(hint.height(), 1)
        self._inner.setMinimumWidth(w)
        self._inner.setMinimumHeight(h)
        self._inner.resize(w, h)
        self._scroll.updateGeometry()
        self._sync_arrows()

    def eventFilter(self, obj, event):
        if obj is self._scroll.viewport() and event.type() == QEvent.Type.Resize:
            self._sync_arrows()
        return False

    def _content_width(self) -> int:
        self._ilayout.activate()
        return self._ilayout.sizeHint().width()

    def _sync_arrows(self) -> None:
        view_w = self._scroll.viewport().width()
        if view_w <= 16:
            self._btn_left.hide()
            self._btn_right.hide()
            return
        cw = self._content_width()
        overflow = cw > view_w + 2
        self._btn_left.setVisible(overflow)
        self._btn_right.setVisible(overflow)
        bar = self._scroll.horizontalScrollBar()
        if overflow:
            self._btn_left.setEnabled(bar.value() > bar.minimum())
            self._btn_right.setEnabled(bar.value() < bar.maximum())
        else:
            bar.setValue(0)

    def _scroll_left(self) -> None:
        bar = self._scroll.horizontalScrollBar()
        animate_scrollbar_to(bar, bar.value() - self._SCROLL_STEP)

    def _scroll_right(self) -> None:
        bar = self._scroll.horizontalScrollBar()
        animate_scrollbar_to(bar, bar.value() + self._SCROLL_STEP)

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self._sync_arrows)


class TrackRow(InteractiveRowFrame):
    _THUMB_SIZE = 44

    def __init__(
        self,
        index: int,
        item: dict,
        on_play,
        parent=None,
        on_open_artist=None,
        session: Optional[UserSession] = None,
        dialog_parent: Optional[QWidget] = None,
        on_library_changed: Optional[Callable[[], None]] = None,
    ):
        super().__init__(radius=6, hover_alpha=30, press_alpha=52, active_alpha=18, parent=parent)
        self.setObjectName("trackRow")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._item = item
        self._on_play = on_play
        self._on_open_artist = on_open_artist
        self._thumb_reply: QNetworkReply | None = None

        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(10)

        num = QLabel(str(index))
        num.setObjectName("trackNumber")
        num.setAlignment(Qt.AlignmentFlag.AlignCenter)
        num.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        self._thumb = CoverArtWidget(
            radius=6,
            border_width=1,
            border_color=QColor("#89A194"),
            fill_color=QColor(49, 41, 56, 90),
            mask_color=QColor("#5c5748"),
            placeholder_text="♪",
            placeholder_color=QColor("#A14016"),
            placeholder_px=18,
        )
        self._thumb.setObjectName("trackRowThumb")
        self._thumb.setFixedSize(self._THUMB_SIZE, self._THUMB_SIZE)
        self._thumb.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._thumb_normal_border = QColor("#89A194")
        self._thumb_hover_border = QColor("#CB883A")
        self._thumb_normal_mask = QColor("#5c5748")
        self._thumb_hover_mask = QColor("#6d6756")
        self._apply_thumb_style(False)
        self._apply_thumb_placeholder()
        url = (item.get("artwork_url") or "").strip()
        if url.startswith(("http://", "https://")):
            self._thumb_reply = _album_cover_network().get(QNetworkRequest(QUrl(url)))
            self._thumb_reply.finished.connect(self._on_thumb_finished)

        title = QLabel((item.get("title") or "Без названия").strip())
        title.setObjectName("trackTitle")
        title.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        self._artist_link = ArtistLinkLabel()
        self._artist_link.setObjectName("trackArtist")
        self._artist_link.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        self._artist_link.set_artist((item.get("artist") or "").strip())
        if on_open_artist:
            self._artist_link.artist_clicked.connect(on_open_artist)

        likes = int(item.get("favorites_count") or 0)
        listens = int(item.get("listens_count") or 0)
        self._stats = QLabel(f"♥ {likes}  ·  {listens} слуш.")
        self._stats.setObjectName("trackStats")
        self._stats.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._stats.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        dur = QLabel(format_duration_mm_ss(effective_duration_sec(item)))
        dur.setObjectName("trackDuration")
        dur.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        dur.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        lay.addWidget(num, 0, Qt.AlignmentFlag.AlignVCenter)
        lay.addWidget(self._thumb, 0, Qt.AlignmentFlag.AlignVCenter)
        lay.addWidget(title, 2, Qt.AlignmentFlag.AlignVCenter)
        lay.addStretch(1)
        lay.addWidget(self._artist_link, 2, Qt.AlignmentFlag.AlignVCenter)
        lay.addStretch(1)
        lay.addWidget(self._stats, 0, Qt.AlignmentFlag.AlignVCenter)
        lay.addStretch(1)
        lay.addWidget(dur, 0, Qt.AlignmentFlag.AlignVCenter)

        self._actions_bar: TrackLikeReviewBar | None = None
        if session is not None and dialog_parent is not None and on_library_changed:
            self._actions_bar = TrackLikeReviewBar(
                item,
                session,
                dialog_parent,
                on_changed=on_library_changed,
                stats_label=self._stats,
            )
            lay.addWidget(self._actions_bar, 0, Qt.AlignmentFlag.AlignVCenter)
        self.install_interaction_filters()

    def _apply_thumb_placeholder(self) -> None:
        self._thumb.clear_cover()
        self._thumb.setToolTip("Обложка не указана")

    def _apply_thumb_style(self, hovered: bool) -> None:
        if hovered:
            self._thumb.set_style_colors(
                border_color=self._thumb_hover_border,
                mask_color=self._thumb_hover_mask,
            )
        else:
            self._thumb.set_style_colors(
                border_color=self._thumb_normal_border,
                mask_color=self._thumb_normal_mask,
            )

    def _on_thumb_finished(self) -> None:
        reply = self.sender()
        if not isinstance(reply, QNetworkReply):
            return
        if self._thumb_reply is not reply:
            reply.deleteLater()
            return
        self._thumb_reply = None
        try:
            if reply.error() != QNetworkReply.NetworkError.NoError:
                self._apply_thumb_placeholder()
                return
            data = reply.readAll()
            img = QImage()
            if not img.loadFromData(data):
                self._apply_thumb_placeholder()
                return
            self._thumb.set_cover_pixmap(QPixmap.fromImage(img))
            self._thumb.setToolTip("")
        finally:
            reply.deleteLater()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._on_play:
            if self._actions_bar is not None and self._actions_bar.geometry().contains(
                event.position().toPoint()
            ):
                super().mouseReleaseEvent(event)
                return
            self._on_play(self._item)
        super().mouseReleaseEvent(event)

    def enterEvent(self, event) -> None:
        self._apply_thumb_style(True)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._apply_thumb_style(False)
        super().leaveEvent(event)


class PopularTab(QWidget):
    library_changed = pyqtSignal()
    def __init__(
        self,
        session: UserSession,
        on_play_track=None,
        on_open_album=None,
        on_open_artist=None,
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("popularPage")
        self._session = session
        self._on_play_track = on_play_track
        self._on_open_album = on_open_album
        self._on_open_artist = on_open_artist

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        page_scroll = QScrollArea()
        page_scroll.setObjectName("popularPageScroll")
        page_scroll.setWidgetResizable(True)
        page_scroll.setFrameShape(QFrame.Shape.NoFrame)
        page_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        inner = QWidget()
        inner.setObjectName("popularPageInner")
        root = QVBoxLayout(inner)
        root.setContentsMargins(24, 16, 24, 24)
        root.setSpacing(10)

        page_title = QLabel("ПОПУЛЯРНОЕ")
        page_title.setObjectName("sectionHeading")
        root.addWidget(page_title)

        self._status = QLabel(inner)
        self._status.setObjectName("popularLoadStatus")
        self._status.hide()
        root.addWidget(self._status)

        self._album_carousel = CarouselSection("АЛЬБОМЫ")
        self._artist_carousel = CarouselSection("ИСПОЛНИТЕЛИ")

        root.addWidget(self._album_carousel)
        root.addSpacing(8)
        root.addWidget(self._artist_carousel)
        root.addSpacing(8)

        tracks_title = QLabel("ТРЕКИ")
        tracks_title.setObjectName("subSectionHeading")
        root.addWidget(tracks_title)

        self._tracks_wrap = QWidget()
        self._tracks_layout = QVBoxLayout(self._tracks_wrap)
        self._tracks_layout.setContentsMargins(0, 4, 0, 0)
        self._tracks_layout.setSpacing(8)
        root.addWidget(self._tracks_wrap)

        root.addStretch()

        page_scroll.setWidget(inner)
        outer.addWidget(page_scroll)

        QTimer.singleShot(0, self._load_popular)

    def reload_content(self) -> None:
        """Снова запросить каталог с сервера (после правок в админке / перезапуска бэкенда)."""
        self._load_popular()

    def _on_album_card_clicked(self, item: dict) -> None:
        if not self._on_open_album:
            return
        tracks = self._fetch_playback_queue(item)
        self._status.hide()
        if not tracks:
            return
        self._on_open_album(tracks, item)

    def _fetch_playback_queue(self, item: dict) -> list[dict]:
        prov = (item.get("provider") or "").strip()
        if prov == "collection":
            cid = item.get("external_id")
            if cid is None:
                return []
            path = f"/api/music-items/playback-queue/?collection_id={cid}"
        else:
            mid = item.get("id")
            if mid is None:
                return []
            path = f"/api/music-items/playback-queue/?music_item_id={mid}"
        st, body = self._session.client.get_json(path)
        if st != 200 or not isinstance(body, dict):
            return []
        raw = body.get("tracks")
        if not isinstance(raw, list):
            return []
        return [x for x in raw if isinstance(x, dict)]

    def _load_popular(self) -> None:
        try:
            status, body = self._session.client.get_json("/api/music-items/popular-feed/")
        except OSError as e:
            self._status.setText(f"Нет связи с сервером: {e}")
            self._status.show()
            self._album_carousel.set_items([])
            self._artist_carousel.set_items([])
            self._clear_tracks()
            return
        except Exception as e:
            self._status.setText(f"Ошибка загрузки: {e}")
            self._status.show()
            self._album_carousel.set_items([])
            self._artist_carousel.set_items([])
            self._clear_tracks()
            return

        if status != 200 or not isinstance(body, dict):
            detail = ""
            if isinstance(body, dict):
                detail = str(body.get("detail", body))
            self._status.setText(
                f"Сервер ответил {status}. {detail}".strip()
            )
            self._status.show()
            self._album_carousel.set_items([])
            self._artist_carousel.set_items([])
            self._clear_tracks()
            return

        self._status.hide()

        api_base = self._session.client.base_url if self._session else ""

        albums = body.get("albums")
        if not isinstance(albums, list):
            albums = []
        album_widgets: list[QWidget] = []
        for it in albums:
            if not isinstance(it, dict):
                continue
            if (it.get("kind") or "").strip().lower() != "album":
                continue
            row = dict(it)
            au = resolve_backend_media_url(
                api_base, (row.get("artwork_url") or "").strip()
            )
            if au:
                row["artwork_url"] = au
            c = AlbumCard()
            c.set_item(row)
            if self._on_open_album:
                c.set_on_open(self._on_album_card_clicked)
            if self._on_open_artist:
                c.set_on_open_artist(self._on_open_artist)
            album_widgets.append(c)
        self._album_carousel.set_items(album_widgets)

        artists = body.get("artists")
        if not isinstance(artists, list):
            artists = []
        artist_widgets: list[QWidget] = []
        for row in artists:
            if isinstance(row, dict):
                name = (row.get("nickname") or row.get("name") or "").strip()
                w = ArtistWidget()
                w.set_name(name)
                avatar_url = resolve_backend_media_url(
                    api_base, (row.get("avatar_url") or "").strip()
                )
                if avatar_url:
                    w.set_avatar_url(avatar_url)
                if self._on_open_artist:
                    w.set_on_open_artist(self._on_open_artist)
                artist_widgets.append(w)
        self._artist_carousel.set_items(artist_widgets)

        tracks = body.get("tracks")
        if not isinstance(tracks, list):
            tracks = []
        norm_tracks: list[dict] = []
        for it in tracks:
            if not isinstance(it, dict):
                continue
            row = dict(it)
            au = resolve_backend_media_url(
                api_base, (row.get("artwork_url") or "").strip()
            )
            if au:
                row["artwork_url"] = au
            norm_tracks.append(row)
        self._fill_tracks(norm_tracks)

    def _clear_tracks(self) -> None:
        while self._tracks_layout.count():
            it = self._tracks_layout.takeAt(0)
            w = it.widget()
            if w is not None:
                w.deleteLater()

    def _fill_tracks(self, tracks: list) -> None:
        self._clear_tracks()
        for i, it in enumerate(tracks, start=1):
            if not isinstance(it, dict):
                continue
            row = TrackRow(
                i,
                it,
                self._on_play_track,
                on_open_artist=self._on_open_artist,
                session=self._session,
                dialog_parent=self,
                on_library_changed=lambda: self.library_changed.emit(),
            )
            self._tracks_layout.addWidget(row)
        if not tracks:
            empty = QLabel("Пока нет треков в каталоге.")
            empty.setObjectName("popularEmptyHint")
            self._tracks_layout.addWidget(empty)
