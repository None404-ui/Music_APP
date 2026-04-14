"""Вкладка «Рецензии»: топ по лайкам (избранное рецензий), лайк через API."""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer
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

from backend.session import UserSession
from ui.artist_link_label import ArtistLinkLabel
from ui.interactive_fx import InteractiveRowFrame


def _response_list(body) -> list:
    if isinstance(body, list):
        return body
    if isinstance(body, dict):
        r = body.get("results")
        return r if isinstance(r, list) else []
    return []


def _headline(review: dict) -> str:
    mi = review.get("music_item")
    if isinstance(mi, dict):
        return (mi.get("title") or "Без названия").strip()
    col = review.get("collection")
    if isinstance(col, dict):
        return (col.get("title") or "Подборка").strip()
    return "Рецензия"


def _subtitle(review: dict) -> str:
    mi = review.get("music_item")
    if isinstance(mi, dict):
        return (mi.get("artist") or "").strip()
    return ""


class ReviewRow(InteractiveRowFrame):
    def __init__(
        self,
        review: dict,
        session: UserSession,
        on_changed,
        on_open_artist=None,
        parent=None,
    ):
        super().__init__(radius=10, hover_alpha=30, press_alpha=48, active_alpha=18, parent=parent)
        self.setObjectName("reviewRow")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._review = dict(review)
        self._session = session
        self._on_changed = on_changed

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(14)

        thumb = QLabel()
        thumb.setObjectName("reviewThumb")
        thumb.setFixedSize(70, 70)
        thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thumb.setText("♪")

        text_col = QVBoxLayout()
        text_col.setSpacing(2)

        self._title_lbl = QLabel(_headline(self._review))
        self._title_lbl.setObjectName("reviewAlbum")

        author = (self._review.get("author_label") or "—").strip()
        self._meta_lbl = QLabel(author)
        self._meta_lbl.setObjectName("reviewMeta")

        body = (self._review.get("text") or "").strip().replace("\n", " ")
        excerpt = body[:200] + ("…" if len(body) > 200 else "")
        self._body_lbl = QLabel(excerpt or "—")
        self._body_lbl.setObjectName("reviewExcerpt")
        self._body_lbl.setWordWrap(True)

        sub = _subtitle(self._review)
        text_col.addWidget(self._title_lbl)
        if sub:
            if on_open_artist:
                artist_lbl = ArtistLinkLabel()
                artist_lbl.setObjectName("reviewArtist")
                artist_lbl.set_artist(sub)
                artist_lbl.artist_clicked.connect(on_open_artist)
            else:
                artist_lbl = QLabel(sub)
                artist_lbl.setObjectName("reviewArtist")
            text_col.addWidget(artist_lbl)
        text_col.addWidget(self._meta_lbl)
        text_col.addWidget(self._body_lbl)

        likes = int(self._review.get("favorites_count") or 0)
        liked = bool(self._review.get("user_favorited"))

        like_col = QVBoxLayout()
        like_col.setSpacing(4)
        like_col.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._like_btn = QPushButton("♥" if liked else "♡")
        self._like_btn.setObjectName("btnReviewLike")
        self._like_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._like_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._like_btn.clicked.connect(self._toggle_like)

        self._like_count = QLabel(str(likes))
        self._like_count.setObjectName("reviewLikeCount")
        self._like_count.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        like_col.addWidget(self._like_btn, 0, Qt.AlignmentFlag.AlignHCenter)
        like_col.addWidget(self._like_count, 0, Qt.AlignmentFlag.AlignHCenter)

        layout.addWidget(thumb)
        layout.addLayout(text_col, stretch=1)
        layout.addLayout(like_col)
        self.install_interaction_filters()

    def _toggle_like(self) -> None:
        rid = self._review.get("id")
        if rid is None:
            return
        liked = bool(self._review.get("user_favorited"))
        if liked:
            st, rows = self._session.client.get_json(
                f"/api/review-favorites/?review={rid}"
            )
            if st == 200 and isinstance(rows, list):
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    fid = row.get("id")
                    if fid is not None:
                        self._session.client.request_json(
                            "DELETE",
                            f"/api/review-favorites/{fid}/",
                        )
                        break
        else:
            self._session.client.post_json(
                "/api/review-favorites/",
                {"review": rid},
            )
        if self._on_changed:
            self._on_changed()


class ReviewsTab(QWidget):
    def __init__(self, session: UserSession, on_open_artist=None, parent=None):
        super().__init__(parent)
        self.setObjectName("reviewsPage")
        self._session = session
        self._on_open_artist = on_open_artist

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 16, 24, 24)
        root.setSpacing(10)

        heading = QLabel("ТОП РЕЦЕНЗИЙ")
        heading.setObjectName("reviewsHeading")
        root.addWidget(heading)

        self._hint = QLabel()
        self._hint.setObjectName("reviewsEmptyHint")
        self._hint.setWordWrap(True)
        self._hint.hide()
        root.addWidget(self._hint)

        scroll = QScrollArea()
        scroll.setObjectName("reviewsScroll")
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        self._col = QVBoxLayout(container)
        self._col.setContentsMargins(0, 0, 0, 0)
        self._col.setSpacing(10)

        scroll.setWidget(container)
        self._scroll = scroll
        root.addWidget(scroll, stretch=1)

        QTimer.singleShot(0, self._load_top)

    def reload_content(self) -> None:
        self._load_top()

    def _load_top(self) -> None:
        while self._col.count():
            it = self._col.takeAt(0)
            w = it.widget()
            if w is not None:
                w.deleteLater()
        self._hint.hide()

        st, body = self._session.client.get_json("/api/reviews/top/")
        reviews = _response_list(body) if st == 200 else []
        if st != 200:
            self._hint.setText("Не удалось загрузить топ рецензий.")
            self._hint.show()
            return
        if not reviews:
            self._hint.setText("Пока нет рецензий.")
            self._hint.show()
            return

        for r in reviews:
            if isinstance(r, dict):
                self._col.addWidget(
                    ReviewRow(
                        r,
                        self._session,
                        self._load_top,
                        on_open_artist=self._on_open_artist,
                        parent=self,
                    )
                )
        self._col.addStretch()
