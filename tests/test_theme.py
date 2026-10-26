"""Contrast checks run without PySide6 (GUI visual checks still require a computer)."""
from batchrename.theme import (TEXT, MUTED, SURFACE, CANVAS, BLUE, BLUE_HOVER,
                               SELECTION, DISABLED_BG, DISABLED_TEXT, STYLESHEET)


def _luminance(hex_color):
    numbers = [int(hex_color[i:i+2], 16) / 255 for i in (1, 3, 5)]
    transformed = [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in numbers]
    return sum(x * w for x, w in zip(transformed, (0.2126, 0.7152, 0.0722)))


def _contrast(foreground, background):
    dark, light = sorted((_luminance(foreground), _luminance(background)))
    return (light + 0.05) / (dark + 0.05)


def test_light_theme_text_meets_contrast():
    for foreground, background in [
        (TEXT, SURFACE), (TEXT, SELECTION), (MUTED, CANVAS),
        (DISABLED_TEXT, DISABLED_BG), ("#FFFFFF", BLUE),
        ("#FFFFFF", BLUE_HOVER), ("#116A3A", SELECTION),
    ]:
        assert _contrast(foreground, background) >= 4.5, (foreground, background)


def test_key_controls_have_explicit_color_rules():
    for selector in ["QPushButton", "QPushButton#primary", "QPushButton:disabled",
                     "QLineEdit", "QComboBox", "QTableView", "QTableWidget",
                     "QTabBar::tab", "QMenu", "QStatusBar", "QToolTip"]:
        assert selector in STYLESHEET
