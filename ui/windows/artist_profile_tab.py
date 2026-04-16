from __future__ import annotations

from urllib.parse import quote

from PyQt6.QtCore import QByteArray, QEasingCurve, QSize, Qt, QTimer, QUrl, QVariantAnimation, pyqtSignal
from PyQt6.QtGui import QColor, QImage, QMouseEvent, QPainter, QPixmap
from PyQt6.QtNetwork import QNetworkReply, QNetworkRequest
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from backend.api_client import resolve_backend_media_url
from ui import i18n
from backend.session import UserSession
from ui.cover_art import CoverArtWidget
from ui.duration_util import effective_duration_sec, format_duration_mm_ss
from ui.interactive_fx import InteractiveRowFrame
from ui.track_like_review import TrackLikeReviewBar
from ui.windows.popular_tab import AlbumCard, CarouselSection, _album_cover_network

# Высота левой колонки (аватар) = высота правой колонки (имя + «популярное» + список)
_HERO_AVATAR = 260
_HERO_NAME_H = 44
_HERO_POPULAR_H = 22
_HERO_GAP = 8
_TRACK_ROW_H = 52


def _fmt_dur(item: dict) -> str:
    return format_duration_mm_ss(effective_duration_sec(item))


class _PixelExpandArrow(QPushButton):
    """Пиксельная стрелка в стиле иконок приложения: развернуть / свернуть все треки."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("artistExpandTracksArrow")
        self.setFixedSize(52, 24)
        self.setFlat(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(i18n.tr("все треки"))
        self._expanded = False

    def set_expanded(self, expanded: bool) -> None:
        self._expanded = expanded
        self.setToolTip(
            i18n.tr("свернуть") if expanded else i18n.tr("все треки")
        )
        self.update()

    def paintEvent(self, event) -> None:
        del event
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        w, h = self.width(), self.height()
        cx = w // 2
        cy = h // 2
        u = 3  # «пиксель» шага
        ink = QColor("#312938")
        acc = QColor("#A14016")
        # Ромб / шеврон из квадратов 3×3
        def rect(gx: int, gy: int, c: QColor) -> None:
            p.fillRect(gx, gy, u, u, c)

        if not self._expanded:
            # вниз ▼
            y0 = cy - u
            rect(cx - u, y0 - u, ink)
            rect(cx, y0 - u, acc)
            rect(cx + u, y0 - u, ink)
            rect(cx - 2 * u, y0, ink)
            rect(cx - u, y0, acc)
            rect(cx, y0, acc)
            rect(cx + u, y0, acc)
            rect(cx + 2 * u, y0, ink)
            rect(cx - u, y0 + u, ink)
            rect(cx, y0 + u, acc)
            rect(cx + u, y0 + u, ink)
            rect(cx, y0 + 2 * u, acc)
        else:
            # вверх ▲
            y0 = cy + u
            rect(cx, y0 - 2 * u, acc)
            rect(cx - u, y0 - u, ink)
            rect(cx, y0 - u, acc)
            rect(cx + u, y0 - u, ink)
            rect(cx - 2 * u, y0, ink)
            rect(cx - u, y0, acc)
            rect(cx, y0, acc)
            rect(cx + u, y0, acc)
            rect(cx + 2 * u, y0, ink)
            rect(cx - u, y0 + u, ink)
            rect(cx, y0 + u, acc)
            rect(cx + u, y0 + u, ink)
        p.end()


class _ArtistHeroTrackRow(InteractiveRowFrame):
    """Обложка · название · длительность · ♥ · рецензия (как в плеере)."""

    _THUMB = 40

    def __init__(
        self,
        item: dict,
        session: UserSession,
        on_play,
        on_favorite_changed,
        dialog_parent: QWidget,
        parent=None,
    ):
        super().__init__(radius=6, hover_alpha=28, press_alpha=48, active_alpha=16, parent=parent)
        self.setObjectName("trackRow")
        self.setFixedHeight(_TRACK_ROW_H)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._item = item
        self._on_play = on_play
        self._thumb_reply: QNetworkReply | None = None

        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 4, 10, 4)
        lay.setSpacing(10)

        self._thumb = CoverArtWidget(
            radius=6,
            border_width=1,
            border_color=QColor("#89A194"),
            fill_color=QColor(49, 41, 56, 90),
            mask_color=QColor("#5c5748"),
            placeholder_text="♪",
            placeholder_color=QColor("#A14016"),
            placeholder_px=16,
        )
        self._thumb.setObjectName("trackRowThumb")
        self._thumb.setFixedSize(self._THUMB, self._THUMB)
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

        self._title = QLabel((item.get("title") or i18n.tr("Без названия")).strip())
        self._title.setObjectName("trackTitle")
        self._title.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        self._title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        self._dur = QLabel(_fmt_dur(item))
        self._dur.setObjectName("trackDuration")
        self._dur.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._dur.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        self._actions_bar = TrackLikeReviewBar(
            item,
            session,
            dialog_parent,
            on_changed=on_favorite_changed,
        )

        lay.addWidget(self._thumb, 0, Qt.AlignmentFlag.AlignVCenter)
        lay.addWidget(self._title, 1, Qt.AlignmentFlag.AlignVCenter)
        lay.addWidget(self._dur, 0, Qt.AlignmentFlag.AlignVCenter)
        lay.addWidget(self._actions_bar, 0, Qt.AlignmentFlag.AlignVCenter)
        self.install_interaction_filters()

    def _apply_thumb_placeholder(self) -> None:
        self._thumb.clear_cover()

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
        finally:
            reply.deleteLater()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            if self._actions_bar.geometry().contains(event.position().toPoint()):
                super().mouseReleaseEvent(event)
                return
            if self._on_play:
                self._on_play(self._item)
        super().mouseReleaseEvent(event)

    def enterEvent(self, event) -> None:
        self._apply_thumb_style(True)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._apply_thumb_style(False)
        super().leaveEvent(event)


class ArtistProfileTab(QWidget):
    """Профиль исполнителя: аватар слева, список треков справа по высоте аватара, стрелка, альбомы."""

    library_changed = pyqtSignal()

    def __init__(
        self,
        session: UserSession,
        *,
        on_back,
        on_play_track=None,
        on_open_album=None,
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("popularPage")
        self._session = session
        self._on_back = on_back
        self._on_play_track = on_play_track
        self._on_open_album = on_open_album
        self._artist_name = ""
        self._norm_tracks: list[dict] = []
        self._tracks_expanded = False
        self._avatar_reply: QNetworkReply | None = None

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

        nav_row = QHBoxLayout()
        self._btn_back = QPushButton(i18n.tr("← назад"))
        self._btn_back.setObjectName("btnNav")
        self._btn_back.setCheckable(False)
        self._btn_back.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_back.clicked.connect(self._on_back)
        nav_row.addWidget(self._btn_back, 0, Qt.AlignmentFlag.AlignLeft)
        nav_row.addStretch(1)
        root.addLayout(nav_row)

        # —— Герой: аватар слева | справа имя + популярное + треки (высота списка = высота аватара) ——
        self._hero = QFrame()
        self._hero.setObjectName("artistHeroBlock")
        hero_lay = QHBoxLayout(self._hero)
        hero_lay.setContentsMargins(0, 0, 0, 0)
        hero_lay.setSpacing(16)

        self._avatar = CoverArtWidget(
            radius=8,
            border_width=2,
            border_color=QColor("#89A194"),
            fill_color=QColor("#BDB685"),
            mask_color=QColor(18, 12, 28),
            placeholder_text="♫",
            placeholder_color=QColor("#A14016"),
            placeholder_px=56,
        )
        self._avatar.setObjectName("artistHeroCover")
        self._avatar.setFixedSize(_HERO_AVATAR, _HERO_AVATAR)
        hero_lay.addWidget(self._avatar, 0, Qt.AlignmentFlag.AlignTop)

        right = QWidget()
        right_col = QVBoxLayout(right)
        right_col.setContentsMargins(0, 0, 0, 0)
        right_col.setSpacing(6)

        self._heading = QLabel("")
        self._heading.setObjectName("sectionHeading")
        self._heading.setWordWrap(True)
        self._heading.setFixedHeight(_HERO_NAME_H)
        right_col.addWidget(self._heading)

        self._popular_lbl = QLabel(i18n.tr("популярное"))
        self._popular_lbl.setObjectName("popularLoadStatus")
        self._popular_lbl.setFixedHeight(_HERO_POPULAR_H)
        right_col.addWidget(self._popular_lbl)

        self._scroll_tracks = QScrollArea()
        self._scroll_tracks.setObjectName("artistHeroTrackScroll")
        self._scroll_tracks.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll_tracks.setWidgetResizable(True)
        self._scroll_tracks.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._scroll_tracks.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._tracks_inner = QWidget()
        self._tracks_inner.setStyleSheet("background: transparent;")
        self._tracks_layout = QVBoxLayout(self._tracks_inner)
        self._tracks_layout.setContentsMargins(0, 0, 0, 0)
        self._tracks_layout.setSpacing(6)
        self._scroll_tracks.setWidget(self._tracks_inner)

        self._list_height = (
            _HERO_AVATAR - _HERO_NAME_H - _HERO_POPULAR_H - _HERO_GAP
        )
        self._track_row_stride = _TRACK_ROW_H + 6
        self._max_visible_preview = max(
            2, self._list_height // self._track_row_stride
        )
        self._scroll_tracks.setFixedHeight(max(self._list_height, _TRACK_ROW_H * 2))
        self._tracks_height_anim = QVariantAnimation(self)
        self._tracks_height_anim.setDuration(180)
        self._tracks_height_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._tracks_height_anim.valueChanged.connect(self._apply_tracks_height)
        right_col.addWidget(self._scroll_tracks)

        self._arrow = _PixelExpandArrow()
        self._arrow.clicked.connect(self._toggle_tracks_expand)
        self._arrow.hide()
        ar_row = QHBoxLayout()
        ar_row.addStretch(1)
        ar_row.addWidget(self._arrow)
        ar_row.addStretch(1)
        right_col.addLayout(ar_row)

        right.setMinimumHeight(_HERO_AVATAR)
        hero_lay.addWidget(right, 1)

        root.addWidget(self._hero)

        self._meta = QLabel("")
        self._meta.setObjectName("popularLoadStatus")
        self._meta.setWordWrap(True)
        root.addWidget(self._meta)

        self._status = QLabel("")
        self._status.setObjectName("popularLoadStatus")
        self._status.setWordWrap(True)
        self._status.hide()
        root.addWidget(self._status)

        self._album_carousel = CarouselSection(i18n.tr("АЛЬБОМЫ"))
        self._playlist_carousel = CarouselSection(i18n.tr("ПЛЕЙЛИСТЫ"))
        root.addWidget(self._album_carousel)
        root.addSpacing(8)
        root.addWidget(self._playlist_carousel)

        root.addStretch()

        page_scroll.setWidget(inner)
        outer.addWidget(page_scroll)

    def _toggle_tracks_expand(self) -> None:
        if len(self._norm_tracks) <= self._max_visible_preview:
            return
        self._tracks_expanded = not self._tracks_expanded
        self._arrow.set_expanded(self._tracks_expanded)
        start_h = self._scroll_tracks.height()
        if self._tracks_expanded:
            self._scroll_tracks.setVerticalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAsNeeded
            )
            end_h = min(
                520,
                max(
                    self._list_height,
                    len(self._norm_tracks) * self._track_row_stride,
                ),
            )
        else:
            self._scroll_tracks.setVerticalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            )
            end_h = self._list_height
        self._rebuild_track_rows()
        self._tracks_height_anim.stop()
        self._tracks_height_anim.setStartValue(start_h)
        self._tracks_height_anim.setEndValue(end_h)
        self._tracks_height_anim.start()

    def _apply_tracks_height(self, value) -> None:
        h = int(value)
        self._scroll_tracks.setMinimumHeight(h)
        self._scroll_tracks.setMaximumHeight(h)
        self._scroll_tracks.setFixedHeight(h)

    def _rebuild_track_rows(self) -> None:
        while self._tracks_layout.count():
            it = self._tracks_layout.takeAt(0)
            w = it.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        if not self._norm_tracks:
            empty = QLabel(i18n.tr("Нет треков в каталоге."))
            empty.setObjectName("popularEmptyHint")
            self._tracks_layout.addWidget(empty)
            return
        if self._tracks_expanded:
            slice_ = self._norm_tracks
        else:
            slice_ = self._norm_tracks[: self._max_visible_preview]
        for it in slice_:
            row = _ArtistHeroTrackRow(
                it,
                self._session,
                self._on_play_track,
                self._on_favorite_changed,
                self,
            )
            self._tracks_layout.addWidget(row)
        self._tracks_layout.addStretch()

    def _on_favorite_changed(self) -> None:
        self.library_changed.emit()

    def _abort_avatar(self) -> None:
        if self._avatar_reply is None:
            return
        r = self._avatar_reply
        self._avatar_reply = None
        r.abort()

    def _apply_avatar_url(self, url: str) -> None:
        self._abort_avatar()
        if not url.startswith(("http://", "https://")):
            return
        self._avatar_reply = _album_cover_network().get(QNetworkRequest(QUrl(url)))
        self._avatar_reply.finished.connect(self._on_avatar_finished)

    def _on_avatar_finished(self) -> None:
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
            if not img.loadFromData(QByteArray(data)):
                return
            self._avatar.set_cover_pixmap(QPixmap.fromImage(img))
        finally:
            reply.deleteLater()

    def load_artist(self, name: str) -> None:
        self._artist_name = (name or "").strip()
        if not self._artist_name:
            return
        self._heading.setText(self._artist_name.upper())
        self._meta.setText("")
        self._status.setText(i18n.tr("загрузка…"))
        self._status.show()
        self._norm_tracks = []
        self._tracks_expanded = False
        self._arrow.set_expanded(False)
        self._arrow.hide()
        self._scroll_tracks.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._scroll_tracks.setFixedHeight(self._list_height)
        self._album_carousel.set_items([])
        self._playlist_carousel.set_items([])
        self._album_carousel.show()
        self._playlist_carousel.show()
        self._rebuild_track_rows()
        self._abort_avatar()
        self._avatar.clear_cover()
        QTimer.singleShot(0, self._fetch)

    def _fetch(self) -> None:
        name = self._artist_name
        if not name:
            return
        path = f"/api/music-items/artist-profile/?name={quote(name)}"
        try:
            st, body = self._session.client.get_json(path)
        except OSError as e:
            self._status.setText(f"{i18n.tr('Нет связи с сервером:')} {e}")
            self._status.show()
            return
        except Exception as e:
            self._status.setText(f"{i18n.tr('Ошибка:')} {e}")
            self._status.show()
            return

        if st != 200 or not isinstance(body, dict):
            detail = ""
            if isinstance(body, dict):
                detail = str(body.get("detail", body))
            self._status.setText(f"{i18n.tr('Сервер ответил')} {st}. {detail}".strip())
            self._status.show()
            return

        self._status.hide()
        display = (body.get("name") or name).strip() or name
        self._heading.setText(display.upper())
        tc = int(body.get("track_count") or 0)
        self._meta.setText(f"{i18n.tr('треков в каталоге:')} {tc}")

        api_base = self._session.client.base_url if self._session else ""

        tracks = body.get("tracks")
        if not isinstance(tracks, list):
            tracks = []
        self._norm_tracks = []
        for it in tracks:
            if not isinstance(it, dict):
                continue
            row = dict(it)
            au = resolve_backend_media_url(
                api_base, (row.get("artwork_url") or "").strip()
            )
            if au:
                row["artwork_url"] = au
            self._norm_tracks.append(row)

        # Аватар только из профиля пользователя с таким ником, не из обложек треков/альбомов.
        self._abort_avatar()
        up = body.get("user_profile")
        avatar_url = ""
        if isinstance(up, dict):
            avatar_url = (up.get("avatar_url") or "").strip()
        resolved = (
            resolve_backend_media_url(api_base, avatar_url) if avatar_url else ""
        )
        if resolved.startswith(("http://", "https://")):
            self._apply_avatar_url(resolved)
        else:
            self._avatar.clear_cover()

        self._arrow.setVisible(len(self._norm_tracks) > self._max_visible_preview)
        self._tracks_expanded = False
        self._arrow.set_expanded(False)
        self._scroll_tracks.setFixedHeight(self._list_height)
        self._scroll_tracks.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._rebuild_track_rows()

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
            c.set_on_open_artist(self._on_open_artist_profile)
            album_widgets.append(c)
        self._album_carousel.set_items(album_widgets)
        self._album_carousel.setVisible(bool(album_widgets))

        playlists = body.get("playlists")
        if not isinstance(playlists, list):
            playlists = []
        pl_widgets: list[QWidget] = []
        for it in playlists:
            if not isinstance(it, dict):
                continue
            if (it.get("kind") or "").strip().lower() != "playlist":
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
            c.set_on_open_artist(self._on_open_artist_profile)
            pl_widgets.append(c)
        self._playlist_carousel.set_items(pl_widgets)
        self._playlist_carousel.setVisible(bool(pl_widgets))

    def _on_open_artist_profile(self, artist: str) -> None:
        a = (artist or "").strip()
        if a:
            self.load_artist(a)

    def _on_album_card_clicked(self, item: dict) -> None:
        if not self._on_open_album:
            return
        tracks = self._fetch_playback_queue(item)
        if tracks:
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
