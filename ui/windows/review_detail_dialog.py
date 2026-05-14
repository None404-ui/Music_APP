"""Страница подробной рецензии с реальными комментариями через API."""

from __future__ import annotations

import re
from datetime import datetime

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QTextOption
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ui import i18n
from ui.transient_scrollbars import enable_transient_vertical_page_scroll
from ui.artist_link_label import ArtistLinkLabel
from ui.interactive_fx import fade_in_widget


_LONG_RUN_RE = re.compile(r"(\S{36})")


def _fmt_date(raw: str) -> str:
    if not raw:
        return ""
    try:
        txt = raw.replace("Z", "+00:00")
        dt = datetime.fromisoformat(txt)
        return dt.strftime("%d.%m.%Y %H:%M")
    except (ValueError, TypeError):
        return raw


def _headline_track(review: dict) -> tuple[str, str]:
    mi = review.get("music_item")
    if isinstance(mi, dict):
        return (
            (mi.get("title") or i18n.tr("Без названия")).strip(),
            (mi.get("artist") or "").strip(),
        )
    col = review.get("collection")
    if isinstance(col, dict):
        return ((col.get("title") or i18n.tr("Подборка")).strip(), "")
    return (i18n.tr("Рецензия"), "")


def _soft_wrap(text: str) -> str:
    """Позволяет QLabel переносить длинные строки без пробелов."""
    return _LONG_RUN_RE.sub(lambda m: m.group(1) + "\u200b", text or "")


class _CommentRow(QFrame):
    def __init__(self, comment: dict, parent=None):
        super().__init__(parent)
        self.setObjectName("reviewCommentRow")
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 10)
        lay.setSpacing(4)

        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        head.setSpacing(8)

        author = (comment.get("author_label") or "—").strip()
        author_lbl = QLabel(_soft_wrap(author))
        author_lbl.setObjectName("reviewCommentAuthor")
        author_lbl.setMinimumWidth(0)
        author_lbl.setWordWrap(True)
        author_lbl.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )

        date_lbl = QLabel(_fmt_date(str(comment.get("created_at") or "")))
        date_lbl.setObjectName("reviewCommentDate")
        date_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        head.addWidget(author_lbl, stretch=1)
        head.addWidget(date_lbl, stretch=0)
        lay.addLayout(head)

        body = QLabel(_soft_wrap((comment.get("text") or "").strip()))
        body.setObjectName("reviewCommentBody")
        body.setMinimumWidth(0)
        body.setWordWrap(True)
        body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        body.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        lay.addWidget(body)


class ReviewDetailPage(QWidget):
    """Полная страница рецензии внутри основного стека приложения."""

    def __init__(
        self,
        session,
        on_back=None,
        on_changed=None,
        on_open_artist=None,
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("reviewDetailPage")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._review: dict = {}
        self._session = session
        self._on_back = on_back
        self._on_changed = on_changed
        self._on_open_artist = on_open_artist

        self._return_index = 0
        self._review_id = None
        self._favorites_count = 0
        self._user_favorited = False

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 18)
        root.setSpacing(12)

        nav_row = QHBoxLayout()
        nav_row.setContentsMargins(0, 0, 0, 0)
        nav_row.setSpacing(12)

        self._back_btn = QPushButton(i18n.tr("← назад"))
        self._back_btn.setObjectName("reviewDetailBackBtn")
        self._back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._back_btn.clicked.connect(self._go_back)
        nav_row.addWidget(self._back_btn, 0, Qt.AlignmentFlag.AlignLeft)

        page_title = QLabel(i18n.tr("Рецензия"))
        page_title.setObjectName("reviewDetailPageTitle")
        page_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        nav_row.addWidget(page_title, stretch=1)
        nav_row.addSpacing(self._back_btn.sizeHint().width())
        root.addLayout(nav_row)

        self._kind_lbl = QLabel()
        self._kind_lbl.setObjectName("reviewDetailKind")
        self._kind_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self._kind_lbl)

        self._head_lbl = QLabel()
        self._head_lbl.setObjectName("reviewDetailHeadline")
        self._head_lbl.setMinimumWidth(0)
        self._head_lbl.setWordWrap(True)
        self._head_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._head_lbl.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        root.addWidget(self._head_lbl)

        self._artist_wrap = QWidget()
        awl = QVBoxLayout(self._artist_wrap)
        awl.setContentsMargins(0, 0, 0, 0)
        awl.setSpacing(0)
        if on_open_artist:
            self._artist_lbl = ArtistLinkLabel()
            self._artist_lbl.setObjectName("reviewDetailArtist")
            self._artist_lbl.artist_clicked.connect(self._handle_artist_click)
            self._artist_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        else:
            self._artist_lbl = QLabel()
            self._artist_lbl.setObjectName("reviewDetailArtist")
            self._artist_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._artist_lbl.setMinimumWidth(0)
        self._artist_lbl.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        awl.addWidget(self._artist_lbl)
        root.addWidget(self._artist_wrap)

        meta_row = QHBoxLayout()
        meta_row.setContentsMargins(0, 0, 0, 0)
        meta_row.setSpacing(8)
        self._author_lbl = QLabel()
        self._author_lbl.setObjectName("reviewDetailMeta")
        self._author_lbl.setMinimumWidth(0)
        self._author_lbl.setWordWrap(True)
        self._author_lbl.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        self._date_lbl = QLabel()
        self._date_lbl.setObjectName("reviewDetailMeta")
        self._date_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        meta_row.addWidget(self._author_lbl, stretch=1)
        meta_row.addWidget(self._date_lbl, stretch=0)
        root.addLayout(meta_row)

        line = QFrame()
        line.setObjectName("reviewDetailLine")
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFixedHeight(2)
        root.addWidget(line)

        self._scroll = QScrollArea()
        self._scroll.setObjectName("reviewDetailScroll")
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)

        self._body_w = QWidget()
        self._body_w.setObjectName("reviewDetailScrollBody")
        self._body_w.setMinimumWidth(0)
        self._body_w.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        bl = QVBoxLayout(self._body_w)
        bl.setContentsMargins(4, 4, 4, 4)
        bl.setSpacing(14)

        self._body_lbl = QLabel()
        self._body_lbl.setObjectName("reviewDetailBody")
        self._body_lbl.setMinimumWidth(0)
        self._body_lbl.setWordWrap(True)
        self._body_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._body_lbl.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._body_lbl.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        bl.addWidget(self._body_lbl)

        actions_row = QHBoxLayout()
        actions_row.setContentsMargins(0, 0, 0, 0)
        actions_row.setSpacing(8)
        self._like_btn = QPushButton("♡")
        self._like_btn.setObjectName("reviewDetailLikeBtn")
        self._like_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._like_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._like_btn.clicked.connect(self._toggle_like)
        self._like_count_lbl = QLabel("0")
        self._like_count_lbl.setObjectName("reviewDetailLikeCount")
        actions_row.addWidget(self._like_btn)
        actions_row.addWidget(self._like_count_lbl)
        actions_row.addStretch()
        bl.addLayout(actions_row)

        comments_head = QLabel(i18n.tr("Комментарии"))
        comments_head.setObjectName("reviewDetailCommentsHead")
        bl.addWidget(comments_head)

        self._comments_col_host = QWidget()
        self._comments_col_host.setObjectName("reviewCommentsHost")
        self._comments_col_host.setMinimumWidth(0)
        self._comments_col_host.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        self._comments_col = QVBoxLayout(self._comments_col_host)
        self._comments_col.setContentsMargins(0, 0, 0, 0)
        self._comments_col.setSpacing(8)
        bl.addWidget(self._comments_col_host)

        self._comments_hint = QLabel("")
        self._comments_hint.setObjectName("reviewDetailEmptyHint")
        self._comments_hint.setMinimumWidth(0)
        self._comments_hint.setWordWrap(True)
        self._comments_hint.hide()
        bl.addWidget(self._comments_hint)

        self._compose = QTextEdit()
        self._compose.setObjectName("reviewCommentCompose")
        self._compose.setPlaceholderText(i18n.tr("Написать комментарий…"))
        self._compose.setFixedHeight(86)
        self._compose.setMinimumWidth(0)
        self._compose.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self._compose.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self._compose.setWordWrapMode(QTextOption.WrapMode.WrapAnywhere)
        if session is None or getattr(session, "user_id", None) is None:
            self._compose.setEnabled(False)
            self._compose.setPlaceholderText(
                i18n.tr("Войдите, чтобы оставить комментарий.")
            )
        bl.addWidget(self._compose)

        compose_row = QHBoxLayout()
        compose_row.addStretch()
        self._submit_btn = QPushButton(i18n.tr("ОТПРАВИТЬ"))
        self._submit_btn.setObjectName("reviewCommentSubmitBtn")
        self._submit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._submit_btn.clicked.connect(self._submit_comment)
        if session is None or getattr(session, "user_id", None) is None:
            self._submit_btn.setEnabled(False)
        compose_row.addWidget(self._submit_btn)
        bl.addLayout(compose_row)

        bl.addStretch()
        self._scroll.setWidget(self._body_w)
        root.addWidget(self._scroll, stretch=1)
        enable_transient_vertical_page_scroll(self._scroll)

    def load_review(self, review: dict, return_index: int = 0) -> None:
        self._review = dict(review or {})
        self._return_index = return_index
        self._review_id = self._review.get("id")
        self._favorites_count = int(self._review.get("favorites_count") or 0)
        self._user_favorited = bool(self._review.get("user_favorited"))
        self._compose.clear()
        self._apply_review_to_ui()
        self._sync_scroll_inner_width()
        QTimer.singleShot(0, self._after_load)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._sync_scroll_inner_width()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._sync_scroll_inner_width()
        fade_in_widget(self)

    def _sync_scroll_inner_width(self) -> None:
        if not hasattr(self, "_scroll") or not hasattr(self, "_body_w"):
            return
        w = self._scroll.viewport().width()
        if w > 0:
            self._body_w.setFixedWidth(w)

    def _go_back(self) -> None:
        if self._on_back:
            self._on_back(self._return_index)

    def _handle_artist_click(self, name: str) -> None:
        if self._on_open_artist is None or not (name or "").strip():
            return
        self._on_open_artist(name)

    def _after_load(self) -> None:
        self._sync_scroll_inner_width()
        self._hydrate_review_from_api()
        self._reload_comments()

    def _apply_review_to_ui(self) -> None:
        coll = self._review.get("collection")
        is_album = isinstance(coll, dict) and not self._review.get("music_item")
        self._kind_lbl.setText(i18n.tr("Альбом") if is_album else i18n.tr("Трек"))

        title, artist = _headline_track(self._review)
        self._head_lbl.setText(_soft_wrap(title))
        art = (artist or "").strip()
        if art:
            self._artist_wrap.show()
            if isinstance(self._artist_lbl, ArtistLinkLabel):
                self._artist_lbl.set_artist(art)
            else:
                self._artist_lbl.setText(_soft_wrap(art))
        else:
            self._artist_wrap.hide()

        author = (self._review.get("author_label") or "—").strip()
        self._author_lbl.setText(_soft_wrap(i18n.tr("Автор:") + f" {author}"))
        self._date_lbl.setText(_fmt_date(str(self._review.get("created_at") or "")))

        body_txt = (self._review.get("text") or "").strip() or "—"
        self._body_lbl.setText(_soft_wrap(body_txt))

        self._like_btn.setText("♥" if self._user_favorited else "♡")
        self._like_count_lbl.setText(str(self._favorites_count))

    def _hydrate_review_from_api(self) -> None:
        rid = self._review.get("id")
        client = self._client()
        if rid is None or client is None:
            return
        try:
            rid_int = int(rid)
        except (TypeError, ValueError):
            return
        st, body = client.get_json(f"/api/reviews/{rid_int}/")
        if st == 200 and isinstance(body, dict):
            self._review = body
            self._review_id = self._review.get("id")
            self._favorites_count = int(self._review.get("favorites_count") or 0)
            self._user_favorited = bool(self._review.get("user_favorited"))
            self._apply_review_to_ui()

    def _client(self):
        return self._session.client if self._session is not None else None

    def _toggle_like(self) -> None:
        if self._review_id is None or self._client() is None:
            return
        if self._user_favorited:
            st, rows = self._client().get_json(
                f"/api/review-favorites/?review={self._review_id}"
            )
            if st == 200 and isinstance(rows, list):
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    fid = row.get("id")
                    if fid is not None:
                        self._client().request_json(
                            "DELETE",
                            f"/api/review-favorites/{fid}/",
                        )
                        break
            self._user_favorited = False
            self._favorites_count = max(0, self._favorites_count - 1)
        else:
            st, _ = self._client().post_json(
                "/api/review-favorites/",
                {"review": self._review_id},
            )
            if st in (200, 201):
                self._user_favorited = True
                self._favorites_count += 1
        self._like_btn.setText("♥" if self._user_favorited else "♡")
        self._like_count_lbl.setText(str(self._favorites_count))
        self._review["favorites_count"] = self._favorites_count
        self._review["user_favorited"] = self._user_favorited
        if self._on_changed:
            self._on_changed()

    def _reload_comments(self) -> None:
        while self._comments_col.count():
            it = self._comments_col.takeAt(0)
            w = it.widget()
            if w is not None:
                w.deleteLater()
        self._comments_hint.hide()

        if self._client() is None or self._review_id is None:
            self._comments_hint.setText(i18n.tr("Комментарии недоступны."))
            self._comments_hint.show()
            return

        st, body = self._client().get_json(
            f"/api/comments/?review_id={self._review_id}"
        )
        rows: list = []
        if st == 200:
            if isinstance(body, list):
                rows = body
            elif isinstance(body, dict):
                rows = body.get("results") or []

        rows = [r for r in rows if isinstance(r, dict) and not r.get("deleted_at")]
        rows.sort(key=lambda r: str(r.get("created_at") or ""))

        if not rows:
            self._comments_hint.setText(
                i18n.tr("Пока нет комментариев. Будьте первым!")
            )
            self._comments_hint.show()
            return

        for c in rows:
            self._comments_col.addWidget(_CommentRow(c, parent=self._comments_col_host))
        self._sync_scroll_inner_width()

    def _submit_comment(self) -> None:
        if self._client() is None or self._review_id is None:
            return
        text = self._compose.toPlainText().strip()
        if not text:
            QMessageBox.information(
                self,
                i18n.tr("Комментарий"),
                i18n.tr("Введите текст комментария."),
            )
            return
        st, body = self._client().post_json(
            "/api/comments/",
            {"review": self._review_id, "text": text, "parent": None},
        )
        if st in (200, 201):
            self._compose.clear()
            self._reload_comments()
            return
        detail = body
        if isinstance(body, dict):
            detail = body.get("detail") or body.get("non_field_errors") or body
        QMessageBox.warning(
            self,
            i18n.tr("Не удалось отправить"),
            str(detail),
        )
