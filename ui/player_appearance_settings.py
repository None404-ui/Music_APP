"""Внешний вид плеера: QSettings (цвета карточек, фон страницы, SVG бегунка, мини-плеер)."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from typing import Any, Literal

from PyQt6.QtCore import QSettings
from PyQt6.QtGui import QColor

_ORG = "CRATES"
_APP = "CRATES"
_JSON_KEY = "player_appearance/state_json"
_scope_prefix = ""

PageMode = Literal["default", "color", "image"]


def _s() -> QSettings:
    return QSettings(QSettings.Scope.UserScope, _ORG, _APP)


def set_user_scope(user_id: int | None) -> None:
    global _scope_prefix
    _scope_prefix = f"users/{int(user_id)}/" if user_id else ""


def _key(name: str) -> str:
    return f"{_scope_prefix}{name}"


def _rgba(c: QColor) -> tuple[int, int, int, int]:
    return c.red(), c.green(), c.blue(), c.alpha()


def _qcolor(t: tuple[int, int, int, int]) -> QColor:
    return QColor(t[0], t[1], t[2], t[3])


@dataclass
class PlayerAppearanceState:
    """Значения по умолчанию совпадают с ui/styles/player.qss (основной плеер и мини-плеер)."""

    left_card_rgba: tuple[int, int, int, int] = (212, 207, 160, 255)  # #D4CFA0
    right_card_rgba: tuple[int, int, int, int] = (212, 207, 160, 255)
    card_border_rgba: tuple[int, int, int, int] = (137, 161, 148, 140)  # 0.55 * 255
    page_mode: PageMode = "default"
    page_color_rgba: tuple[int, int, int, int] = (207, 200, 154, 224)  # rgba(..., 0.88)
    page_image_path: str = ""
    thumb_svg_path: str = ""
    progress_groove_rgba: tuple[int, int, int, int] = (207, 200, 154, 255)  # #CFC89A
    progress_filled_rgba: tuple[int, int, int, int] = (161, 64, 22, 255)  # #A14016
    progress_thumb_fill_rgba: tuple[int, int, int, int] = (49, 41, 56, 255)  # #312938
    progress_thumb_border_rgba: tuple[int, int, int, int] = (203, 136, 58, 255)  # #CB883A
    mini_bar_bg_rgba: tuple[int, int, int, int] = (36, 33, 24, 239)  # 0.94
    mini_bar_border_rgba: tuple[int, int, int, int] = (203, 136, 58, 140)  # 0.55
    volume_groove_rgba: tuple[int, int, int, int] = (207, 200, 154, 255)  # #CFC89A
    volume_filled_rgba: tuple[int, int, int, int] = (137, 161, 148, 255)  # #89A194 sub-page
    volume_handle_fill_rgba: tuple[int, int, int, int] = (49, 41, 56, 255)  # #312938
    volume_handle_border_rgba: tuple[int, int, int, int] = (203, 136, 58, 255)  # #CB883A

    def to_json_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["page_mode"] = self.page_mode
        return d

    @classmethod
    def from_json_dict(cls, d: dict[str, Any]) -> PlayerAppearanceState:
        base = defaults()
        if not d:
            return base
        try:
            pm = d.get("page_mode", base.page_mode)
            if pm == "transparent":
                pm = "default"
            elif pm not in ("default", "color", "image"):
                pm = "default"
            return cls(
                left_card_rgba=tuple(d.get("left_card_rgba", base.left_card_rgba)),  # type: ignore[arg-type]
                right_card_rgba=tuple(d.get("right_card_rgba", base.right_card_rgba)),  # type: ignore[arg-type]
                card_border_rgba=tuple(d.get("card_border_rgba", base.card_border_rgba)),  # type: ignore[arg-type]
                page_mode=pm,
                page_color_rgba=tuple(d.get("page_color_rgba", base.page_color_rgba)),  # type: ignore[arg-type]
                page_image_path=str(d.get("page_image_path", "") or ""),
                thumb_svg_path=str(d.get("thumb_svg_path", "") or ""),
                progress_groove_rgba=tuple(
                    d.get("progress_groove_rgba", base.progress_groove_rgba)
                ),  # type: ignore[arg-type]
                progress_filled_rgba=tuple(
                    d.get("progress_filled_rgba", base.progress_filled_rgba)
                ),  # type: ignore[arg-type]
                progress_thumb_fill_rgba=tuple(
                    d.get("progress_thumb_fill_rgba", base.progress_thumb_fill_rgba)
                ),  # type: ignore[arg-type]
                progress_thumb_border_rgba=tuple(
                    d.get("progress_thumb_border_rgba", base.progress_thumb_border_rgba)
                ),  # type: ignore[arg-type]
                mini_bar_bg_rgba=tuple(d.get("mini_bar_bg_rgba", base.mini_bar_bg_rgba)),  # type: ignore[arg-type]
                mini_bar_border_rgba=tuple(
                    d.get("mini_bar_border_rgba", base.mini_bar_border_rgba)
                ),  # type: ignore[arg-type]
                volume_groove_rgba=tuple(
                    d.get("volume_groove_rgba", base.volume_groove_rgba)
                ),  # type: ignore[arg-type]
                volume_filled_rgba=tuple(
                    d.get("volume_filled_rgba", base.volume_filled_rgba)
                ),  # type: ignore[arg-type]
                volume_handle_fill_rgba=tuple(
                    d.get("volume_handle_fill_rgba", base.volume_handle_fill_rgba)
                ),  # type: ignore[arg-type]
                volume_handle_border_rgba=tuple(
                    d.get("volume_handle_border_rgba", base.volume_handle_border_rgba)
                ),  # type: ignore[arg-type]
            )
        except (TypeError, ValueError, KeyError):
            return defaults()


def defaults() -> PlayerAppearanceState:
    return PlayerAppearanceState()


def load() -> PlayerAppearanceState:
    raw = _s().value(_key(_JSON_KEY), "", str)
    if not (raw or "").strip():
        return defaults()
    try:
        data = json.loads(raw)
        if not isinstance(data, dict):
            return defaults()
        return PlayerAppearanceState.from_json_dict(data)
    except json.JSONDecodeError:
        return defaults()


def save(state: PlayerAppearanceState) -> None:
    _s().setValue(_key(_JSON_KEY), json.dumps(state.to_json_dict(), ensure_ascii=False))


def color_css_rgba(t: tuple[int, int, int, int]) -> str:
    return f"rgba({t[0]}, {t[1]}, {t[2]}, {t[3] / 255.0:.4f})"


def qcolor_tuple(t: tuple[int, int, int, int]) -> QColor:
    return _qcolor(t)


def default_thumb_svg_path() -> str:
    return os.path.normpath(
        os.path.join(os.path.dirname(__file__), "icons", "player_progress_thumb.svg")
    )


def resolved_thumb_svg_path(state: PlayerAppearanceState) -> str | None:
    """Путь к SVG бегунка или None — рисовать встроенный прямоугольник."""
    p = (state.thumb_svg_path or "").strip()
    if not p:
        d = default_thumb_svg_path()
        return d if os.path.isfile(d) else None
    if os.path.isfile(p):
        return os.path.normpath(p)
    return None


def _ambient_like_preview_gradient_css() -> str:
    """Тот же характер фона, что у AmbientBackground (превью редактора)."""
    return (
        "background-color: #18121C;"
        "background-image: "
        "radial-gradient(circle at 22% 35%, rgba(255, 120, 40, 0.35) 0%, transparent 55%),"
        "radial-gradient(circle at 78% 28%, rgba(40, 200, 190, 0.28) 0%, transparent 50%),"
        "radial-gradient(circle at 55% 72%, rgba(60, 90, 220, 0.22) 0%, transparent 55%);"
    )


def preview_page_background_style(state: PlayerAppearanceState) -> str:
    """Фон превью: режим «как в приложении» — градиент ambient; иначе цвет или картинка."""
    if state.page_mode == "default":
        return _ambient_like_preview_gradient_css()
    return resolved_page_background_style(state)


def _preview_band_header_info(
    state: PlayerAppearanceState,
) -> tuple[str, str, str]:
    """Стили band/header/info для превью с учётом прозрачных карточек."""
    lc = _q_rgb(state.left_card_rgba)
    rc = _q_rgb(state.right_card_rgba)
    br = _q_rgb(state.card_border_rgba)
    if state.left_card_rgba[3] == 0:
        band_css = "background-color: rgba(0, 0, 0, 0);"
    else:
        band = lc.darker(108)
        band_css = f"background-color: {_hex_rgb(band)};"
    if state.right_card_rgba[3] == 0:
        header_css = "background-color: rgba(0, 0, 0, 0);"
        info_css = "background-color: rgba(0, 0, 0, 0); border: none;"
    else:
        header = rc.darker(105)
        info = QColor(rc)
        info.setAlpha(115)
        row_border = color_css_rgba(
            (br.red(), br.green(), br.blue(), min(255, int(br.alpha() * 0.65)))
        )
        header_css = f"background-color: {_hex_rgb(header)};"
        info_css = (
            f"background-color: {color_css_rgba((info.red(), info.green(), info.blue(), info.alpha()))}; "
            f"border-bottom: 1px solid {row_border};"
        )
    return band_css, header_css, info_css


def resolved_page_background_style(state: PlayerAppearanceState) -> str:
    """CSS fallback for color backgrounds. Images are painted by widgets."""
    if state.page_mode == "default":
        return "background-color: rgba(0, 0, 0, 0);"
    if state.page_mode == "image":
        img = (state.page_image_path or "").strip()
        if img and os.path.isfile(img):
            return "background-color: rgba(0, 0, 0, 0);"
        # файл пропал — подложка цвета страницы
        return f"background-color: {color_css_rgba(state.page_color_rgba)};"
    return f"background-color: {color_css_rgba(state.page_color_rgba)};"


def _card_style_for_object_id(oid: str, left: bool, state: PlayerAppearanceState) -> str:
    rgba = state.left_card_rgba if left else state.right_card_rgba
    br = state.card_border_rgba
    border = color_css_rgba(br)
    if rgba[3] == 0:
        border_soft = color_css_rgba(
            (br[0], br[1], br[2], min(255, max(40, br[3] // 2)))
        )
        return (
            f"QFrame#{oid} {{"
            "background-color: rgba(0, 0, 0, 0);"
            f"border-radius: 22px;"
            f"border: 2px solid {border_soft};"
            "}"
        )
    bg = color_css_rgba(rgba)
    return (
        f"QFrame#{oid} {{"
        f"background-color: {bg};"
        f"border-radius: 22px;"
        f"border: 2px solid {border};"
        "}"
    )


def card_style_fragment(
    left: bool,
    state: PlayerAppearanceState,
) -> str:
    oid = "playerLeftCard" if left else "playerRightCard"
    return _card_style_for_object_id(oid, left, state)


def _q_rgb(t: tuple[int, int, int, int]) -> QColor:
    return QColor(t[0], t[1], t[2], t[3])


def _hex_rgb(c: QColor) -> str:
    return c.name(QColor.NameFormat.HexRgb)


def inner_left_inset_fragment(state: PlayerAppearanceState) -> str:
    """Блок управления без собственного фона; полоса «ТРЕК» — оттенок от цвета левой карточки."""
    if state.left_card_rgba[3] == 0:
        return (
            "QWidget#playerCtrlBlock { background: transparent; }"
            "QFrame#playerTrackBand { background-color: rgba(0, 0, 0, 0); }"
        )
    lc = _q_rgb(state.left_card_rgba)
    band = lc.darker(108)
    return (
        "QWidget#playerCtrlBlock { background: transparent; }"
        f"QFrame#playerTrackBand {{ background-color: {_hex_rgb(band)}; }}"
    )


def inner_right_inset_fragment(state: PlayerAppearanceState) -> str:
    """Шапка и панель инфо справа — из оттенков цвета правой карточки (как в player.qss, но от выбранного цвета)."""
    if state.right_card_rgba[3] == 0:
        return (
            "QFrame#playerAlbumTab { background-color: rgba(0, 0, 0, 0); }"
            "QFrame#playerTrackInfoPanel { background-color: rgba(0, 0, 0, 0); border: none; }"
            "QFrame#playerTrackRow { background-color: rgba(0, 0, 0, 0); border: 1px solid rgba(137, 161, 148, 0.35); border-radius: 8px; }"
            "QFrame#playerTrackRowActive { background-color: rgba(203, 136, 58, 0.15); border: 1px solid #CB883A; border-radius: 8px; }"
            "QScrollArea#playerAlbumScroll { background: transparent; border: none; }"
        )
    rc = _q_rgb(state.right_card_rgba)
    br = _q_rgb(state.card_border_rgba)
    header = rc.darker(105)
    info = QColor(rc)
    info.setAlpha(115)
    row_a = QColor(rc)
    row_a.setAlpha(89)
    row_border = color_css_rgba(
        (br.red(), br.green(), br.blue(), min(255, int(br.alpha() * 0.65)))
    )
    active = QColor(203, 136, 58, 56)
    return (
        f"QFrame#playerAlbumTab {{ background-color: {_hex_rgb(header)}; }}"
        f"QFrame#playerTrackInfoPanel {{ background-color: {color_css_rgba((info.red(), info.green(), info.blue(), info.alpha()))}; border-bottom: 1px solid {row_border}; }}"
        f"QFrame#playerTrackRow {{ background-color: {color_css_rgba((row_a.red(), row_a.green(), row_a.blue(), row_a.alpha()))}; border-radius: 8px; border: 1px solid {row_border}; }}"
        f"QFrame#playerTrackRowActive {{ background-color: {color_css_rgba((active.red(), active.green(), active.blue(), active.alpha()))}; border-radius: 8px; border: 1px solid #CB883A; }}"
        "QScrollArea#playerAlbumScroll { background: transparent; border: none; }"
    )


def volume_slider_fragment(state: PlayerAppearanceState) -> str:
    """Стили QSlider#playerVolume (громкость)."""
    g = color_css_rgba(state.volume_groove_rgba)
    f = color_css_rgba(state.volume_filled_rgba)
    hf = color_css_rgba(state.volume_handle_fill_rgba)
    hb = color_css_rgba(state.volume_handle_border_rgba)
    border_dark = "#312938"
    return (
        "QSlider#playerVolume::groove:horizontal {"
        f"background-color: {g};"
        f"border: 2px solid {border_dark};"
        "height: 6px; border-radius: 0px; }"
        "QSlider#playerVolume::sub-page:horizontal {"
        f"background-color: {f};"
        f"border: 2px solid {border_dark};"
        "height: 6px; border-radius: 0px; }"
        "QSlider#playerVolume::add-page:horizontal {"
        f"background-color: {g};"
        f"border: 2px solid {border_dark};"
        "height: 6px; border-radius: 0px; }"
        "QSlider#playerVolume::handle:horizontal {"
        f"background-color: {hf};"
        f"border: 2px solid {hb};"
        "width: 12px; height: 14px; border-radius: 0px; margin: -6px 0; }"
        "QSlider#playerVolume::handle:horizontal:hover {"
        f"background-color: {hb};"
        f"border-color: {border_dark}; }}"
    )


def player_tab_widget_stylesheet(state: PlayerAppearanceState) -> str:
    """Плеер: фон страницы, карточки и внутренности."""
    return (
        "QWidget#playerPage { background-color: rgba(0, 0, 0, 0); }"
        + card_style_fragment(True, state)
        + card_style_fragment(False, state)
        + inner_left_inset_fragment(state)
        + inner_right_inset_fragment(state)
        + volume_slider_fragment(state)
    )


def ambient_player_fill_stylesheet(state: PlayerAppearanceState) -> str:
    """Полноэкранный слой над градиентным ambient: свой цвет или картинка. Режим default — без слоя."""
    if state.page_mode == "default":
        return ""
    body = resolved_page_background_style(state)
    return f"QWidget#ambientPlayerFill {{ {body} }}"


def player_tab_dynamic_stylesheet(state: PlayerAppearanceState) -> str:
    """Совместимость: то же, что player_tab_widget_stylesheet."""
    return player_tab_widget_stylesheet(state)


def editor_preview_style_sheet(state: PlayerAppearanceState) -> str:
    """Стили макета-превью: те же пропорции цветов, свои objectName."""
    band_css, header_css, info_inner = _preview_band_header_info(state)
    br = _q_rgb(state.card_border_rgba)
    rc = _q_rgb(state.right_card_rgba)
    row_border = color_css_rgba(
        (br.red(), br.green(), br.blue(), min(255, int(br.alpha() * 0.65)))
    )
    if state.right_card_rgba[3] == 0:
        row1 = (
            "background-color: rgba(0, 0, 0, 0); border: 1px solid rgba(137, 161, 148, 0.35); border-radius: 8px;"
        )
        row2 = (
            "background-color: rgba(203, 136, 58, 0.15); border: 1px solid #CB883A; border-radius: 8px;"
        )
    else:
        row_a = QColor(rc)
        row_a.setAlpha(89)
        active = QColor(203, 136, 58, 56)
        row1 = (
            f"background-color: {color_css_rgba((row_a.red(), row_a.green(), row_a.blue(), row_a.alpha()))}; "
            f"border-radius: 8px; border: 1px solid {row_border};"
        )
        row2 = (
            f"background-color: {color_css_rgba((active.red(), active.green(), active.blue(), active.alpha()))}; "
            "border-radius: 8px; border: 1px solid #CB883A;"
        )
    return (
        "QWidget#playerPagePreview { background-color: rgba(0, 0, 0, 0); }"
        + _card_style_for_object_id("playerLeftCardPreview", True, state)
        + _card_style_for_object_id("playerRightCardPreview", False, state)
        + "QWidget#playerCtrlBlockPreview { background: transparent; }"
        f"QFrame#playerTrackBandPreview {{ {band_css} border-bottom-left-radius: 20px; border-bottom-right-radius: 20px; }}"
        f"QFrame#playerAlbumTabPreview {{ {header_css} border-top-left-radius: 18px; border-top-right-radius: 18px; min-height: 40px; }}"
        f"QFrame#playerTrackInfoPanelPreview {{ {info_inner} }}"
        f"QFrame#playerTrackRowPreview {{ {row1} }}"
        f"QFrame#playerTrackRowActivePreview {{ {row2} }}"
        "QScrollArea#playerAlbumScrollPreview { background: transparent; border: none; }"
        "QFrame#playerRightCardPreview QScrollArea { border-bottom-left-radius: 18px; border-bottom-right-radius: 18px; }"
        "QScrollArea#playerAlbumScrollPreview > QWidget { background: transparent; }"
        "QScrollArea#playerAlbumScrollPreview > QWidget > QWidget { background: transparent; }"
        + volume_slider_fragment(state)
    )


def mini_bar_style_fragment(state: PlayerAppearanceState) -> str:
    bg = color_css_rgba(state.mini_bar_bg_rgba)
    br = color_css_rgba(state.mini_bar_border_rgba)
    return (
        "QFrame#miniPlayerBar {"
        f"background-color: {bg};"
        f"border: 2px solid {br};"
        "border-radius: 14px;"
        "}"
    )
