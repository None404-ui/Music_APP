from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QWidget,
    QFrame,
    QSizePolicy,
)
from PyQt6.QtCore import Qt


class ReviewDetailDialog(QDialog):
    """Полная страница рецензии по клику на заголовок у альбома."""

    def __init__(
        self,
        album_title: str,
        headline: str,
        author: str,
        score: str,
        body: str,
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("reviewDetailDialog")
        self.setWindowTitle("Рецензия — CRATES")
        self.setModal(True)
        self.setMinimumSize(440, 360)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(12)

        album_lbl = QLabel(album_title)
        album_lbl.setObjectName("reviewDetailAlbum")
        album_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(album_lbl)

        head_lbl = QLabel(headline)
        head_lbl.setObjectName("reviewDetailHeadline")
        head_lbl.setWordWrap(True)
        head_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(head_lbl)

        meta_row = QHBoxLayout()
        author_lbl = QLabel(author)
        author_lbl.setObjectName("reviewDetailMeta")
        score_lbl = QLabel(score)
        score_lbl.setObjectName("reviewDetailScore")
        meta_row.addWidget(author_lbl)
        meta_row.addStretch()
        meta_row.addWidget(score_lbl)
        root.addLayout(meta_row)

        line = QFrame()
        line.setObjectName("reviewDetailLine")
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFixedHeight(2)
        root.addWidget(line)

        scroll = QScrollArea()
        scroll.setObjectName("reviewDetailScroll")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        body_w = QWidget()
        body_w.setStyleSheet("background: transparent;")
        bl = QVBoxLayout(body_w)
        bl.setContentsMargins(4, 0, 4, 0)
        body_lbl = QLabel(body)
        body_lbl.setObjectName("reviewDetailBody")
        body_lbl.setWordWrap(True)
        body_lbl.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        bl.addWidget(body_lbl)
        scroll.setWidget(body_w)
        root.addWidget(scroll, stretch=1)

        btn = QPushButton("ЗАКРЫТЬ")
        btn.setObjectName("reviewDetailCloseBtn")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(self.accept)
        root.addWidget(btn)
