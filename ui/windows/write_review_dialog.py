"""Диалог: короткая рецензия на трек (POST /api/reviews/)."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QFrame,
    QMessageBox,
)


class WriteReviewDialog(QDialog):
    def __init__(self, client, music_item_id: int, track_title: str, parent=None):
        super().__init__(parent)
        self.setObjectName("writeReviewDialog")
        self.setWindowTitle("Рецензия — CRATES")
        self.setModal(True)
        self.setMinimumSize(420, 320)
        self._client = client
        self._music_item_id = music_item_id
        self._submitted = False

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(10)

        head = QLabel(f"Трек: {track_title}")
        head.setObjectName("writeReviewHead")
        head.setWordWrap(True)
        root.addWidget(head)

        self._text = QTextEdit()
        self._text.setObjectName("writeReviewBody")
        self._text.setPlaceholderText("Текст рецензии…")
        root.addWidget(self._text, stretch=1)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setObjectName("writeReviewLine")
        line.setFixedHeight(2)
        root.addWidget(line)

        row = QHBoxLayout()
        row.addStretch()
        cancel = QPushButton("ОТМЕНА")
        cancel.setObjectName("writeReviewCancelBtn")
        cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel.clicked.connect(self.reject)
        ok = QPushButton("ОТПРАВИТЬ")
        ok.setObjectName("writeReviewOkBtn")
        ok.setCursor(Qt.CursorShape.PointingHandCursor)
        ok.clicked.connect(self._submit)
        row.addWidget(cancel)
        row.addWidget(ok)
        root.addLayout(row)

    def _submit(self) -> None:
        body_text = self._text.toPlainText().strip()
        if not body_text:
            QMessageBox.information(self, "Рецензия", "Введите текст рецензии.")
            return
        status, body = self._client.post_json(
            "/api/reviews/",
            {
                "music_item": self._music_item_id,
                "collection": None,
                "text": body_text,
                "spoiler": False,
            },
        )
        if status in (200, 201):
            self._submitted = True
            self.accept()
        else:
            detail = body
            if isinstance(body, dict):
                detail = body.get("detail", body.get("non_field_errors", body))
            QMessageBox.warning(
                self,
                "Не удалось отправить",
                str(detail),
            )

    def submitted(self) -> bool:
        return self._submitted
