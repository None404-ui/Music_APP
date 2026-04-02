"""
Пиксельный ретро-шрифт для UI.

Файл ui/fonts/RetroShift.ttf — это Press Start 2P (OFL), подключённый под ожидаемое
имя «RetroShift» в дизайне. При отсутствии файла используется моноширинный запасной вариант.
"""

import os

from PyQt6.QtGui import QFontDatabase


def register_retro_font() -> str:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(root, "ui", "fonts", "RetroShift.ttf")
    if not os.path.isfile(path):
        return "Courier New"
    fid = QFontDatabase.addApplicationFont(path)
    if fid < 0:
        return "Courier New"
    families = QFontDatabase.applicationFontFamilies(fid)
    return families[0] if families else "Courier New"


def inject_font_into_qss(qss: str, font_family: str) -> str:
    s = qss.replace(
        '"Segoe UI", "Courier New", monospace',
        f'"{font_family}", monospace',
    )
    s = s.replace('"Courier New", monospace', f'"{font_family}", monospace')
    s = s.replace('"Courier New"', f'"{font_family}"')
    return s
