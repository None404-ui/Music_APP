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
from PyQt6.QtCore import QThread, Qt, pyqtSignal
from PyQt6.QtGui import QColor

from backend.session import UserSession
from backend.api_client import CratesApiClient
from ui import i18n
from ui.transient_scrollbars import enable_transient_vertical_page_scroll
from ui.artist_link_label import ArtistLinkLabel
from ui.windows.upload_music_dialog import UploadMusicDialog

OnPlayTrackQueue = Callable[[list[dict], int], None]
OnOpenAlbum = Callable[[list, dict], None]
OnOpenReview = Callable[[dict], None]
OnOpenArtist = Callable[[str], None]


def _response_list(body) -> list:
    if isinstance(body, list):
        return body
    if isinstance(body, dict) and "results" in body:
        return body["results"]
    return []


def _load_favorites_core(
    client: CratesApiClient,
) -> tuple[int, list[dict], list[dict], list[dict]]:
    st_fav, fav_body = client.get_json("/api/favorites/")
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


def _load_favorite_reviews_core(client: CratesApiClient) -> tuple[int, list[dict]]:
    st_fav, body = client.get_json("/api/review-favorites/")
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
        st_review, review_body = client.get_json(f"/api/reviews/{rid}/")
        if st_review == 200 and isinstance(review_body, dict):
            reviews.append(review_body)
    return st_fav, reviews


def _load_user_music_core(
    client: CratesApiClient, user_id: int, kind: str
) -> tuple[int, list[dict]]:
    st, body = client.get_json(
        f"/api/music-items/?artist_user_id={user_id}&kind={kind}"
    )
    items = _response_list(body) if st == 200 else []
    out = [
        dict(item)
        for item in items
        if isinstance(item, dict) and item.get("id") is not None
    ]
    return st, out


def _load_own_collections_core(
    client: CratesApiClient, user_id: int
) -> tuple[int, list[dict]]:
    st_col, col_body = client.get_json("/api/collections/")
    collections = _response_list(col_body) if st_col == 200 else []
    own = [c for c in collections if _owner_id(c) == user_id]
    return st_col, own


def _load_own_reviews_core(
    client: CratesApiClient, user_id: int
) -> tuple[int, list[dict]]:
    st_rev, rev_body = client.get_json(f"/api/reviews/?author_id={user_id}")
    reviews = _response_list(rev_body) if st_rev == 200 else []
    return st_rev, [r for r in reviews if isinstance(r, dict)]


def _gather_selected_reload_dict(client: CratesApiClient, user_id: int) -> dict:
    st_fav, fav_tracks, fav_albums, fav_playlists = _load_favorites_core(client)
    st_review_fav, favorite_reviews = _load_favorite_reviews_core(client)
    st_own_tracks, own_tracks = _load_user_music_core(client, user_id, "track")
    st_own_albums, own_albums = _load_user_music_core(client, user_id, "album")
    st_col, own_collections = _load_own_collections_core(client, user_id)
    st_rev, own_reviews = _load_own_reviews_core(client, user_id)
    return {
        "fav": (st_fav, fav_tracks, fav_albums, fav_playlists),
        "fav_rev": (st_review_fav, favorite_reviews),
        "own_tr": (st_own_tracks, own_tracks),
        "own_al": (st_own_albums, own_albums),
        "col": (st_col, own_collections),
        "rev": (st_rev, own_reviews),
    }


class _SelectedTabReloadThread(QThread):
    """Сбор данных «Моё» в фоне, чтобы не блокировать GUI (аудио, resize)."""

    fetched = pyqtSignal(int, object)

    def __init__(
        self, client: CratesApiClient, user_id: int, token: int, parent=None
    ):
        super().__init__(parent)
        self._client = client
        self._user_id = user_id
        self._token = token

    def run(self) -> None:
        self.fetched.emit(
            self._token,
            _gather_selected_reload_dict(self._client, self._user_id),
        )


def _owner_id(collection: dict):
    o = collection.get("owner")
    if isinstance(o, dict):
        return o.get("id")
    return o


def _review_title(review: dict) -> str:
    mi = review.get("music_item")
    if isinstance(mi, dict):
        return mi.get("title") or i18n.tr("Рецензия")
    if mi is not None:
        return f"{i18n.tr('Трек')} #{mi}"
    collection = review.get("collection")
    if isinstance(collection, dict):
        return collection.get("title") or i18n.tr("Подборка")
    if collection is not None:
        return f"{i18n.tr('Подборка')} #{collection}"
    return i18n.tr("Рецензия")


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


def _fit_wrapped_label(label: QLabel) -> QLabel:
    label.setWordWrap(True)
    label.setMinimumWidth(0)
    label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
    return label


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
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(4)
        tt = _ClickableTitle(title_s)
        tt.setObjectName("selectedRowTitle")
        _fit_wrapped_label(tt)
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
            _fit_wrapped_label(link)
            link.artist_clicked.connect(on_artist)
            row.addWidget(pre)
            row.addWidget(link, 1)
            lay.addLayout(row)
        else:
            disp = ar or "—"
            lab = QLabel(f"{sub} · {disp}")
            lab.setObjectName("selectedRowSub")
            lay.addWidget(_fit_wrapped_label(lab))
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
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(4)
        title_s = str(mi.get("title") or "—")
        tt = _ClickableTitle(title_s)
        tt.setObjectName("selectedRowTitle")
        _fit_wrapped_label(tt)
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
            _fit_wrapped_label(link)
            link.artist_clicked.connect(on_artist)
            row_meta.addWidget(link, 1, Qt.AlignmentFlag.AlignLeft)
        else:
            lab = QLabel(ar if ar else "—")
            lab.setObjectName("selectedRowSub")
            _fit_wrapped_label(lab)
            row_meta.addWidget(lab, 1, Qt.AlignmentFlag.AlignLeft)
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
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
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
        lay.addWidget(_fit_wrapped_label(t))
        lay.addWidget(_fit_wrapped_label(a))
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
        on_play_tracks: Optional[OnPlayTrackQueue] = None,
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
        self._reload_async_token = 0
        self._on_play_tracks = on_play_tracks
        self._on_open_album = on_open_album
        self._on_open_review = on_open_review
        self._on_open_artist = on_open_artist

        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(24, 16, 24, 24)
        self._outer.setSpacing(6)

        title = QLabel(i18n.tr("МОЁ"))
        title.setObjectName("sectionHeading")
        sh = QGraphicsDropShadowEffect(title)
        sh.setBlurRadius(16)
        sh.setOffset(2, 3)
        sh.setColor(QColor(8, 28, 42, 150))
        title.setGraphicsEffect(sh)
        self._outer.addWidget(title)

        toggle_row = QHBoxLayout()
        toggle_row.setSpacing(8)

        self._btn_favorites = QPushButton(i18n.tr("избранное"))
        self._btn_favorites.setObjectName("btnNav")
        self._btn_favorites.setCheckable(True)

        self._btn_uploads = QPushButton(i18n.tr("мои загрузки"))
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
        enable_transient_vertical_page_scroll(self._favorites_scroll)
        enable_transient_vertical_page_scroll(self._uploads_scroll)

        self._btn_favorites.clicked.connect(self._sync_stack_from_buttons)
        self._btn_uploads.clicked.connect(self._sync_stack_from_buttons)
        self.reset_to_favorites()

        self.reload_content_async()

    def reload_content(self) -> None:
        """Перечитать списки с API (синхронно; после диалогов и т.п.)."""
        self._apply_selected_reload_dict(
            _gather_selected_reload_dict(self._client, self._session.user_id)
        )

    def reload_content_async(self) -> None:
        """То же в фоновом потоке — не блокирует воспроизведение и UI."""
        self._reload_async_token += 1
        tok = self._reload_async_token
        th = _SelectedTabReloadThread(
            self._client, self._session.user_id, tok, self
        )
        th.fetched.connect(self._on_selected_reload_async_done)
        th.finished.connect(th.deleteLater)
        th.start()

    def _on_selected_reload_async_done(self, token: int, payload: object) -> None:
        if token != self._reload_async_token:
            return
        if not isinstance(payload, dict):
            return
        self._apply_selected_reload_dict(payload)

    def _apply_selected_reload_dict(self, d: dict) -> None:
        st_fav, fav_tracks, fav_albums, fav_playlists = d["fav"]
        st_review_fav, favorite_reviews = d["fav_rev"]
        st_own_tracks, own_tracks = d["own_tr"]
        st_own_albums, own_albums = d["own_al"]
        st_col, own_collections = d["col"]
        st_rev, own_reviews = d["rev"]

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
        container.setMinimumWidth(0)
        container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        scroll.setWidget(container)

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
        container.setObjectName("selectedContentContainer")
        col = QVBoxLayout(container)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(6)

        if st_fav != 200:
            col.addWidget(self._section_label(i18n.tr("ИЗБРАННОЕ")))
            col.addWidget(self._empty(i18n.tr("Не удалось загрузить избранное с сервера.")))
        else:
            col.addWidget(self._section_label(i18n.tr("ИЗБРАННЫЕ ТРЕКИ")))
            self._add_track_rows(
                col,
                fav_tracks,
                i18n.tr("Пока нет. ♥ для одного трека (поиск / не из очереди альбома)."),
            )

            col.addWidget(self._section_label(i18n.tr("ИЗБРАННЫЕ АЛЬБОМЫ")))
            self._add_album_rows(
                col,
                fav_albums,
                i18n.tr("Пока нет. Во время воспроизведения альбома нажмите ♥."),
                item_kind="album",
            )

            if fav_playlists:
                col.addWidget(self._section_label(i18n.tr("ИЗБРАННЫЕ ПЛЕЙЛИСТЫ")))
                self._add_album_rows(
                    col,
                    fav_playlists,
                    i18n.tr("Пока нет."),
                    item_kind="playlist",
                )

        col.addWidget(self._section_label(i18n.tr("ИЗБРАННЫЕ РЕЦЕНЗИИ")))
        if st_review_fav != 200:
            col.addWidget(self._empty(i18n.tr("Не удалось загрузить избранные рецензии.")))
        elif favorite_reviews:
            self._add_review_rows(col, favorite_reviews)
        else:
            col.addWidget(
                self._empty(i18n.tr("Пока нет. Отмечайте понравившиеся рецензии сердцем."))
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
        container.setObjectName("selectedContentContainer")
        col = QVBoxLayout(container)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(6)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 4)
        actions.setSpacing(8)
        btn_upload_track = QPushButton(i18n.tr("загрузить трек"))
        btn_upload_track.setObjectName("btnPrimary")
        btn_upload_track.clicked.connect(lambda: self._open_upload_dialog("track"))
        btn_upload_album = QPushButton(i18n.tr("загрузить альбом"))
        btn_upload_album.setObjectName("btnPrimary")
        btn_upload_album.clicked.connect(lambda: self._open_upload_dialog("album"))
        btn_upload_track.setMinimumWidth(160)
        btn_upload_album.setMinimumWidth(160)
        actions.addWidget(btn_upload_track)
        actions.addWidget(btn_upload_album)
        actions.addStretch(1)
        col.addLayout(actions)

        col.addWidget(self._section_label(i18n.tr("МОИ ТРЕКИ")))
        if st_own_tracks != 200:
            col.addWidget(self._empty(i18n.tr("Не удалось загрузить ваши треки.")))
        else:
            self._add_track_rows(col, own_tracks, i18n.tr("Вы пока не загружали треки."))

        col.addWidget(self._section_label(i18n.tr("МОИ АЛЬБОМЫ")))
        if st_own_albums != 200:
            col.addWidget(self._empty(i18n.tr("Не удалось загрузить ваши альбомы.")))
        else:
            self._add_album_rows(
                col,
                own_albums,
                i18n.tr("Вы пока не загружали альбомы."),
                item_kind="album",
            )

        col.addWidget(self._section_label(i18n.tr("МОИ РЕЦЕНЗИИ")))
        if st_rev != 200:
            col.addWidget(self._empty(i18n.tr("Не удалось загрузить рецензии.")))
        elif own_reviews:
            self._add_review_rows(col, own_reviews)
        else:
            col.addWidget(self._empty(i18n.tr("Рецензий пока нет. Добавьте из плеера.")))

        col.addWidget(self._section_label(i18n.tr("МОИ ПОДБОРКИ")))
        if st_col != 200:
            col.addWidget(self._empty(i18n.tr("Не удалось загрузить подборки.")))
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
            col.addWidget(self._empty(i18n.tr("Подборок пока нет.")))

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
        for idx, item in enumerate(items):
            row_mi = dict(item)
            play_cb = None
            if self._on_play_tracks:

                def _make_fav_play_cb(ix: int):
                    def _cb(_m: dict) -> None:
                        self._on_play_tracks(items, ix)

                    return _cb

                play_cb = _make_fav_play_cb(idx)
            layout.addWidget(
                _FavTrackRow(
                    row_mi,
                    play_cb,
                    self._on_open_artist,
                    self._session,
                    self.reload_content_async,
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
        sub = i18n.tr("Альбом") if item_kind == "album" else i18n.tr("Плейлист")
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
