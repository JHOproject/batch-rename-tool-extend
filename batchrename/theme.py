"""Fixed, readable light theme for Windows/macOS, including dark-mode systems.

The app must not inherit white text from a system dark palette while using
white widget backgrounds. The palette and widget stylesheet are set together.
"""
from __future__ import annotations

TEXT = "#17263D"
MUTED = "#42536C"
SURFACE = "#FFFFFF"
CANVAS = "#F4F7FB"
BLUE = "#2459C2"
BLUE_HOVER = "#174BA9"
SELECTION = "#DDEBFF"
DISABLED_BG = "#E6EBF2"
DISABLED_TEXT = "#576579"

STYLESHEET = f"""
QWidget {{
    color: {TEXT};
    font-family: 'PingFang SC', 'Microsoft YaHei', 'Noto Sans CJK SC', sans-serif;
    font-size: 13px;
}}
QMainWindow, QDialog, QWidget#mainRoot, QWidget#tabPage, QTabWidget::pane {{
    background-color: {CANVAS};
}}
QLabel {{ color: {TEXT}; background-color: transparent; }}
QLabel#title {{ color: #122440; font-size: 22px; font-weight: 700; }}
QLabel#subtitle {{ color: {MUTED}; }}
QGroupBox {{
    color: {TEXT};
    font-weight: 600;
    border: 1px solid #C9D5E5;
    border-radius: 8px;
    margin-top: 14px;
    padding: 15px 9px 10px 9px;
    background-color: {SURFACE};
}}
QGroupBox::title {{ color: {TEXT}; subcontrol-origin: margin; left: 12px; padding: 0 5px; }}
QPushButton {{
    color: {TEXT};
    background-color: {SURFACE};
    border: 1px solid #B9C8D9;
    border-radius: 6px;
    padding: 7px 11px;
    min-height: 19px;
}}
QPushButton:hover {{ color: #16375B; background-color: #E8F0FF; border-color: #7C9FD3; }}
QPushButton:pressed {{ color: {TEXT}; background-color: #CCDFFB; }}
QPushButton:disabled {{ color: {DISABLED_TEXT}; background-color: {DISABLED_BG}; border-color: #BEC8D6; }}
QPushButton#primary {{ color: #FFFFFF; background-color: {BLUE}; border-color: {BLUE}; font-weight: 700; }}
QPushButton#primary:hover {{ color: #FFFFFF; background-color: {BLUE_HOVER}; border-color: {BLUE_HOVER}; }}
QPushButton#primary:pressed {{ color: #FFFFFF; background-color: #123C8D; }}
QPushButton#primary:disabled {{ color: {DISABLED_TEXT}; background-color: {DISABLED_BG}; border-color: #BEC8D6; }}
QLineEdit, QComboBox, QSpinBox, QListWidget, QListView, QTreeView, QTableView, QTableWidget {{
    color: {TEXT};
    background-color: {SURFACE};
    selection-background-color: {SELECTION};
    selection-color: {TEXT};
    border: 1px solid #C6D2E2;
    border-radius: 5px;
    padding: 3px;
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{ border-color: #3671CD; }}
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled {{
    color: {DISABLED_TEXT}; background-color: {DISABLED_BG};
}}
QComboBox {{ padding-right: 18px; }}
QComboBox::drop-down {{ background-color: #EAF0FA; border-left: 1px solid #C6D2E2; width: 18px; }}
QComboBox QAbstractItemView {{
    color: {TEXT}; background-color: {SURFACE};
    selection-background-color: {SELECTION}; selection-color: {TEXT};
    border: 1px solid #C6D2E2;
}}
QTableView::item, QTableWidget::item, QListWidget::item, QListView::item, QTreeView::item {{
    color: {TEXT};
}}
QTableView::item:selected, QTableWidget::item:selected,
QListWidget::item:selected, QListView::item:selected, QTreeView::item:selected {{
    color: {TEXT}; background-color: {SELECTION};
}}
QTableView::item:alternate, QTableWidget::item:alternate {{ background: #F5F8FC; }}
QHeaderView::section {{
    color: {TEXT}; background-color: #E7EEF7;
    border: 0; border-right: 1px solid #C8D4E3;
    border-bottom: 1px solid #C8D4E3;
    padding: 5px 7px;
    font-weight: 600;
}}
QTableCornerButton::section {{ background-color: #E7EEF7; border: 1px solid #C8D4E3; }}
QTabWidget::pane {{ border: 1px solid #CAD6E7; background-color: {CANVAS}; }}
QTabBar::tab {{
    color: {MUTED}; background-color: #E7ECF4;
    padding: 11px 20px; border: 1px solid #C9D5E5;
    border-bottom: 0; margin-right: 2px;
}}
QTabBar::tab:hover {{ color: #164E9B; background-color: #E1EBFC; }}
QTabBar::tab:selected {{ color: #123F92; background-color: {SURFACE}; font-weight: 700; }}
QMenuBar {{ color: {TEXT}; background-color: #E9EEF5; }}
QMenuBar::item {{ color: {TEXT}; background: transparent; padding: 5px 10px; }}
QMenuBar::item:selected {{ color: {TEXT}; background-color: {SELECTION}; }}
QMenu {{ color: {TEXT}; background-color: {SURFACE}; border: 1px solid #C9D5E5; }}
QMenu::item {{ color: {TEXT}; padding: 6px 26px; }}
QMenu::item:selected {{ color: {TEXT}; background-color: {SELECTION}; }}
QStatusBar {{ color: #30425C; background-color: #E9EEF5; }}
QStatusBar QLabel {{ color: #30425C; }}
QToolTip {{ color: {TEXT}; background-color: {SURFACE}; border: 1px solid #96AAC6; }}
QCheckBox {{ color: {TEXT}; spacing: 7px; background: transparent; }}
QCheckBox::indicator {{ width: 16px; height: 16px; }}
QSplitter::handle {{ background-color: #CDD7E4; }}
"""


def apply_theme(app):
    """Apply the same light palette across macOS and Windows, including dark mode."""
    from PySide6.QtGui import QColor, QFont, QPalette

    app.setStyle("Fusion")
    app.setFont(QFont("Microsoft YaHei" if __import__("sys").platform == "win32" else "PingFang SC", 10))
    palette = QPalette()
    colors = {
        QPalette.Window: CANVAS,
        QPalette.WindowText: TEXT,
        QPalette.Base: SURFACE,
        QPalette.AlternateBase: "#F5F8FC",
        QPalette.Text: TEXT,
        QPalette.Button: SURFACE,
        QPalette.ButtonText: TEXT,
        QPalette.Highlight: SELECTION,
        QPalette.HighlightedText: TEXT,
        QPalette.ToolTipBase: SURFACE,
        QPalette.ToolTipText: TEXT,
        QPalette.Link: BLUE,
        QPalette.PlaceholderText: MUTED,
        QPalette.Light: SURFACE,
        QPalette.Midlight: "#E9EEF5",
        QPalette.Mid: "#C4CFDC",
        QPalette.Dark: "#7B8CA3",
    }
    for role, value in colors.items():
        palette.setColor(QPalette.Active, role, QColor(value))
        palette.setColor(QPalette.Inactive, role, QColor(value))
        palette.setColor(QPalette.Disabled, role,
                         QColor(DISABLED_TEXT if role in (QPalette.WindowText, QPalette.Text,
                                                        QPalette.ButtonText, QPalette.HighlightedText) else
                                DISABLED_BG if role in (QPalette.Button, QPalette.Base) else value))
    app.setPalette(palette)
    app.setStyleSheet(STYLESHEET)
