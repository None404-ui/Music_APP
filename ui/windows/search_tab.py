import json
import os
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

from PyQt6.QtCore import Qt, QSize, QSettings, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QIcon, QMouseEvent
from backend.api_client import resolve_backend_media_url
from backend.session import UserSession
from ui.artist_link_label import ArtistLinkLabel
from ui.interactive_fx import InteractiveRowFrame
from ui.track_like_review import TrackLikeReviewBar
from ui import i18n

from PyQt6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStyle,
    QVBoxLayout,
    QWidget,
)

_FILTER_DEFS = (
    ("all", "все"),
    ("albums", "альбомы"),
    ("tracks", "треки"),
    ("reviews", "рецензии"),
    ("users", "пользователи"),
)

_ICON_SEARCH = os.path.join(os.path.dirname(__file__), "..", "icons", "search.svg")

_ORG = "CRATES"
_APP = "CRATES"
_RECENT_KEY = "search/recent_tracks_json"
_RECENT_MAX = 5
_SEARCH_DEBOUNCE_MS = 1000
_LIST_ROW_MIN = 48
_LIST_SPACING = 6
# Высота строки списка в пикселях (должна быть ≥ реальной отрисовки из search.qss).
_HISTORY_ROW_PX = 104
_RESULTS_ROW_PX = 104


def _list_font() -> QFont:
    f = QFont("Courier New", 13)
    if not f.exactMatch():
        f = QFont("Consolas", 13)
    return f


def _settings() -> QSettings:
    return QSettings(QSettings.Scope.UserScope, _ORG, _APP)


def _row_height(row: QWidget, fallback: int) -> int:
    hint = row.sizeHint().height() if row is not None else 0
    return max(fallback, hint + 8)


def _response_list(body) -> list:
    if isinstance(body, list):
        return body
    if isinstance(body, dict):
        rows = body.get("results")
        return rows if isinstance(rows, list) else []
    return []


def _review_title(review: dict) -> str:
    music_item = review.get("music_item")
    if isinstance(music_item, dict):
        return (music_item.get("title") or i18n.tr("Без названия")).strip()
    collection = review.get("collection")
    if isinstance(collection, dict):
        return (collection.get("title") or i18n.tr("Подборка")).strip()
    return i18n.tr("Рецензия")


def _review_artist(review: dict) -> str:
    music_item = review.get("music_item")
    if isinstance(music_item, dict):
        return (music_item.get("artist") or "").strip()
    return ""


def _review_excerpt(review: dict, limit: int = 140) -> str:
    text = str(review.get("text") or "").strip().replace("\n", " ")
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


class _SearchTrackRow(InteractiveRowFrame):
    """Строка трека: клик по фону — в плеер; по имени исполнителя — профиль; ♥ и рецензия как в плеере."""

    def __init__(
        self,
        item: dict,
        on_play,
        on_open_artist,
        *,
        session: UserSession | None = None,
        on_library_changed=None,
        dialog_parent=None,
        parent=None,
    ):
        super().__init__(radius=8, hover_alpha=22, press_alpha=38, active_alpha=16, parent=parent)
        self.setObjectName("searchListRow")
        self._item = item
        self._on_play = on_play
        self._actions_bar: TrackLikeReviewBar | None = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(2)

        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(8)
        self._title = QLabel((item.get("title") or i18n.tr("Без названия")).strip())
        self._title.setObjectName("searchRowTitle")
        self._title.setFont(_list_font())
        self._title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        title_row.addWidget(self._title, 1)
        if session is not None and on_library_changed and dialog_parent is not None:
            self._actions_bar = TrackLikeReviewBar(
                item,
                session,
                dialog_parent,
                on_changed=on_library_changed,
            )
            title_row.addWidget(self._actions_bar, 0, Qt.AlignmentFlag.AlignTop)
        lay.addLayout(title_row)

        art = (item.get("artist") or "").strip()
        self._artist = ArtistLinkLabel()
        self._artist.setObjectName("searchRowArtist")
        self._artist.setFont(_list_font())
        self._artist.set_artist(art)
        if on_open_artist and art:
            self._artist.artist_clicked.connect(on_open_artist)
        lay.addWidget(self._artist)
        self.install_interaction_filters()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._on_play:
            if self._actions_bar is not None and self._actions_bar.geometry().contains(
                event.position().toPoint()
            ):
                super().mouseReleaseEvent(event)
                return
            if self.rect().contains(event.position().toPoint()):
                self._on_play(self._item)
        super().mouseReleaseEvent(event)


class _SearchEntityRow(InteractiveRowFrame):
    def __init__(
        self,
        title: str,
        meta: str = "",
        body: str = "",
        on_activate=None,
        parent=None,
    ):
        super().__init__(radius=8, hover_alpha=22, press_alpha=38, active_alpha=16, parent=parent)
        self.setObjectName("searchListRow")
        self._on_activate = on_activate
        self.setCursor(
            Qt.CursorShape.PointingHandCursor
            if on_activate is not None
            else Qt.CursorShape.ArrowCursor
        )

        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(4)

        self._title = QLabel((title or i18n.tr("Без названия")).strip())
        self._title.setObjectName("searchRowTitle")
        self._title.setFont(_list_font())
        self._title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        lay.addWidget(self._title)

        if meta:
            self._meta = QLabel(meta.strip())
            self._meta.setObjectName("searchRowMeta")
            self._meta.setAttribute(
                Qt.WidgetAttribute.WA_TransparentForMouseEvents, True
            )
            lay.addWidget(self._meta)

        if body:
            self._body = QLabel(body.strip())
            self._body.setObjectName("searchRowBody")
            self._body.setWordWrap(True)
            self._body.setAttribute(
                Qt.WidgetAttribute.WA_TransparentForMouseEvents, True
            )
            lay.addWidget(self._body)

        self.install_interaction_filters()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self._on_activate is not None
            and self.rect().contains(event.position().toPoint())
        ):
            self._on_activate()
        super().mouseReleaseEvent(event)


class SearchTab(QWidget):
    library_changed = pyqtSignal()

    def __init__(
        self,
        session: UserSession | None = None,
        on_select_track=None,
        on_open_album=None,
        on_open_artist=None,
        on_open_review=None,
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("searchPage")

        self._session = session
        self._on_select_track = on_select_track
        self._on_open_album = on_open_album
        self._on_open_artist = on_open_artist
        self._on_open_review = on_open_review
        self._backend_url = os.getenv("CRATES_BACKEND_URL", "http://127.0.0.1:8000").rstrip(
            "/"
        )
        self._search_cache: dict[str, list[dict]] = {
            "albums": [],
            "tracks": [],
            "reviews": [],
            "users": [],
        }
        self._active_filter = "all"

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        page_scroll = QScrollArea()
        page_scroll.setObjectName("searchPageScroll")
        page_scroll.setWidgetResizable(True)
        page_scroll.setFrameShape(QFrame.Shape.NoFrame)
        page_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        inner = QWidget()
        inner.setStyleSheet("background: transparent;")
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(24, 20, 24, 24)
        inner_layout.setSpacing(14)

        # --- Поиск: компактная строка (без широкой градиентной полосы) ---
        search_row = QWidget()
        search_row.setObjectName("searchRowCompact")
        bar_layout = QHBoxLayout(search_row)
        bar_layout.setContentsMargins(0, 0, 0, 0)
        bar_layout.setSpacing(10)

        self._search_input = QLineEdit()
        self._search_input.setObjectName("searchInput")
        self._search_input.setPlaceholderText(i18n.tr("поиск . . . ."))
        bar_layout.addWidget(self._search_input, stretch=1)

        btn_search = QPushButton()
        btn_search.setObjectName("btnSearchCompact")
        btn_search.setFixedSize(48, 44)
        btn_search.setIcon(QIcon(_ICON_SEARCH))
        btn_search.setIconSize(QSize(24, 22))
        btn_search.setCursor(Qt.CursorShape.PointingHandCursor)

        bar_layout.addWidget(btn_search)
        btn_search.clicked.connect(self._run_search_now)
        self._search_input.returnPressed.connect(self._run_search_now)

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(_SEARCH_DEBOUNCE_MS)
        self._debounce.timeout.connect(self._do_search)
        self._search_input.textChanged.connect(self._on_search_text_changed)

        inner_layout.addWidget(search_row)

        # --- Filter buttons ---
        filter_row = QWidget()
        filter_row.setObjectName("filterRow")
        filter_layout = QHBoxLayout(filter_row)
        filter_layout.setContentsMargins(0, 0, 0, 0)
        filter_layout.setSpacing(10)

        self._filter_group = QButtonGroup(self)
        self._filter_group.setExclusive(True)
        self._filter_btns: dict[str, QPushButton] = {}
        for idx, (filter_key, label) in enumerate(_FILTER_DEFS):
            btn = QPushButton(i18n.tr(label))
            btn.setObjectName("btnNav")
            btn.setCheckable(True)
            btn.setProperty("filterKey", filter_key)
            btn.clicked.connect(self._on_filter_clicked)
            self._filter_group.addButton(btn, idx)
            filter_layout.addWidget(btn)
            self._filter_btns[filter_key] = btn

        if self._filter_btns:
            self._filter_btns["all"].setChecked(True)

        filter_layout.addStretch()
        inner_layout.addWidget(filter_row)

        # --- Recent tracks (отдельный контейнер — предсказуемый порядок в layout) ---
        self._history_host = QWidget()
        self._history_host.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Maximum,
        )
        hl = QVBoxLayout(self._history_host)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(8)

        history_label = QLabel(i18n.tr("недавние треки"))
        history_label.setObjectName("searchSectionLabel")
        hl.addWidget(history_label)

        self._history_list = QListWidget()
        self._history_list.setObjectName("searchHistory")
        self._history_list.setFont(_list_font())
        self._history_list.setSpacing(_LIST_SPACING)
        self._history_list.setUniformItemSizes(False)
        self._history_list.setTextElideMode(Qt.TextElideMode.ElideRight)
        self._history_list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._history_list.setVerticalScrollMode(
            QAbstractItemView.ScrollMode.ScrollPerPixel
        )
        self._history_list.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._history_list.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._history_list.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        hl.addWidget(self._history_list)
        inner_layout.addWidget(self._history_host)

        # --- Search results ---
        inner_layout.addSpacing(10)
        results_label = QLabel(i18n.tr("результаты"))
        results_label.setObjectName("searchSectionLabel")
        results_label.setMinimumHeight(
            max(22, results_label.sizeHint().height() + 4)
        )
        inner_layout.addWidget(results_label)

        self._results_list = QListWidget()
        self._results_list.setObjectName("searchResults")
        self._results_list.setFont(_list_font())
        self._results_list.setSpacing(_LIST_SPACING)
        self._results_list.setUniformItemSizes(False)
        self._results_list.setTextElideMode(Qt.TextElideMode.ElideRight)
        self._results_list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._results_list.setVerticalScrollMode(
            QAbstractItemView.ScrollMode.ScrollPerPixel
        )
        self._results_list.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._results_list.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        inner_layout.addWidget(self._results_list)

        inner_layout.addStretch()

        page_scroll.setWidget(inner)
        root.addWidget(page_scroll, stretch=1)

        self._refresh_recent_list()

    def _history_viewport_width(self) -> int:
        w = self._history_list.viewport().width()
        if w >= 40:
            return w
        pw = self.width() - 48
        return max(200, pw)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._refresh_recent_list()
        self._resize_results_list_height()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._refresh_recent_list()
        self._resize_results_list_height()

    def _on_search_text_changed(self, _text: str) -> None:
        if not self._search_input.text().strip():
            self._search_cache = {
                "albums": [],
                "tracks": [],
                "reviews": [],
                "users": [],
            }
            self._results_list.clear()
            self._resize_results_list_height()
        self._debounce.stop()
        self._debounce.start()

    def _run_search_now(self) -> None:
        self._debounce.stop()
        self._do_search()

    def _on_filter_clicked(self):
        sender = self.sender()
        if isinstance(sender, QPushButton):
            self._active_filter = str(sender.property("filterKey") or "all")
        if not self._search_input.text().strip():
            self._results_list.clear()
            self._resize_results_list_height()
            return
        self._render_search_results()

    def _load_recent_tracks(self) -> list[dict]:
        raw = _settings().value(_RECENT_KEY, "[]", str)
        if not isinstance(raw, str):
            raw = "[]"
        try:
            data = json.loads(raw)
            return data if isinstance(data, list) else []
        except json.JSONDecodeError:
            return []

    def _save_recent_tracks(self, items: list[dict]) -> None:
        _settings().setValue(_RECENT_KEY, json.dumps(items, ensure_ascii=False))

    def _play_track_item(self, music_item: dict) -> None:
        if not self._on_select_track:
            return
        self._push_recent_track(music_item)
        self._on_select_track(music_item)

    def _row_library_cb(self):
        if self._session is not None:
            return lambda: self.library_changed.emit()
        return None

    def _refresh_recent_list(self) -> None:
        self._history_list.clear()
        vw = self._history_viewport_width()
        for it in self._load_recent_tracks():
            if not isinstance(it, dict):
                continue
            item = QListWidgetItem()
            row = _SearchTrackRow(
                it,
                self._play_track_item,
                self._on_open_artist,
                session=self._session,
                on_library_changed=self._row_library_cb(),
                dialog_parent=self,
                parent=self._history_list,
            )
            row.setFixedWidth(max(vw - 8, 100))
            item_h = _row_height(row, _HISTORY_ROW_PX)
            item.setSizeHint(QSize(vw, item_h))
            self._history_list.addItem(item)
            self._history_list.setItemWidget(item, row)
        cnt = self._history_list.count()
        sp = self._history_list.spacing()
        fw = self._history_list.style().pixelMetric(
            QStyle.PixelMetric.PM_DefaultFrameWidth,
            None,
            self._history_list,
        )
        if cnt == 0:
            self._history_list.setFixedHeight(_LIST_ROW_MIN + 16)
            self._history_host.updateGeometry()
            return
        h = cnt * _HISTORY_ROW_PX + max(0, cnt - 1) * sp + max(8, 2 * fw + 6)
        self._history_list.setFixedHeight(h)
        self._history_host.updateGeometry()

    def _results_viewport_width(self) -> int:
        w = self._results_list.viewport().width()
        if w >= 40:
            return w
        pw = self.width() - 48
        return max(200, pw)

    def _resize_results_list_height(self) -> None:
        cnt = self._results_list.count()
        sp = self._results_list.spacing()
        fw = self._results_list.style().pixelMetric(
            QStyle.PixelMetric.PM_DefaultFrameWidth,
            None,
            self._results_list,
        )
        if cnt == 0:
            self._results_list.setFixedHeight(_LIST_ROW_MIN + 16)
            return
        rows_h = 0
        for idx in range(cnt):
            item = self._results_list.item(idx)
            rows_h += item.sizeHint().height() if item is not None else _RESULTS_ROW_PX
        h = rows_h + max(0, cnt - 1) * sp + max(8, 2 * fw + 6)
        self._results_list.setFixedHeight(h)

    def _push_recent_track(self, music_item: dict) -> None:
        def _same(a: dict, b: dict) -> bool:
            if a.get("id") is not None and a.get("id") == b.get("id"):
                return True
            return (
                (a.get("audio_url") or "") == (b.get("audio_url") or "")
                and (a.get("title") or "") == (b.get("title") or "")
            )

        items = [x for x in self._load_recent_tracks() if isinstance(x, dict)]
        items = [x for x in items if not _same(x, music_item)]
        items.insert(0, dict(music_item))
        self._save_recent_tracks(items[:_RECENT_MAX])
        self._refresh_recent_list()

    def _get_json(self, path: str):
        if self._session is not None:
            return self._session.client.get_json(path)
        try:
            url = f"{self._backend_url}{path}"
            req = Request(url, headers={"Accept": "application/json"})
            with urlopen(req, timeout=10) as resp:
                raw = resp.read().decode("utf-8")
                return resp.status, json.loads(raw)
        except Exception:
            return 0, None

    def _normalize_music_items(self, rows: list[dict]) -> list[dict]:
        api_base = self._session.client.base_url if self._session is not None else self._backend_url
        items: list[dict] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            item = dict(row)
            artwork_url = resolve_backend_media_url(
                api_base, (item.get("artwork_url") or "").strip()
            )
            if artwork_url:
                item["artwork_url"] = artwork_url
            items.append(item)
        return items

    def _extract_user_results(self, items: list[dict]) -> list[dict]:
        users: list[dict] = []
        seen: dict[str, dict] = {}
        for item in items:
            if not isinstance(item, dict):
                continue
            artist_user = item.get("artist_user")
            if isinstance(artist_user, dict):
                nickname = (artist_user.get("nickname") or "").strip()
                avatar_url = (artist_user.get("avatar_url") or "").strip()
                user_id = artist_user.get("id")
            else:
                nickname = ""
                avatar_url = ""
                user_id = None
            if not nickname:
                nickname = (item.get("artist") or "").strip()
            if not nickname:
                continue
            key = str(user_id) if user_id is not None else nickname.casefold()
            row = seen.get(key)
            if row is None:
                row = {
                    "id": user_id,
                    "nickname": nickname,
                    "avatar_url": avatar_url,
                    "items_count": 0,
                }
                seen[key] = row
                users.append(row)
            row["items_count"] = int(row.get("items_count") or 0) + 1
        return users

    def _fetch_album_queue(self, music_item: dict) -> list[dict]:
        provider = (music_item.get("provider") or "").strip()
        if provider == "collection":
            collection_id = music_item.get("external_id")
            if collection_id is None:
                return []
            path = f"/api/music-items/playback-queue/?collection_id={collection_id}"
        else:
            music_item_id = music_item.get("id")
            if music_item_id is None:
                return []
            path = f"/api/music-items/playback-queue/?music_item_id={music_item_id}"
        status, body = self._get_json(path)
        if status != 200 or not isinstance(body, dict):
            return []
        tracks = body.get("tracks")
        return self._normalize_music_items(tracks if isinstance(tracks, list) else [])

    def _open_album_result(self, music_item: dict) -> None:
        if self._on_open_album is None:
            return
        tracks = self._fetch_album_queue(music_item)
        if not tracks:
            return
        self._on_open_album(tracks, music_item)

    def _visible_results(self) -> list[tuple[str, dict]]:
        if self._active_filter == "albums":
            return [("album", row) for row in self._search_cache["albums"]]
        if self._active_filter == "tracks":
            return [("track", row) for row in self._search_cache["tracks"]]
        if self._active_filter == "reviews":
            return [("review", row) for row in self._search_cache["reviews"]]
        if self._active_filter == "users":
            return [("user", row) for row in self._search_cache["users"]]
        results: list[tuple[str, dict]] = []
        results.extend(("album", row) for row in self._search_cache["albums"])
        results.extend(("track", row) for row in self._search_cache["tracks"])
        results.extend(("review", row) for row in self._search_cache["reviews"])
        results.extend(("user", row) for row in self._search_cache["users"])
        return results

    def _add_result_widget(self, row_widget: QWidget, fallback_height: int = _RESULTS_ROW_PX) -> None:
        row_width = max(200, self._results_viewport_width(), self.width() - 48)
        item = QListWidgetItem()
        row_widget.setFixedWidth(max(row_width - 8, 100))
        item.setSizeHint(QSize(row_width, _row_height(row_widget, fallback_height)))
        self._results_list.addItem(item)
        self._results_list.setItemWidget(item, row_widget)

    def _render_search_results(self) -> None:
        self._results_list.clear()
        results = self._visible_results()
        if not results:
            empty = QLabel(i18n.tr("Ничего не найдено."))
            empty.setObjectName("searchEmptyLabel")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._add_result_widget(empty, fallback_height=_LIST_ROW_MIN + 12)
            self._resize_results_list_height()
            return

        for kind, payload in results:
            if kind == "track":
                row_widget = _SearchTrackRow(
                    payload,
                    self._play_track_item,
                    self._on_open_artist,
                    session=self._session,
                    on_library_changed=self._row_library_cb(),
                    dialog_parent=self,
                    parent=self._results_list,
                )
            elif kind == "album":
                artist = (payload.get("artist") or "").strip()
                meta = i18n.tr("Альбом")
                if artist:
                    meta = f"{meta} · {artist}"
                row_widget = _SearchEntityRow(
                    (payload.get("title") or i18n.tr("Без названия")).strip(),
                    meta=meta,
                    body=i18n.tr("Открыть альбом"),
                    on_activate=lambda item=payload: self._open_album_result(item),
                    parent=self._results_list,
                )
            elif kind == "review":
                author = (payload.get("author_label") or "—").strip()
                artist = _review_artist(payload)
                meta = f"{i18n.tr('Рецензия')} · {author}"
                if artist:
                    meta = f"{meta} · {artist}"
                row_widget = _SearchEntityRow(
                    _review_title(payload),
                    meta=meta,
                    body=_review_excerpt(payload),
                    on_activate=(
                        (lambda review=payload: self._on_open_review(review))
                        if self._on_open_review is not None
                        else None
                    ),
                    parent=self._results_list,
                )
            else:
                items_count = int(payload.get("items_count") or 0)
                body = i18n.tr("Найдено релизов:") + f" {items_count}"
                row_widget = _SearchEntityRow(
                    (payload.get("nickname") or "—").strip(),
                    meta=i18n.tr("Пользователь"),
                    body=body,
                    on_activate=(
                        (lambda nickname=(payload.get("nickname") or "").strip(): self._on_open_artist(nickname))
                        if self._on_open_artist is not None
                        else None
                    ),
                    parent=self._results_list,
                )
            self._add_result_widget(row_widget)
        self._resize_results_list_height()

    def _do_search(self) -> None:
        q = self._search_input.text().strip()
        if not q:
            self._search_cache = {
                "albums": [],
                "tracks": [],
                "reviews": [],
                "users": [],
            }
            self._results_list.clear()
            self._resize_results_list_height()
            return
        status_items, body_items = self._get_json(f"/api/music-items/?q={quote_plus(q)}")
        music_items = (
            self._normalize_music_items(
                [row for row in _response_list(body_items) if isinstance(row, dict)]
            )
            if status_items == 200
            else []
        )

        status_reviews, body_reviews = self._get_json(f"/api/reviews/?q={quote_plus(q)}")
        reviews = (
            [row for row in _response_list(body_reviews) if isinstance(row, dict)]
            if status_reviews == 200
            else []
        )

        self._search_cache = {
            "albums": [
                row
                for row in music_items
                if (row.get("kind") or "").strip().lower() == "album"
            ],
            "tracks": [
                row
                for row in music_items
                if (row.get("kind") or "").strip().lower() == "track"
            ],
            "reviews": reviews,
            "users": self._extract_user_results(music_items),
        }
        self._render_search_results()
