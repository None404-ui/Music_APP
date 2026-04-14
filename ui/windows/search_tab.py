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

from PyQt6.QtWidgets import (
    QAbstractItemView,
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

_FILTER_LABELS = ["альбомы", "рецензии", "исполнители"]

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
        self._title = QLabel((item.get("title") or "Без названия").strip())
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


class SearchTab(QWidget):
    library_changed = pyqtSignal()

    def __init__(
        self,
        session: UserSession | None = None,
        on_select_track=None,
        on_open_artist=None,
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("searchPage")

        self._session = session
        self._on_select_track = on_select_track
        self._on_open_artist = on_open_artist
        self._backend_url = os.getenv("CRATES_BACKEND_URL", "http://127.0.0.1:8000").rstrip(
            "/"
        )

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
        self._search_input.setPlaceholderText("поиск . . . .")
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

        self._filter_btns: list[QPushButton] = []
        for label in _FILTER_LABELS:
            btn = QPushButton(label)
            btn.setObjectName("btnFilter")
            btn.setCheckable(True)
            btn.clicked.connect(self._on_filter_clicked)
            filter_layout.addWidget(btn)
            self._filter_btns.append(btn)

        if self._filter_btns:
            self._filter_btns[0].setChecked(True)

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

        history_label = QLabel("недавние треки")
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
        results_label = QLabel("результаты")
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
        self._debounce.stop()
        self._debounce.start()

    def _run_search_now(self) -> None:
        self._debounce.stop()
        self._do_search()

    def _on_filter_clicked(self):
        sender = self.sender()
        for btn in self._filter_btns:
            if btn is not sender:
                btn.setChecked(False)

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
        h = cnt * _RESULTS_ROW_PX + max(0, cnt - 1) * sp + max(8, 2 * fw + 6)
        self._results_list.setFixedHeight(h)

    def _push_recent_track(self, music_item: dict) -> None:
        def _same(a: dict, b: dict) -> bool:
            if a.get("id") is not None and a.get("id") == b.get("id"):
                return True
            return (
                (a.get("playback_ref") or "") == (b.get("playback_ref") or "")
                and (a.get("title") or "") == (b.get("title") or "")
            )

        items = [x for x in self._load_recent_tracks() if isinstance(x, dict)]
        items = [x for x in items if not _same(x, music_item)]
        items.insert(0, dict(music_item))
        self._save_recent_tracks(items[:_RECENT_MAX])
        self._refresh_recent_list()

    def _do_search(self) -> None:
        q = self._search_input.text().strip()
        if not q:
            return
        self._results_list.clear()
        items: list = []
        if self._session is not None:
            try:
                api_base = self._session.client.base_url
                st, data = self._session.client.get_json(
                    f"/api/music-items/?q={quote_plus(q)}"
                )
                if st == 200:
                    if isinstance(data, list):
                        raw_items = data
                    elif isinstance(data, dict):
                        r = data.get("results")
                        raw_items = r if isinstance(r, list) else []
                    else:
                        raw_items = []
                    for it in raw_items:
                        if not isinstance(it, dict):
                            continue
                        row = dict(it)
                        au = resolve_backend_media_url(
                            api_base, (row.get("artwork_url") or "").strip()
                        )
                        if au:
                            row["artwork_url"] = au
                        items.append(row)
            except Exception:
                items = []
        else:
            try:
                url = f"{self._backend_url}/api/music-items/?q={quote_plus(q)}"
                req = Request(url, headers={"Accept": "application/json"})
                with urlopen(req, timeout=10) as resp:
                    raw = resp.read().decode("utf-8")
                    data = json.loads(raw)
                raw_items = (
                    data.get("results", data) if isinstance(data, dict) else data
                )
                if not isinstance(raw_items, list):
                    raw_items = []
                items = [x for x in raw_items if isinstance(x, dict)]
            except Exception:
                items = []

        rw = max(200, self._results_viewport_width(), self.width() - 48)
        for it in items:
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
                parent=self._results_list,
            )
            row.setFixedWidth(max(rw - 8, 100))
            item_h = _row_height(row, _RESULTS_ROW_PX)
            item.setSizeHint(QSize(rw, item_h))
            self._results_list.addItem(item)
            self._results_list.setItemWidget(item, row)
        self._resize_results_list_height()
