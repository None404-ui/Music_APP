"""Кнопки ♥ и рецензии для строки трека — те же иконки и API, что в плеере."""

from __future__ import annotations

import os
from typing import Callable, Optional

from PyQt6.QtCore import QSize, Qt, QTimer
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from backend.session import UserSession
from ui.interactive_fx import StatefulIconButton

_ICONS_DIR = os.path.join(os.path.dirname(__file__), "icons")


class TrackLikeReviewBar(QWidget):
    """
    Лайк (toggle, /api/favorites/) и рецензия (WriteReviewDialog).
    После успешного действия вызывает on_changed (обновить «Моё», счётчики и т.д.).
    """

    def __init__(
        self,
        item: dict,
        session: Optional[UserSession],
        dialog_parent: Optional[QWidget],
        on_changed: Optional[Callable[[], None]] = None,
        stats_label: Optional[QLabel] = None,
        parent=None,
    ):
        super().__init__(parent)
        self._item = item
        self._session = session
        self._dialog_parent = dialog_parent
        self._on_changed = on_changed
        self._stats_label = stats_label
        self._favorite_id: int | None = None

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

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

        mid = item.get("id")
        can = mid is not None and session is not None
        self._btn_like.setEnabled(can)
        self._btn_review.setEnabled(can)
        self._btn_like.setChecked(bool(item.get("user_favorited")))
        self._btn_like.toggled.connect(self._on_like_toggled)
        self._btn_review.clicked.connect(self._on_review_clicked)
        if can and self._btn_like.isChecked():
            QTimer.singleShot(0, lambda m=int(mid): self._resolve_favorite_id(m))

        lay.addWidget(self._btn_like)
        lay.addWidget(self._btn_review)

    def _emit_changed(self) -> None:
        if self._on_changed:
            self._on_changed()
        self._refresh_stats_label()

    def _refresh_stats_label(self) -> None:
        if self._stats_label is None:
            return
        likes = int(self._item.get("favorites_count") or 0)
        listens = int(self._item.get("listens_count") or 0)
        self._stats_label.setText(f"♥ {likes}  ·  {listens} слуш.")

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

    def _on_like_toggled(self, checked: bool) -> None:
        if not self._session:
            return
        mid = self._item.get("id")
        if mid is None:
            return
        mid = int(mid)
        if checked:
            st, body = self._session.client.post_json(
                "/api/favorites/", {"music_item": mid}
            )
            if st in (200, 201) and isinstance(body, dict):
                fid = body.get("id")
                if fid is not None:
                    self._favorite_id = int(fid)
                self._item["user_favorited"] = True
                self._item["favorites_count"] = int(
                    self._item.get("favorites_count") or 0
                ) + 1
                self._emit_changed()
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
                    self._item["user_favorited"] = False
                    self._item["favorites_count"] = max(
                        0, int(self._item.get("favorites_count") or 0) - 1
                    )
                    self._emit_changed()
                    return
            self._btn_like.blockSignals(True)
            self._btn_like.setChecked(True)
            self._btn_like.blockSignals(False)

    def _on_review_clicked(self) -> None:
        if not self._session or not self._dialog_parent:
            return
        mid = self._item.get("id")
        if mid is None:
            return
        from PyQt6.QtWidgets import QDialog

        from ui.windows.write_review_dialog import WriteReviewDialog

        title = str(self._item.get("title") or "трек")
        dlg = WriteReviewDialog(
            self._session.client,
            int(mid),
            title,
            self._dialog_parent,
        )
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.submitted():
            self._emit_changed()
