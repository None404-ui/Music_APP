"""Всплывающее окно графического эквалайзера."""

from __future__ import annotations

from typing import Callable, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from ui import i18n
from ui.audio_eq import BAND_CENTER_HZ, EQ_PRESET_GAINS_DB
from ui import equalizer_settings as eqs


def _hz_label(hz: float) -> str:
    if hz >= 1000:
        if hz == int(hz):
            return f"{int(hz // 1000)}k"
        return f"{hz / 1000:.1f}k".replace(".0k", "k")
    return str(int(hz))


class EqualizerPopup(QFrame):
    def __init__(
        self,
        parent: Optional[QWidget] = None,
        on_changed: Optional[Callable[[], None]] = None,
    ):
        super().__init__(parent, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setObjectName("playerPlaybackSettingsPopup")
        self._on_changed = on_changed
        self._preset_combo_block = False
        self._slider_block = False

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(10)

        cap = QLabel(i18n.tr("ЭКВАЛАЙЗЕР"))
        cap.setObjectName("playerPlaybackPopupTitle")
        root.addWidget(cap)

        preset_row = QHBoxLayout()
        preset_lab = QLabel(i18n.tr("Профиль"))
        preset_lab.setObjectName("playerPlaybackPopupLabel")
        self._preset_combo = QComboBox()
        self._preset_combo.setObjectName("settingsCombo")
        for key, label_key in (
            ("flat", "Плоский"),
            ("bass", "Усиление НЧ"),
            ("treble", "Усиление ВЧ"),
            ("rock", "Рок"),
            ("vocal", "Вокал"),
            ("electronic", "Электроника"),
            ("warm", "Тёплый"),
        ):
            self._preset_combo.addItem(i18n.tr(label_key), key)
        self._preset_combo.addItem(i18n.tr("Свой"), "custom")
        self._preset_combo.currentIndexChanged.connect(self._on_preset_index)
        preset_row.addWidget(preset_lab)
        preset_row.addWidget(self._preset_combo, stretch=1)
        root.addLayout(preset_row)

        grid = QGridLayout()
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(4)
        self._sliders: list[QSlider] = []
        for i, hz in enumerate(BAND_CENTER_HZ):
            col = QVBoxLayout()
            col.setSpacing(2)
            s = QSlider(Qt.Orientation.Vertical)
            s.setObjectName("eqBandSlider")
            s.setRange(-12, 12)
            s.setValue(0)
            s.setInvertedAppearance(True)
            s.setFixedHeight(110)
            s.setTickPosition(QSlider.TickPosition.TicksLeft)
            s.setSingleStep(1)
            s.valueChanged.connect(lambda _v, idx=i: self._on_slider_moved(idx))
            lab = QLabel(_hz_label(hz))
            lab.setObjectName("eqBandHzLabel")
            lab.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            col.addWidget(s, alignment=Qt.AlignmentFlag.AlignHCenter)
            col.addWidget(lab)
            w = QWidget()
            w.setLayout(col)
            grid.addWidget(w, 0, i)
            self._sliders.append(s)
        root.addLayout(grid)

        hint = QLabel(i18n.tr("Ползунки: −12…+12 дБ по полосам."))
        hint.setObjectName("settingsHint")
        hint.setWordWrap(True)
        root.addWidget(hint)

    def sync_from_storage(self) -> None:
        gains = eqs.band_gains_db()
        pid = eqs.preset_id()
        self._slider_block = True
        try:
            for i, sl in enumerate(self._sliders):
                sl.setValue(int(round(gains[i] if i < len(gains) else 0.0)))
        finally:
            self._slider_block = False

        self._preset_combo_block = True
        try:
            idx = self._preset_combo.findData(pid)
            if idx < 0:
                idx = self._preset_combo.findData("custom")
            self._preset_combo.setCurrentIndex(max(0, idx))
        finally:
            self._preset_combo_block = False

    def toggle_near(self, anchor: QWidget) -> None:
        if self.isVisible():
            self.hide()
            return
        self.sync_from_storage()
        self.adjustSize()
        sz = self.sizeHint()
        # Левый нижний угол панели — над иконкой (слева от неё по X); панель уходит вверх и вправо от этой точки
        tl = anchor.mapToGlobal(anchor.rect().topLeft())
        gap = 6
        x = tl.x()
        y = tl.y() - gap - sz.height()
        ref = anchor.mapToGlobal(anchor.rect().center())
        screen = QApplication.screenAt(ref) or QApplication.primaryScreen()
        if screen is not None:
            geo = screen.availableGeometry()
            margin = 6
            x = min(max(geo.left() + margin, x), geo.right() - sz.width() - margin)
            y = min(max(geo.top() + margin, y), geo.bottom() - sz.height() - margin)
        else:
            x = max(8, x)
            y = max(8, y)
        self.move(int(x), int(y))
        self.show()
        self.raise_()

    def _emit_changed(self) -> None:
        if self._on_changed:
            self._on_changed()

    def _save_sliders_and_notify(self) -> None:
        gains = [float(s.value()) for s in self._sliders]
        eqs.set_band_gains_db(gains)
        self._emit_changed()

    def _on_slider_moved(self, _idx: int) -> None:
        if self._slider_block:
            return
        if not self._preset_combo_block:
            self._preset_combo_block = True
            try:
                ci = self._preset_combo.findData("custom")
                if ci >= 0:
                    self._preset_combo.setCurrentIndex(ci)
                eqs.set_preset_id("custom")
            finally:
                self._preset_combo_block = False
        self._save_sliders_and_notify()

    def _on_preset_index(self, index: int) -> None:
        if self._preset_combo_block:
            return
        key = self._preset_combo.itemData(index)
        if not isinstance(key, str):
            return
        if key == "custom":
            return
        tpl = EQ_PRESET_GAINS_DB.get(key)
        if tpl is None:
            return
        eqs.set_preset_id(key)
        self._slider_block = True
        try:
            for i, sl in enumerate(self._sliders):
                sl.setValue(int(round(tpl[i] if i < len(tpl) else 0.0)))
        finally:
            self._slider_block = False
        eqs.set_band_gains_db([float(s.value()) for s in self._sliders])
        self._emit_changed()
