from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QSlider, QSizePolicy,
)
from PyQt6.QtCore import Qt


class PlayerTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("playerPage")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addStretch()

        center = QWidget()
        center.setObjectName("playerCenter")
        center.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        col = QVBoxLayout(center)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(16)
        col.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self._art = QLabel()
        self._art.setObjectName("albumArt")
        self._art.setFixedSize(280, 280)
        self._art.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._art.setText("♪")
        self._art.setStyleSheet("font-size: 72px; color: #A14016;")
        col.addWidget(self._art, alignment=Qt.AlignmentFlag.AlignHCenter)

        self._track_title = QLabel("Название трека")
        self._track_title.setObjectName("trackTitle")
        self._track_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        col.addWidget(self._track_title, alignment=Qt.AlignmentFlag.AlignHCenter)

        self._track_artist = QLabel("Исполнитель")
        self._track_artist.setObjectName("trackArtist")
        self._track_artist.setAlignment(Qt.AlignmentFlag.AlignCenter)
        col.addWidget(self._track_artist, alignment=Qt.AlignmentFlag.AlignHCenter)

        col.addSpacing(8)

        progress_wrapper = QWidget()
        progress_wrapper.setFixedWidth(320)
        pw_layout = QVBoxLayout(progress_wrapper)
        pw_layout.setContentsMargins(0, 0, 0, 0)
        pw_layout.setSpacing(4)

        self._progress = QSlider(Qt.Orientation.Horizontal)
        self._progress.setObjectName("progressSlider")
        self._progress.setRange(0, 100)
        self._progress.setValue(18)
        pw_layout.addWidget(self._progress)

        time_row = QHBoxLayout()
        lbl_current = QLabel("0:42")
        lbl_current.setObjectName("timeLabel")
        lbl_total = QLabel("3:55")
        lbl_total.setObjectName("timeLabel")
        time_row.addWidget(lbl_current)
        time_row.addStretch()
        time_row.addWidget(lbl_total)
        pw_layout.addLayout(time_row)

        col.addWidget(progress_wrapper, alignment=Qt.AlignmentFlag.AlignHCenter)

        controls = QWidget()
        controls.setObjectName("controlsRow")
        ctrl_layout = QHBoxLayout(controls)
        ctrl_layout.setContentsMargins(0, 0, 0, 0)
        ctrl_layout.setSpacing(8)
        ctrl_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        btn_prev = QPushButton("⏮")
        btn_prev.setObjectName("btnPlayback")

        self._btn_play = QPushButton("⏸")
        self._btn_play.setObjectName("btnPlayback")
        self._btn_play.setStyleSheet("font-size: 28px;")
        self._btn_play.clicked.connect(self._toggle_play)

        btn_next = QPushButton("⏭")
        btn_next.setObjectName("btnPlayback")

        ctrl_layout.addWidget(btn_prev)
        ctrl_layout.addWidget(self._btn_play)
        ctrl_layout.addWidget(btn_next)

        col.addWidget(controls, alignment=Qt.AlignmentFlag.AlignHCenter)

        vol_row = QHBoxLayout()
        vol_row.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        vol_lbl = QLabel("🔈")
        vol_lbl.setObjectName("volumeLabel")
        self._volume = QSlider(Qt.Orientation.Horizontal)
        self._volume.setObjectName("volumeSlider")
        self._volume.setFixedWidth(120)
        self._volume.setRange(0, 100)
        self._volume.setValue(75)
        vol_row.addWidget(vol_lbl)
        vol_row.addWidget(self._volume)
        col.addLayout(vol_row)

        outer.addWidget(center, alignment=Qt.AlignmentFlag.AlignHCenter)
        outer.addStretch()

        self._playing = True

    def _toggle_play(self):
        self._playing = not self._playing
        self._btn_play.setText("⏸" if self._playing else "▶")
