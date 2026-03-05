from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QScrollArea, QPushButton, QFrame, QSizePolicy,
)
from PyQt6.QtCore import Qt


class AlbumCard(QFrame):
    def __init__(self, title: str = "Альбом", parent=None):
        super().__init__(parent)
        self.setObjectName("albumCard")
        self.setFixedSize(140, 170)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 6)
        layout.setSpacing(4)

        cover = QLabel()
        cover.setFixedSize(140, 140)
        cover.setObjectName("albumCover")
        cover.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cover.setText("♪")
        cover.setStyleSheet("font-size: 32px; color: #A14016;")

        name = QLabel(title)
        name.setObjectName("albumTitle")
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(cover)
        layout.addWidget(name)


class ArtistWidget(QWidget):
    def __init__(self, name: str = "Имя", parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)
        layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        avatar = QLabel()
        avatar.setObjectName("artistAvatar")
        avatar.setFixedSize(80, 80)
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar.setText("♫")
        avatar.setStyleSheet("font-size: 24px; color: #A14016;")

        label = QLabel(name)
        label.setObjectName("artistName")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setFixedWidth(90)

        layout.addWidget(avatar, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(label, alignment=Qt.AlignmentFlag.AlignHCenter)


class CarouselPanel(QWidget):
    def __init__(self, items: list[QWidget], parent=None):
        super().__init__(parent)
        self.setObjectName("carouselPanel")

        outer = QHBoxLayout(self)
        outer.setContentsMargins(8, 12, 8, 12)
        outer.setSpacing(0)

        self._btn_left = QPushButton("‹")
        self._btn_left.setObjectName("btnArrow")
        self._btn_left.clicked.connect(self._scroll_left)

        self._scroll = QScrollArea()
        self._scroll.setObjectName("carouselScroll")
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)

        inner_widget = QWidget()
        inner_widget.setObjectName("carouselInner")
        inner_widget.setStyleSheet("background: transparent;")
        inner_layout = QHBoxLayout(inner_widget)
        inner_layout.setContentsMargins(8, 0, 8, 0)
        inner_layout.setSpacing(14)
        for item in items:
            inner_layout.addWidget(item)
        inner_layout.addStretch()

        self._scroll.setWidget(inner_widget)

        self._btn_right = QPushButton("›")
        self._btn_right.setObjectName("btnArrow")
        self._btn_right.clicked.connect(self._scroll_right)

        outer.addWidget(self._btn_left)
        outer.addWidget(self._scroll, stretch=1)
        outer.addWidget(self._btn_right)

    def _scroll_left(self):
        bar = self._scroll.horizontalScrollBar()
        bar.setValue(bar.value() - 160)

    def _scroll_right(self):
        bar = self._scroll.horizontalScrollBar()
        bar.setValue(bar.value() + 160)


class PopularTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("popularPage")

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 16, 24, 24)
        root.setSpacing(10)

        root.addWidget(self._make_section_heading("АЛЬБОМЫ"))
        album_cards = [AlbumCard(f"Альбом {i + 1}") for i in range(8)]
        root.addWidget(CarouselPanel(album_cards))

        root.addSpacing(16)

        root.addWidget(self._make_section_heading("ИСПОЛНИТЕЛИ"))
        artist_widgets = [ArtistWidget(f"Артист {i + 1}") for i in range(8)]
        root.addWidget(CarouselPanel(artist_widgets))

        root.addStretch()

    @staticmethod
    def _make_section_heading(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("sectionHeading")
        return label
