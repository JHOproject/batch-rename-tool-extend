"""Runs as a GUI smoke test when PySide6 and an interactive or offscreen Qt setup are available."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest
pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication, QLineEdit, QPushButton
from PySide6.QtGui import QPalette
from batchrename.gui import MainWindow
from batchrename.theme import apply_theme


def test_window_loads_with_readable_light_palette():
    app = QApplication.instance() or QApplication([])
    apply_theme(app)
    window = MainWindow()
    assert window.windowTitle().startswith("批量文件重命名工具")
    assert window.findChildren(QPushButton)
    assert window.findChildren(QLineEdit)
    assert app.palette().color(QPalette.ColorRole.Text).name().lower() == "#17263d"
    assert window.tabs.count() == 3
    window.close()
