"""Страница настройки внешнего вида плеера: макет как на вкладке, ПКМ → «Изменить цвет» / фон страницы."""

from __future__ import annotations

import copy
import os
from typing import Callable, Optional

from PyQt6.QtCore import QPoint, QSize, Qt
from PyQt6.QtGui import QColor, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QScrollArea,
    QSlider,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui import i18n, player_appearance_settings
from ui.cover_art import CoverArtWidget
from ui.interactive_fx import StatefulIconButton
from ui.widgets.svg_seek_slider import SvgSeekSlider

_ICONS_DIR = os.path.join(os.path.dirname(__file__), "..", "icons")


class _PreviewBackgroundWidget(QWidget):
    """Editor preview background: same behavior as the real player page."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._color = QColor(0, 0, 0, 0)
        self._pixmap = QPixmap()

    def apply_state(self, state) -> None:
        self._pixmap = QPixmap()
        if state.page_mode == "default":
            self._color = QColor(0, 0, 0, 0)
            self.update()
            return
        rgba = state.page_color_rgba
        self._color = QColor(rgba[0], rgba[1], rgba[2], rgba[3])
        if state.page_mode == "image":
            path = (state.page_image_path or "").strip()
            if path and os.path.isfile(path):
                pm = QPixmap(path)
                if not pm.isNull():
                    self._pixmap = pm
        self.update()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        p = QPainter(self)
        if not self._pixmap.isNull():
            scaled = self._pixmap.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = int((self.width() - scaled.width()) / 2)
            y = int((self.height() - scaled.height()) / 2)
            p.drawPixmap(x, y, scaled)
        elif self._color.alpha() > 0:
            p.fillRect(self.rect(), self._color)
        p.end()


class PlayerAppearancePage(QWidget):
    def __init__(
        self,
        on_back: Callable[[], None],
        on_applied: Callable[[], None],
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("playerAppearancePage")
        self._on_back = on_back
        self._on_applied = on_applied
        self._draft = player_appearance_settings.defaults()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 12, 20, 12)
        outer.setSpacing(8)

        nav = QHBoxLayout()
        self._btn_back = QPushButton(i18n.tr("← назад"))
        self._btn_back.setObjectName("btnNav")
        self._btn_back.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_back.clicked.connect(self._on_back)
        nav.addWidget(self._btn_back, 0, Qt.AlignmentFlag.AlignLeft)
        title = QLabel(i18n.tr("Оформление плеера"))
        title.setObjectName("playerAppearanceTitle")
        nav.addWidget(title, 1, Qt.AlignmentFlag.AlignCenter)
        self._btn_thumb = QPushButton(i18n.tr("SVG бегунка…"))
        self._btn_thumb.setObjectName("playerAppearanceToolBtn")
        self._btn_thumb.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_thumb.clicked.connect(self._pick_thumb_svg)
        nav.addWidget(self._btn_thumb, 0, Qt.AlignmentFlag.AlignRight)
        outer.addLayout(nav)

        trans_row = QHBoxLayout()
        trans_row.setSpacing(8)
        self._page_bg_mode = QComboBox()
        self._page_bg_mode.setObjectName("playerPageBgMode")
        self._page_bg_mode.addItem(i18n.tr("Как в приложении (ambient)"), "default")
        self._page_bg_mode.addItem(i18n.tr("Свой цвет"), "color")
        self._page_bg_mode.addItem(i18n.tr("Своё изображение"), "image")
        self._page_bg_mode.currentIndexChanged.connect(self._on_page_bg_mode_changed)
        bg_lbl = QLabel(i18n.tr("Фон за плеером:"))
        bg_lbl.setObjectName("playerAppearanceControlLabel")
        trans_row.addWidget(bg_lbl)
        trans_row.addWidget(self._page_bg_mode)
        self._btn_page_image = QPushButton(i18n.tr("Загрузить картинку…"))
        self._btn_page_image.setObjectName("playerAppearanceToolBtn")
        self._btn_page_image.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_page_image.clicked.connect(self._pick_page_image)
        trans_row.addWidget(self._btn_page_image)
        self._page_image_lbl = QLabel("")
        self._page_image_lbl.setObjectName("playerAppearanceFileLabel")
        self._page_image_lbl.setMinimumWidth(0)
        self._page_image_lbl.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        trans_row.addWidget(self._page_image_lbl, stretch=1)
        outer.addLayout(trans_row)

        check_row = QHBoxLayout()
        check_row.setSpacing(12)
        check_row.addStretch()
        self._chk_left_transparent = QCheckBox(i18n.tr("Прозрачная левая карточка"))
        self._chk_right_transparent = QCheckBox(i18n.tr("Прозрачная правая карточка"))
        self._chk_left_transparent.setObjectName("playerAppearanceCheck")
        self._chk_right_transparent.setObjectName("playerAppearanceCheck")
        self._chk_left_transparent.toggled.connect(self._on_left_transparent_toggled)
        self._chk_right_transparent.toggled.connect(self._on_right_transparent_toggled)
        check_row.addWidget(self._chk_left_transparent)
        check_row.addWidget(self._chk_right_transparent)
        outer.addLayout(check_row)

        self._preview_root = _PreviewBackgroundWidget()
        self._preview_root.setObjectName("playerPagePreview")
        self._preview_root.setMinimumHeight(0)
        self._preview_root.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self._preview_root.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._preview_root.customContextMenuRequested.connect(self._on_preview_root_menu)

        pv = QHBoxLayout(self._preview_root)
        pv.setContentsMargins(12, 10, 12, 10)
        pv.setSpacing(12)

        self._left_prev = QFrame()
        self._left_prev.setObjectName("playerLeftCardPreview")
        self._left_prev.setMinimumWidth(180)
        self._left_prev.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self._wire_zone_menu(self._left_prev, "left")

        lv = QVBoxLayout(self._left_prev)
        lv.setContentsMargins(0, 0, 0, 0)
        lv.setSpacing(0)

        art = CoverArtWidget(
            radius=22,
            border_width=3,
            border_color=QColor(49, 41, 56),
            fill_color=QColor(216, 228, 236),
            mask_color=QColor("#D4D4A8"),
            placeholder_text="♪",
            placeholder_color=QColor(0, 51, 102),
            placeholder_px=32,
            top_align_square=True,
        )
        art.setObjectName("playerArtPanel")
        art.setMinimumSize(96, 96)
        art.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._wire_zone_menu(art, "left")
        lv.addWidget(art)

        band = QFrame()
        band.setObjectName("playerTrackBandPreview")
        self._wire_zone_menu(band, "left")
        bl = QVBoxLayout(band)
        bl.setContentsMargins(14, 10, 14, 10)
        lbl_trek = QLabel(i18n.tr("ТРЕК"))
        lbl_trek.setObjectName("playerTrekLabel")
        bl.addWidget(lbl_trek)
        title_prev = QLabel("—")
        title_prev.setObjectName("playerNowTitle")
        bl.addWidget(title_prev)
        lv.addWidget(band)

        ctrl = QWidget()
        ctrl.setObjectName("playerCtrlBlockPreview")
        self._wire_zone_menu(ctrl, "left")
        cvl = QVBoxLayout(ctrl)
        cvl.setContentsMargins(16, 14, 16, 16)
        cvl.setSpacing(12)

        self._mock_seek = SvgSeekSlider(compact=False)
        self._mock_seek.setObjectName("playerProgressSvg")
        self._mock_seek.setMinimumHeight(22)
        self._mock_seek.setRange(0, 1000)
        self._mock_seek.setValue(400)
        self._wire_zone_menu(self._mock_seek, "seek")

        times = QHBoxLayout()
        te = QLabel("0:00")
        te.setObjectName("playerTimeElapsed")
        tt = QLabel("0:00")
        tt.setObjectName("playerTimeRemain")
        times.addWidget(te)
        times.addStretch()
        times.addWidget(tt)
        cvl.addWidget(self._mock_seek)
        cvl.addLayout(times)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(18)
        btn_row.addStretch()
        for obj, ic in (
            ("playerBtnPrev", "player_prev.svg"),
            ("playerBtnPlayCircle", "player_play.svg"),
            ("playerBtnNext", "player_next.svg"),
        ):
            b = QPushButton()
            b.setObjectName(obj)
            b.setIcon(QIcon(os.path.join(_ICONS_DIR, ic)))
            is_play = "play" in ic
            b.setIconSize(QSize(32, 32) if is_play else QSize(28, 28))
            b.setFlat(True)
            b.setFixedSize(52 if is_play else 44, 52 if is_play else 44)
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            b.setCursor(Qt.CursorShape.ArrowCursor)
            self._wire_zone_menu(b, "left")
            btn_row.addWidget(b)
        btn_row.addStretch()
        cvl.addLayout(btn_row)

        vol_row = QHBoxLayout()
        vol_ic = QPushButton()
        vol_ic.setObjectName("playerVolumeIcon")
        vol_ic.setIcon(QIcon(os.path.join(_ICONS_DIR, "player_volume.svg")))
        vol_ic.setIconSize(QSize(22, 22))
        vol_ic.setFlat(True)
        vol_ic.setFixedSize(28, 28)
        vol_ic.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        vol_ic.setCursor(Qt.CursorShape.ArrowCursor)
        self._wire_zone_menu(vol_ic, "left")
        vol_sl = QSlider(Qt.Orientation.Horizontal)
        vol_sl.setObjectName("playerVolume")
        vol_sl.setRange(0, 100)
        vol_sl.setValue(70)
        vol_sl.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._wire_zone_menu(vol_sl, "volume")
        eq_btn = QPushButton()
        eq_btn.setObjectName("playerEqBtn")
        eq_btn.setIcon(QIcon(os.path.join(_ICONS_DIR, "player_equalizer.svg")))
        eq_btn.setIconSize(QSize(22, 22))
        eq_btn.setFlat(True)
        eq_btn.setFixedSize(28, 28)
        eq_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        eq_btn.setCursor(Qt.CursorShape.ArrowCursor)
        self._wire_zone_menu(eq_btn, "left")
        vol_row.addWidget(vol_ic)
        vol_row.addWidget(vol_sl, 1)
        vol_row.addWidget(eq_btn)
        cvl.addLayout(vol_row)

        lv.addWidget(ctrl, 0)
        pv.addWidget(self._left_prev, 2)

        self._right_prev = QFrame()
        self._right_prev.setObjectName("playerRightCardPreview")
        self._right_prev.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self._wire_zone_menu(self._right_prev, "right")

        rv = QVBoxLayout(self._right_prev)
        rv.setContentsMargins(0, 0, 0, 0)
        rv.setSpacing(0)

        tab_header = QFrame()
        tab_header.setObjectName("playerAlbumTabPreview")
        self._wire_zone_menu(tab_header, "right")
        th = QHBoxLayout(tab_header)
        th.setContentsMargins(20, 12, 20, 10)
        album_title = QLabel(i18n.tr("ИМЯ АЛЬБОМА"))
        album_title.setObjectName("playerAlbumTitle")
        th.addWidget(album_title)
        th.addStretch()
        rv.addWidget(tab_header)

        info = QFrame()
        info.setObjectName("playerTrackInfoPanelPreview")
        self._wire_zone_menu(info, "right")
        il = QVBoxLayout(info)
        il.setContentsMargins(16, 10, 16, 12)
        info_title = QLabel(i18n.tr("превью текста"))
        info_title.setObjectName("playerInfoTitleLine")
        il.addWidget(info_title)
        rv.addWidget(info)

        tools = QHBoxLayout()
        tools.setSpacing(10)
        like_btn = StatefulIconButton(
            os.path.join(_ICONS_DIR, "player_like.svg"),
            checked_icon_path=os.path.join(_ICONS_DIR, "player_like_filled.svg"),
            base_color="#312938",
            hover_color="#A14016",
            pressed_color="#CB883A",
            checked_color="#CB883A",
            parent=self,
        )
        like_btn.setObjectName("playerLikeBtn")
        like_btn.setCheckable(True)
        like_btn.setFixedSize(40, 36)
        like_btn.setIconSize(QSize(22, 22))
        like_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        like_btn.setCursor(Qt.CursorShape.ArrowCursor)
        self._wire_zone_menu(like_btn, "right")
        tools.addWidget(like_btn)

        review_btn = StatefulIconButton(
            os.path.join(_ICONS_DIR, "player_review_mono.svg"),
            base_color="#312938",
            hover_color="#004766",
            pressed_color="#2A7A8C",
            checked_color="#2A7A8C",
            pulse_on_toggle=False,
            parent=self,
        )
        review_btn.setObjectName("playerReviewBtn")
        review_btn.setFixedSize(40, 36)
        review_btn.setIconSize(QSize(22, 22))
        review_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        review_btn.setCursor(Qt.CursorShape.ArrowCursor)
        self._wire_zone_menu(review_btn, "right")
        tools.addWidget(review_btn)
        tools.addStretch()
        il.addLayout(tools)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setObjectName("playerAlbumScrollPreview")
        scroll.setStyleSheet("background: transparent;")
        scroll.viewport().setAutoFillBackground(False)
        self._wire_zone_menu(scroll, "right")
        list_host = QWidget()
        list_host.setStyleSheet("background: transparent;")
        list_lay = QVBoxLayout(list_host)
        list_lay.setContentsMargins(12, 8, 12, 12)
        list_lay.setSpacing(4)
        self._wire_zone_menu(list_host, "right")
        row1 = QFrame()
        row1.setObjectName("playerTrackRowPreview")
        self._wire_zone_menu(row1, "right")
        r1 = QHBoxLayout(row1)
        r1.setContentsMargins(10, 8, 14, 8)
        track_lbl = QLabel(i18n.tr("трек"))
        track_lbl.setObjectName("playerTrackTitle")
        r1.addWidget(track_lbl)
        list_lay.addWidget(row1)
        row2 = QFrame()
        row2.setObjectName("playerTrackRowActivePreview")
        self._wire_zone_menu(row2, "right")
        r2 = QHBoxLayout(row2)
        r2.setContentsMargins(10, 8, 14, 8)
        active_lbl = QLabel(i18n.tr("активный трек"))
        active_lbl.setObjectName("playerTrackTitle")
        r2.addWidget(active_lbl)
        list_lay.addWidget(row2)
        list_lay.addStretch()
        scroll.setWidget(list_host)
        rv.addWidget(scroll, 1)

        pv.addWidget(self._right_prev, 5)

        outer.addWidget(self._preview_root, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._btn_save = QPushButton(i18n.tr("Сохранить"))
        self._btn_save.setObjectName("playerAppearanceActionBtn")
        self._btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_save.clicked.connect(self._on_save)
        self._btn_cancel = QPushButton(i18n.tr("Отмена"))
        self._btn_cancel.setObjectName("playerAppearanceActionBtn")
        self._btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_cancel.clicked.connect(self._on_cancel)
        self._btn_default = QPushButton(i18n.tr("По умолчанию"))
        self._btn_default.setObjectName("playerAppearanceActionBtn")
        self._btn_default.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_default.clicked.connect(self._on_restore_defaults)
        btn_row.addWidget(self._btn_save)
        btn_row.addWidget(self._btn_cancel)
        btn_row.addWidget(self._btn_default)
        outer.addLayout(btn_row)
        self._sync_preview_constraints()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._sync_preview_constraints()

    def _sync_preview_constraints(self) -> None:
        if not hasattr(self, "_preview_root") or not hasattr(self, "_left_prev"):
            return
        h = self._preview_root.height()
        if h <= 0:
            return
        self._left_prev.setMaximumWidth(max(180, min(680, h - 220)))

    def _on_preview_root_menu(self, pos: QPoint) -> None:
        """ПКМ по пустому месту между карточками / полям — фон страницы за плеером."""
        if self._preview_root.childAt(pos) is not None:
            return
        self._page_background_menu_at(self._preview_root.mapToGlobal(pos))

    def _wire_zone_menu(self, w: QWidget, zone: str) -> None:
        w.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        w.customContextMenuRequested.connect(
            lambda pos, z=zone, wid=w: self._open_zone_menu(wid, pos, z)
        )

    def _open_zone_menu(self, w: QWidget, pos: QPoint, zone: str) -> None:
        menu = QMenu(self)
        if zone == "seek":
            a_g = menu.addAction(i18n.tr("Цвет подложки дорожки"))
            a_f = menu.addAction(i18n.tr("Цвет заполнения"))
            act = menu.exec(w.mapToGlobal(pos))
            if act == a_g:
                self._edit_progress_groove()
            elif act == a_f:
                self._edit_progress_filled()
            return
        if zone == "volume":
            a_g = menu.addAction(i18n.tr("Цвет подложки громкости"))
            a_f = menu.addAction(i18n.tr("Цвет заполнения громкости"))
            a_hf = menu.addAction(i18n.tr("Цвет бегунка громкости"))
            a_hb = menu.addAction(i18n.tr("Обводка бегунка громкости"))
            act = menu.exec(w.mapToGlobal(pos))
            if act == a_g:
                self._edit_volume_groove()
            elif act == a_f:
                self._edit_volume_filled()
            elif act == a_hf:
                self._edit_volume_handle_fill()
            elif act == a_hb:
                self._edit_volume_handle_border()
            return
        act = menu.addAction(i18n.tr("Изменить цвет"))
        chosen = menu.exec(w.mapToGlobal(pos))
        if chosen != act:
            return
        if zone == "left":
            self._edit_left_card()
        elif zone == "right":
            self._edit_right_card()

    def _page_background_menu_at(self, global_pos: QPoint) -> None:
        m = QMenu(self)
        a0 = m.addAction(i18n.tr("Стандартный фон (как в приложении)"))
        a1 = m.addAction(i18n.tr("Цвет фона…"))
        a2 = m.addAction(i18n.tr("Фоновое изображение…"))
        chosen = m.exec(global_pos)
        if chosen is None:
            return
        if chosen == a0:
            self._draft.page_mode = "default"
            self._refresh_preview()
        elif chosen == a1:
            t = self._pick_color(
                self._draft.page_color_rgba,
                i18n.tr("Цвет фона страницы"),
            )
            if t is not None:
                self._draft.page_mode = "color"
                self._draft.page_color_rgba = t
                self._refresh_preview()
        elif chosen == a2:
            path, _ = QFileDialog.getOpenFileName(
                self,
                i18n.tr("Фоновое изображение"),
                "",
                i18n.tr("Изображения (*.png *.jpg *.jpeg *.webp *.bmp);;Все файлы (*.*)"),
            )
            if path:
                self._draft.page_mode = "image"
                self._draft.page_image_path = path
                self._refresh_preview()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._draft = copy.deepcopy(player_appearance_settings.load())
        self._refresh_preview()

    def _refresh_preview(self) -> None:
        s = self._draft
        self._sync_page_bg_combo()
        self._sync_page_image_widgets()
        self._sync_transparency_checks()
        self._preview_root.apply_state(s)
        self._preview_root.setStyleSheet(player_appearance_settings.editor_preview_style_sheet(s))
        self._mock_seek.set_thumb_svg_path(player_appearance_settings.resolved_thumb_svg_path(s))
        groove_border = QColor(49, 41, 56)
        self._mock_seek.apply_colors(
            player_appearance_settings.qcolor_tuple(s.progress_groove_rgba),
            player_appearance_settings.qcolor_tuple(s.progress_filled_rgba),
            groove_border,
            player_appearance_settings.qcolor_tuple(s.progress_thumb_fill_rgba),
            player_appearance_settings.qcolor_tuple(s.progress_thumb_border_rgba),
        )

    def _sync_page_bg_combo(self) -> None:
        mode = self._draft.page_mode
        idx = self._page_bg_mode.findData(mode)
        if idx < 0:
            idx = 0
        self._page_bg_mode.blockSignals(True)
        self._page_bg_mode.setCurrentIndex(idx)
        self._page_bg_mode.blockSignals(False)

    def _on_page_bg_mode_changed(self, index: int) -> None:
        mode = self._page_bg_mode.itemData(index)
        if mode is None:
            return
        self._draft.page_mode = mode
        self._refresh_preview()

    def _sync_page_image_widgets(self) -> None:
        path = (self._draft.page_image_path or "").strip()
        is_image = self._draft.page_mode == "image"
        self._btn_page_image.setEnabled(True)
        if not is_image:
            text = ""
        elif not path:
            text = i18n.tr("Картинка не выбрана")
        elif os.path.isfile(path):
            text = os.path.basename(path)
        else:
            text = i18n.tr("Файл не найден:") + f" {os.path.basename(path)}"
        self._page_image_lbl.setText(text)

    def _pick_page_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            i18n.tr("Фоновое изображение"),
            "",
            i18n.tr("Изображения (*.png *.jpg *.jpeg *.webp *.bmp);;Все файлы (*.*)"),
        )
        if not path:
            if self._draft.page_mode != "image":
                self._draft.page_mode = "image"
                self._sync_page_bg_combo()
                self._refresh_preview()
            return
        self._draft.page_mode = "image"
        self._draft.page_image_path = path
        self._sync_page_bg_combo()
        self._refresh_preview()

    def _sync_transparency_checks(self) -> None:
        d = self._draft
        for cb, cond in (
            (self._chk_left_transparent, d.left_card_rgba[3] == 0),
            (self._chk_right_transparent, d.right_card_rgba[3] == 0),
        ):
            cb.blockSignals(True)
            cb.setChecked(cond)
            cb.blockSignals(False)

    def _on_left_transparent_toggled(self, checked: bool) -> None:
        r, g, b, _ = self._draft.left_card_rgba
        self._draft.left_card_rgba = (r, g, b, 0 if checked else 255)
        self._refresh_preview()

    def _on_right_transparent_toggled(self, checked: bool) -> None:
        r, g, b, _ = self._draft.right_card_rgba
        self._draft.right_card_rgba = (r, g, b, 0 if checked else 255)
        self._refresh_preview()

    def _pick_color(
        self,
        initial: tuple[int, int, int, int],
        title: str,
    ) -> Optional[tuple[int, int, int, int]]:
        c = QColor(initial[0], initial[1], initial[2], initial[3])
        dlg = QColorDialog(self)
        dlg.setOption(QColorDialog.ColorDialogOption.ShowAlphaChannel, True)
        dlg.setWindowTitle(title)
        dlg.setCurrentColor(c)
        if dlg.exec() != QColorDialog.DialogCode.Accepted:
            return None
        out = dlg.selectedColor()
        return out.red(), out.green(), out.blue(), out.alpha()

    def _edit_left_card(self) -> None:
        t = self._pick_color(
            self._draft.left_card_rgba,
            i18n.tr("Цвет левой карточки"),
        )
        if t is not None:
            self._draft.left_card_rgba = t
            self._refresh_preview()

    def _edit_right_card(self) -> None:
        t = self._pick_color(
            self._draft.right_card_rgba,
            i18n.tr("Цвет правой карточки"),
        )
        if t is not None:
            self._draft.right_card_rgba = t
            self._refresh_preview()

    def _edit_progress_groove(self) -> None:
        t = self._pick_color(
            self._draft.progress_groove_rgba,
            i18n.tr("Цвет подложки дорожки"),
        )
        if t is not None:
            self._draft.progress_groove_rgba = t
            self._refresh_preview()

    def _edit_progress_filled(self) -> None:
        t = self._pick_color(
            self._draft.progress_filled_rgba,
            i18n.tr("Цвет заполнения дорожки"),
        )
        if t is not None:
            self._draft.progress_filled_rgba = t
            self._refresh_preview()

    def _edit_volume_groove(self) -> None:
        t = self._pick_color(
            self._draft.volume_groove_rgba,
            i18n.tr("Цвет подложки громкости"),
        )
        if t is not None:
            self._draft.volume_groove_rgba = t
            self._refresh_preview()

    def _edit_volume_filled(self) -> None:
        t = self._pick_color(
            self._draft.volume_filled_rgba,
            i18n.tr("Цвет заполнения громкости"),
        )
        if t is not None:
            self._draft.volume_filled_rgba = t
            self._refresh_preview()

    def _edit_volume_handle_fill(self) -> None:
        t = self._pick_color(
            self._draft.volume_handle_fill_rgba,
            i18n.tr("Цвет бегунка громкости"),
        )
        if t is not None:
            self._draft.volume_handle_fill_rgba = t
            self._refresh_preview()

    def _edit_volume_handle_border(self) -> None:
        t = self._pick_color(
            self._draft.volume_handle_border_rgba,
            i18n.tr("Обводка бегунка громкости"),
        )
        if t is not None:
            self._draft.volume_handle_border_rgba = t
            self._refresh_preview()

    def _pick_thumb_svg(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            i18n.tr("SVG бегунка"),
            "",
            i18n.tr("Векторные изображения (*.svg);;Все файлы (*.*)"),
        )
        if path:
            self._draft.thumb_svg_path = path
            self._refresh_preview()

    def _on_save(self) -> None:
        player_appearance_settings.save(self._draft)
        self._on_applied()

    def _on_cancel(self) -> None:
        self._draft = copy.deepcopy(player_appearance_settings.load())
        self._refresh_preview()

    def _on_restore_defaults(self) -> None:
        self._draft = player_appearance_settings.defaults()
        self._refresh_preview()
