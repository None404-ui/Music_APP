from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QScrollArea, QFrame, QSizePolicy,
)
from PyQt6.QtCore import Qt


class ReviewRow(QFrame):
    def __init__(self, album: str, author: str, score: str, body: str, parent=None):
        super().__init__(parent)
        self.setObjectName("reviewRow")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(14)

        thumb = QLabel()
        thumb.setObjectName("reviewThumb")
        thumb.setFixedSize(70, 70)
        thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thumb.setText("♪")
        thumb.setStyleSheet("font-size: 22px; color: #A14016;")

        text_col = QVBoxLayout()
        text_col.setSpacing(2)

        title_lbl = QLabel(album)
        title_lbl.setObjectName("reviewTitle")

        meta_lbl = QLabel(f"{author}  ·  {score}")
        meta_lbl.setObjectName("reviewMeta")

        body_lbl = QLabel(body)
        body_lbl.setObjectName("reviewBody")
        body_lbl.setWordWrap(True)

        text_col.addWidget(title_lbl)
        text_col.addWidget(meta_lbl)
        text_col.addWidget(body_lbl)

        score_lbl = QLabel(score)
        score_lbl.setObjectName("reviewScore")
        score_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        score_lbl.setFixedWidth(40)

        layout.addWidget(thumb)
        layout.addLayout(text_col, stretch=1)
        layout.addWidget(score_lbl)


_PLACEHOLDER_REVIEWS = [
    ("Название альбома", "Автор рецензии", "9/10",
     "Краткое описание рецензии..."),
] * 6


class ReviewsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("reviewsPage")

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 16, 24, 24)
        root.setSpacing(10)

        heading = QLabel("ТОП РЕЦЕНЗИЙ")
        heading.setObjectName("reviewsHeading")
        root.addWidget(heading)

        scroll = QScrollArea()
        scroll.setObjectName("reviewsScroll")
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        col = QVBoxLayout(container)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(10)

        for album, author, score, body in _PLACEHOLDER_REVIEWS:
            col.addWidget(ReviewRow(album, author, score, body))

        col.addStretch()
        scroll.setWidget(container)
        root.addWidget(scroll, stretch=1)
