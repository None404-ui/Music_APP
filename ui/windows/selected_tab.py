from __future__ import annotations

from typing import Callable, Optional

from ui.interactive_fx import InteractiveRowFrame, animate_stack_fade
from ui.track_like_review import TrackLikeReviewBar

from PyQt6.QtWidgets import (
    QButtonGroup,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QFrame,
    QSizePolicy,
    QGraphicsDropShadowEffect,
    QPushButton,
    QStackedWidget,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor

from backend.session import UserSession
from ui.artist_link_label import ArtistLinkLabel
from ui.windows.upload_music_dialog import UploadMusicDialog

OnPlayTrack = Callable[[dict], None]
OnOpenAlbum = Callable[[list, dict], None]
OnOpenReview = Callable[[dict], None]
OnOpenArtist = Callable[[str], None]


def _response_list(body) -> list:
    if isinstance(body, list):
        return body
    if isinstance(body, dict) and "results" in body:
        return body["results"]
    return []


def _owner_id(collection: dict):
    o = collection.get("owner")
    if isinstance(o, dict):
        return o.get("id")
    return o


def _review_title(review: dict) -> str:
    mi = review.get("music_item")
    if isinstance(mi, dict):
        return mi.get("title") or "Рецензия"
    if mi is not None:
        return f"Трек #{mi}"
    collection = review.get("collection")
    if isinstance(collection, dict):
        return collection.get("title") or "Подборка"
    if collection is not None:
        return f"Подборка #{collection}"
    return "Рецензия"


def _review_excerpt(review: dict, limit: int = 120) -> str:
    full = str(review.get("text") or "")
    text = full[:limit]
    if len(full) > limit:
        text += "…"
    return text or "—"


class _ClickableTitle(QLabel):
    clicked = pyqtSignal()

    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class _FavAlbumRow(InteractiveRowFrame):
    """Строка избранного альбома: клик по названию — очередь; по исполнителю — профиль."""

    def __init__(
        self,
        title_s: str,
        sub: str,
        artist_raw: str,
        on_album,
        on_artist: Optional[OnOpenArtist],
        parent=None,
    ):
        super().__init__(radius=8, hover_alpha=24, press_alpha=42, active_alpha=18, parent=parent)
        self.setObjectName("selectedRow")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(4)
        tt = _ClickableTitle(title_s)
        tt.setObjectName("selectedRowTitle")
        if on_album:
            tt.clicked.connect(on_album)
        lay.addWidget(tt)
        ar = (artist_raw or "").strip()
        if ar and on_artist:
            row = QHBoxLayout()
            row.setSpacing(0)
            pre = QLabel(f"{sub} · ")
            pre.setObjectName("selectedRowSub")
            link = ArtistLinkLabel()
            link.setObjectName("selectedRowArtist")
            link.set_artist(ar)
            link.artist_clicked.connect(on_artist)
            row.addWidget(pre)
            row.addWidget(link)
            row.addStretch()
            lay.addLayout(row)
        else:
            disp = ar or "—"
            lab = QLabel(f"{sub} · {disp}")
            lab.setObjectName("selectedRowSub")
            lab.setWordWrap(True)
            lay.addWidget(lab)
        self.install_interaction_filters()


class _FavTrackRow(InteractiveRowFrame):
    """Избранный трек: название — в плеер; исполнитель — профиль; ♥ и рецензия как в плеере."""

    def __init__(
        self,
        mi: dict,
        on_play,
        on_artist: Optional[OnOpenArtist],
        session: UserSession,
        on_library_changed: Callable[[], None],
        parent=None,
    ):
        super().__init__(radius=8, hover_alpha=24, press_alpha=42, active_alpha=18, parent=parent)
        self.setObjectName("selectedRow")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(4)
        title_s = str(mi.get("title") or "—")
        tt = _ClickableTitle(title_s)
        tt.setObjectName("selectedRowTitle")
        if on_play:
            tt.clicked.connect(lambda: on_play(mi))
        lay.addWidget(tt)

        row_meta = QHBoxLayout()
        row_meta.setContentsMargins(0, 0, 0, 0)
        row_meta.setSpacing(8)
        ar = (mi.get("artist") or "").strip()
        if ar and on_artist:
            link = ArtistLinkLabel()
            link.setObjectName("selectedRowArtist")
            link.set_artist(ar)
            link.artist_clicked.connect(on_artist)
            row_meta.addWidget(link, 0, Qt.AlignmentFlag.AlignLeft)
        else:
            lab = QLabel(ar if ar else "—")
            lab.setObjectName("selectedRowSub")
            row_meta.addWidget(lab, 0, Qt.AlignmentFlag.AlignLeft)
        row_meta.addStretch(1)
        self._actions = TrackLikeReviewBar(
            mi,
            session,
            self.window() or self,
            on_changed=on_library_changed,
        )
        row_meta.addWidget(self._actions, 0, Qt.AlignmentFlag.AlignRight)
        lay.addLayout(row_meta)
        self.install_interaction_filters()


class _ClickableRow(InteractiveRowFrame):
    def __init__(
        self,
        title: str,
        subtitle: str,
        on_click: Optional[Callable[[], None]] = None,
        parent=None,
    ):
        super().__init__(radius=8, hover_alpha=24, press_alpha=42, active_alpha=18, parent=parent)
        self.setObjectName("selectedRow")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._on_click = on_click
        if on_click:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(2)
        t = QLabel(title)
        t.setObjectName("selectedRowTitle")
        a = QLabel(subtitle)
        a.setObjectName("selectedRowSub")
        a.setWordWrap(True)
        lay.addWidget(t)
        lay.addWidget(a)
        self.install_interaction_filters()

    def mousePressEvent(self, event):
        if (
            self._on_click
            and event.button() == Qt.MouseButton.LeftButton
        ):
            self._on_click()
        super().mousePressEvent(event)


class SelectedTab(QWidget):
    """Две внутренние страницы: избранное и загруженный пользователем контент."""

    _SUB_FAVORITES = 0
    _SUB_UPLOADS = 1

    def __init__(
        self,
        session: UserSession,
        *,
        on_play_track: Optional[OnPlayTrack] = None,
        on_open_album: Optional[OnOpenAlbum] = None,
        on_open_review: Optional[OnOpenReview] = None,
        on_open_artist: Optional[OnOpenArtist] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("selectedPage")
        self.setAutoFillBackground(True)
        self._session = session
        self._client = session.client
        self._on_play_track = on_play_track
        self._on_open_album = on_open_album
        self._on_open_review = on_open_review
        self._on_open_artist = on_open_artist

        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(24, 16, 24, 24)
        self._outer.setSpacing(6)

        title = QLabel("МОЁ")
        title.setObjectName("sectionHeading")
        sh = QGraphicsDropShadowEffect(title)
        sh.setBlurRadius(16)
        sh.setOffset(2, 3)
        sh.setColor(QColor(8, 28, 42, 150))
        title.setGraphicsEffect(sh)
        self._outer.addWidget(title)

        toggle_row = QHBoxLayout()
        toggle_row.setSpacing(8)

        self._btn_favorites = QPushButton("избранное")
        self._btn_favorites.setObjectName("btnNav")
        self._btn_favorites.setCheckable(True)

        self._btn_uploads = QPushButton("мои загрузки")
        self._btn_uploads.setObjectName("btnNav")
        self._btn_uploads.setCheckable(True)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._group.addButton(self._btn_favorites, self._SUB_FAVORITES)
        self._group.addButton(self._btn_uploads, self._SUB_UPLOADS)

        toggle_row.addWidget(self._btn_favorites)
        toggle_row.addWidget(self._btn_uploads)
        toggle_row.addStretch()
        self._outer.addLayout(toggle_row)

        self._stack = QStackedWidget()
        self._favorites_scroll = self._create_scroll()
        self._uploads_scroll = self._create_scroll()
        self._stack.addWidget(self._favorites_scroll)
        self._stack.addWidget(self._uploads_scroll)
        self._outer.addWidget(self._stack, stretch=1)

        self._btn_favorites.clicked.connect(self._sync_stack_from_buttons)
        self._btn_uploads.clicked.connect(self._sync_stack_from_buttons)
        self.reset_to_favorites()

        self.reload_content()

    def reload_content(self) -> None:
        """Перечитать списки с API для обеих внутренних страниц."""
        (
            st_fav,
            fav_tracks,
            fav_albums,
            fav_playlists,
        ) = self._load_favorites()
        st_review_fav, favorite_reviews = self._load_favorite_reviews()
        st_own_tracks, own_tracks = self._load_user_music("track")
        st_own_albums, own_albums = self._load_user_music("album")
        st_col, own_collections = self._load_own_collections()
        st_rev, own_reviews = self._load_own_reviews()

        self._set_scroll_content(
            self._favorites_scroll,
            self._build_favorites_page(
                st_fav,
                fav_tracks,
                fav_albums,
                fav_playlists,
                st_review_fav,
                favorite_reviews,
            ),
        )
        self._set_scroll_content(
            self._uploads_scroll,
            self._build_uploads_page(
                st_own_tracks,
                own_tracks,
                st_own_albums,
                own_albums,
                st_rev,
                own_reviews,
                st_col,
                own_collections,
            ),
        )

    def reset_to_favorites(self) -> None:
        self._group.blockSignals(True)
        try:
            self._btn_favorites.setChecked(True)
            self._btn_uploads.setChecked(False)
        finally:
            self._group.blockSignals(False)
        self._stack.setCurrentIndex(self._SUB_FAVORITES)

    def _sync_stack_from_buttons(self) -> None:
        if self._btn_favorites.isChecked():
            animate_stack_fade(self._stack, self._SUB_FAVORITES)
        elif self._btn_uploads.isChecked():
            animate_stack_fade(self._stack, self._SUB_UPLOADS)

    def _create_scroll(self) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setObjectName("selectedScroll")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        return scroll

    def _set_scroll_content(self, scroll: QScrollArea, container: QWidget) -> None:
        scroll.takeWidget()
        scroll.setWidget(container)

    def _load_favorites(self) -> tuple[int, list[dict], list[dict], list[dict]]:
        st_fav, fav_body = self._client.get_json("/api/favorites/")
        favs = _response_list(fav_body) if st_fav == 200 else []
        fav_tracks: list[dict] = []
        fav_albums: list[dict] = []
        fav_playlists: list[dict] = []
        for row in favs:
            mi = row.get("music_item")
            if not isinstance(mi, dict) or mi.get("id") is None:
                continue
            kind = (mi.get("kind") or "").strip().lower()
            if kind == "album":
                fav_albums.append(mi)
            elif kind == "playlist":
                fav_playlists.append(mi)
            else:
                row_mi = dict(mi)
                row_mi["user_favorited"] = True
                fav_tracks.append(row_mi)
        return st_fav, fav_tracks, fav_albums, fav_playlists

    def _load_favorite_reviews(self) -> tuple[int, list[dict]]:
        st_fav, body = self._client.get_json("/api/review-favorites/")
        if st_fav != 200:
            return st_fav, []
        rows = _response_list(body)
        reviews: list[dict] = []
        for row in rows:
            review_id = row.get("review")
            try:
                rid = int(review_id)
            except (TypeError, ValueError):
                continue
            st_review, review_body = self._client.get_json(f"/api/reviews/{rid}/")
            if st_review == 200 and isinstance(review_body, dict):
                reviews.append(review_body)
        return st_fav, reviews

    def _load_user_music(self, kind: str) -> tuple[int, list[dict]]:
        st, body = self._client.get_json(
            f"/api/music-items/?artist_user_id={self._session.user_id}&kind={kind}"
        )
        items = _response_list(body) if st == 200 else []
        out = [
            dict(item)
            for item in items
            if isinstance(item, dict) and item.get("id") is not None
        ]
        return st, out

    def _load_own_collections(self) -> tuple[int, list[dict]]:
        st_col, col_body = self._client.get_json("/api/collections/")
        collections = _response_list(col_body) if st_col == 200 else []
        uid = self._session.user_id
        own = [c for c in collections if _owner_id(c) == uid]
        return st_col, own

    def _load_own_reviews(self) -> tuple[int, list[dict]]:
        st_rev, rev_body = self._client.get_json(
            f"/api/reviews/?author_id={self._session.user_id}"
        )
        reviews = _response_list(rev_body) if st_rev == 200 else []
        return st_rev, [r for r in reviews if isinstance(r, dict)]

    def _build_favorites_page(
        self,
        st_fav: int,
        fav_tracks: list[dict],
        fav_albums: list[dict],
        fav_playlists: list[dict],
        st_review_fav: int,
        favorite_reviews: list[dict],
    ) -> QWidget:
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        col = QVBoxLayout(container)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(6)

        if st_fav != 200:
            col.addWidget(self._section_label("ИЗБРАННОЕ"))
            col.addWidget(self._empty("Не удалось загрузить избранное с сервера."))
        else:
            col.addWidget(self._section_label("ИЗБРАННЫЕ ТРЕКИ"))
            self._add_track_rows(
                col,
                fav_tracks,
                "Пока нет. ♥ для одного трека (поиск / не из очереди альбома).",
            )

            col.addWidget(self._section_label("ИЗБРАННЫЕ АЛЬБОМЫ"))
            self._add_album_rows(
                col,
                fav_albums,
                "Пока нет. Во время воспроизведения альбома нажмите ♥.",
                item_kind="album",
            )

            if fav_playlists:
                col.addWidget(self._section_label("ИЗБРАННЫЕ ПЛЕЙЛИСТЫ"))
                self._add_album_rows(
                    col,
                    fav_playlists,
                    "Пока нет.",
                    item_kind="playlist",
                )

        col.addWidget(self._section_label("ИЗБРАННЫЕ РЕЦЕНЗИИ"))
        if st_review_fav != 200:
            col.addWidget(self._empty("Не удалось загрузить избранные рецензии."))
        elif favorite_reviews:
            self._add_review_rows(col, favorite_reviews)
        else:
            col.addWidget(
                self._empty("Пока нет. Отмечайте понравившиеся рецензии сердцем.")
            )

        col.addStretch()
        return container

    def _build_uploads_page(
        self,
        st_own_tracks: int,
        own_tracks: list[dict],
        st_own_albums: int,
        own_albums: list[dict],
        st_rev: int,
        own_reviews: list[dict],
        st_col: int,
        own_collections: list[dict],
    ) -> QWidget:
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        col = QVBoxLayout(container)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(6)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 4)
        actions.setSpacing(8)
        btn_upload_track = QPushButton("загрузить трек")
        btn_upload_track.setObjectName("btnPrimary")
        btn_upload_track.clicked.connect(lambda: self._open_upload_dialog("track"))
        btn_upload_album = QPushButton("загрузить альбом")
        btn_upload_album.setObjectName("btnPrimary")
        btn_upload_album.clicked.connect(lambda: self._open_upload_dialog("album"))
        btn_upload_track.setMinimumWidth(160)
        btn_upload_album.setMinimumWidth(160)
        actions.addWidget(btn_upload_track)
        actions.addWidget(btn_upload_album)
        actions.addStretch(1)
        col.addLayout(actions)

        col.addWidget(self._section_label("МОИ ТРЕКИ"))
        if st_own_tracks != 200:
            col.addWidget(self._empty("Не удалось загрузить ваши треки."))
        else:
            self._add_track_rows(col, own_tracks, "Вы пока не загружали треки.")

        col.addWidget(self._section_label("МОИ АЛЬБОМЫ"))
        if st_own_albums != 200:
            col.addWidget(self._empty("Не удалось загрузить ваши альбомы."))
        else:
            self._add_album_rows(
                col,
                own_albums,
                "Вы пока не загружали альбомы.",
                item_kind="album",
            )

        col.addWidget(self._section_label("МОИ РЕЦЕНЗИИ"))
        if st_rev != 200:
            col.addWidget(self._empty("Не удалось загрузить рецензии."))
        elif own_reviews:
            self._add_review_rows(col, own_reviews)
        else:
            col.addWidget(self._empty("Рецензий пока нет. Добавьте из плеера."))

        col.addWidget(self._section_label("МОИ ПОДБОРКИ"))
        if st_col != 200:
            col.addWidget(self._empty("Не удалось загрузить подборки."))
        elif own_collections:
            for collection in own_collections:
                col.addWidget(
                    _ClickableRow(
                        collection.get("title") or "—",
                        (collection.get("description") or "").strip(),
                        None,
                    )
                )
        else:
            col.addWidget(self._empty("Подборок пока нет."))

        col.addStretch()
        return container

    def _open_upload_dialog(self, kind: str) -> None:
        dlg = UploadMusicDialog(self._session, kind, self)
        if dlg.exec():
            self._btn_uploads.setChecked(True)
            self._sync_stack_from_buttons()
            self.reload_content()

    def _add_track_rows(
        self,
        layout: QVBoxLayout,
        items: list[dict],
        empty_text: str,
    ) -> None:
        if not items:
            layout.addWidget(self._empty(empty_text))
            return
        for item in items:
            row_mi = dict(item)
            play_cb = None
            if self._on_play_track:
                play_cb = lambda m=row_mi: self._on_play_track(m)
            layout.addWidget(
                _FavTrackRow(
                    row_mi,
                    play_cb,
                    self._on_open_artist,
                    self._session,
                    self.reload_content,
                )
            )

    def _add_album_rows(
        self,
        layout: QVBoxLayout,
        items: list[dict],
        empty_text: str,
        *,
        item_kind: str,
    ) -> None:
        if not items:
            layout.addWidget(self._empty(empty_text))
            return
        sub = "Альбом" if item_kind == "album" else "Плейлист"
        for item in items:
            open_cb = None
            if self._on_open_album:
                open_cb = lambda m=item: self._open_favorite_album(m)
            layout.addWidget(
                _FavAlbumRow(
                    str(item.get("title") or "—"),
                    sub,
                    (item.get("artist") or "").strip(),
                    open_cb,
                    self._on_open_artist,
                )
            )

    def _add_review_rows(self, layout: QVBoxLayout, reviews: list[dict]) -> None:
        for review in reviews:
            rev_cb = None
            if self._on_open_review:
                rev_cb = lambda rev=review: self._on_open_review(rev)
            layout.addWidget(
                _ClickableRow(
                    _review_title(review),
                    _review_excerpt(review),
                    rev_cb,
                )
            )

    def _open_favorite_album(self, mi: dict) -> None:
        if not self._on_open_album:
            return
        mid = mi.get("id")
        if mid is None:
            return
        st, body = self._client.get_json(
            f"/api/music-items/playback-queue/?music_item_id={int(mid)}"
        )
        if st != 200 or not isinstance(body, dict):
            return
        raw = body.get("tracks")
        if not isinstance(raw, list):
            return
        tracks = [x for x in raw if isinstance(x, dict)]
        if tracks:
            self._on_open_album(tracks, mi)

    @staticmethod
    def _section_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("selectedSectionLabel")
        return lbl

    @staticmethod
    def _empty(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("selectedEmpty")
        lbl.setWordWrap(True)
        return lbl
