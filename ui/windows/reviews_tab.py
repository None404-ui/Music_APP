"""Вкладка «Рецензии»: топ по лайкам (избранное рецензий), лайк через API."""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer, QUrl
from PyQt6.QtGui import QColor, QImage, QMouseEvent, QPixmap
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PyQt6.QtWidgets import (
    QApplication,
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
from backend.session import UserSession
from ui import i18n
from ui.transient_scrollbars import enable_transient_vertical_page_scroll
from ui.artist_link_label import ArtistLinkLabel
from ui.cover_art import CoverArtWidget
from ui.interactive_fx import InteractiveRowFrame

_review_cover_nam: QNetworkAccessManager | None = None


def _review_cover_network() -> QNetworkAccessManager:
    global _review_cover_nam
    if _review_cover_nam is None:
        _review_cover_nam = QNetworkAccessManager(QApplication.instance())
    return _review_cover_nam


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
        return (mi.get("title") or i18n.tr("Без названия")).strip()
    col = review.get("collection")
    if isinstance(col, dict):
        return (col.get("title") or i18n.tr("Подборка")).strip()
    return i18n.tr("Рецензия")


def _subtitle(review: dict) -> str:
    mi = review.get("music_item")
    if isinstance(mi, dict):
        return (mi.get("artist") or "").strip()
    return ""


def _cover_url(review: dict, api_base: str = "") -> str:
    mi = review.get("music_item")
    if isinstance(mi, dict):
        return resolve_backend_media_url(
            api_base,
            (mi.get("artwork_url") or "").strip(),
        )
    col = review.get("collection")
    if isinstance(col, dict):
        return resolve_backend_media_url(
            api_base,
            (col.get("cover_url") or "").strip(),
        )
    return ""


class ReviewRow(InteractiveRowFrame):
    def __init__(
        self,
        review: dict,
        session: UserSession,
        on_changed,
        on_open_artist=None,
        on_open_review=None,
        parent=None,
    ):
        super().__init__(radius=10, hover_alpha=30, press_alpha=48, active_alpha=18, parent=parent)
        self.setObjectName("reviewRow")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setMinimumWidth(0)
        self._review = dict(review)
        self._session = session
        self._on_changed = on_changed
        self._on_open_review = on_open_review
        self._cover_reply: QNetworkReply | None = None
        if on_open_review is not None:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self.setToolTip(i18n.tr("Нажмите, чтобы открыть рецензию, комментарии и лайки."))

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(14)

        self._thumb = CoverArtWidget(
            radius=6,
            border_width=1,
            border_color=QColor("#89A194"),
            fill_color=QColor("#BDB685"),
            mask_color=QColor("#5c5748"),
            placeholder_text="♪",
            placeholder_color=QColor("#A14016"),
            placeholder_px=22,
        )
        self._thumb.setObjectName("reviewThumb")
        self._thumb.setFixedSize(70, 70)
        self._thumb.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._apply_thumb_style(False)
        self._load_cover(_cover_url(self._review, self._session.client.base_url))

        text_col = QVBoxLayout()
        text_col.setSpacing(2)

        self._title_lbl = QLabel(_headline(self._review))
        self._title_lbl.setObjectName("reviewAlbum")
        self._title_lbl.setWordWrap(True)
        self._title_lbl.setMinimumWidth(0)
        self._title_lbl.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        self._title_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        author = (self._review.get("author_label") or "—").strip()
        self._meta_lbl = QLabel(i18n.tr("Автор:") + f" {author}")
        self._meta_lbl.setObjectName("reviewMeta")
        self._meta_lbl.setWordWrap(True)
        self._meta_lbl.setMinimumWidth(0)
        self._meta_lbl.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        self._meta_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        body = (self._review.get("text") or "").strip().replace("\n", " ")
        excerpt = body[:240] + ("…" if len(body) > 240 else "")
        self._body_lbl = QLabel(excerpt or "—")
        self._body_lbl.setObjectName("reviewExcerpt")
        self._body_lbl.setWordWrap(True)
        self._body_lbl.setMinimumWidth(0)
        self._body_lbl.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        self._body_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

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
                artist_lbl.setAttribute(
                    Qt.WidgetAttribute.WA_TransparentForMouseEvents, True
                )
            text_col.addWidget(artist_lbl)
            self._artist_lbl = artist_lbl
        else:
            self._artist_lbl = None
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
        self._like_count.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, True
        )

        like_col.addWidget(self._like_btn, 0, Qt.AlignmentFlag.AlignHCenter)
        like_col.addWidget(self._like_count, 0, Qt.AlignmentFlag.AlignHCenter)

        layout.addWidget(self._thumb)
        layout.addLayout(text_col, stretch=1)
        layout.addLayout(like_col)
        self.install_interaction_filters()

    def _apply_thumb_style(self, hovered: bool) -> None:
        self._thumb.set_style_colors(
            border_color=QColor("#CB883A") if hovered else QColor("#89A194"),
            fill_color=QColor("#d1c996") if hovered else QColor("#BDB685"),
            mask_color=QColor("#6d6756") if hovered else QColor("#5c5748"),
        )

    def _load_cover(self, url: str) -> None:
        raw = (url or "").strip()
        self._thumb.clear_cover()
        if not raw.startswith(("http://", "https://")):
            return
        self._cover_reply = _review_cover_network().get(QNetworkRequest(QUrl(raw)))
        self._cover_reply.finished.connect(self._on_cover_finished)

    def _on_cover_finished(self) -> None:
        reply = self.sender()
        if not isinstance(reply, QNetworkReply):
            return
        if reply is not self._cover_reply:
            reply.deleteLater()
            return
        self._cover_reply = None
        try:
            if reply.error() != QNetworkReply.NetworkError.NoError:
                self._thumb.clear_cover()
                return
            img = QImage()
            if not img.loadFromData(reply.readAll()):
                self._thumb.clear_cover()
                return
            self._thumb.set_cover_pixmap(QPixmap.fromImage(img))
        finally:
            reply.deleteLater()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self._on_open_review is not None
            and self.rect().contains(event.position().toPoint())
        ):
            if self._like_btn.geometry().contains(event.position().toPoint()):
                super().mouseReleaseEvent(event)
                return
            if self._artist_lbl is not None and isinstance(
                self._artist_lbl, ArtistLinkLabel
            ) and self._artist_lbl.geometry().contains(event.position().toPoint()):
                super().mouseReleaseEvent(event)
                return
            self._on_open_review(dict(self._review))
        super().mouseReleaseEvent(event)

    def enterEvent(self, event) -> None:
        self._apply_thumb_style(True)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._apply_thumb_style(False)
        super().leaveEvent(event)

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
        # Отложить перерисовку списка: иначе _load_top удалит этот ReviewRow,
        # пока Qt ещё обрабатывает mouseRelease (RuntimeError: object deleted).
        if self._on_changed:
            QTimer.singleShot(0, self._on_changed)


class ReviewsTab(QWidget):
    def __init__(
        self,
        session: UserSession,
        on_open_artist=None,
        on_open_review=None,
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("reviewsPage")
        self._session = session
        self._on_open_artist = on_open_artist
        self._on_open_review = on_open_review

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 16, 24, 24)
        root.setSpacing(10)

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
        container.setObjectName("reviewsScrollInner")
        self._col = QVBoxLayout(container)
        self._col.setContentsMargins(0, 0, 0, 0)
        self._col.setSpacing(10)

        scroll.setWidget(container)
        self._scroll = scroll
        self._scroll_inner = container
        root.addWidget(scroll, stretch=1)
        enable_transient_vertical_page_scroll(scroll)

        QTimer.singleShot(0, self._load_top)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._sync_scroll_inner_width()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        QTimer.singleShot(0, self._sync_scroll_inner_width)

    def _sync_scroll_inner_width(self) -> None:
        inner = getattr(self, "_scroll_inner", None)
        if inner is None:
            return
        w = self._scroll.viewport().width()
        if w > 0:
            inner.setFixedWidth(w)

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
            self._hint.setText(i18n.tr("Не удалось загрузить топ рецензий."))
            self._hint.show()
            return
        if not reviews:
            self._hint.setText(i18n.tr("Пока нет рецензий."))
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
                        on_open_review=self._on_open_review,
                        parent=self,
                    )
                )
        self._col.addStretch()
        self._sync_scroll_inner_width()
