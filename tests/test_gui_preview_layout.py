"""Preview gets most of the space; rules remain reachable when required."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest
pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication
from batchrename.gui import MainWindow
from batchrename.core import TypeRule


def test_preview_dominates_default_view_and_rules_can_be_edited():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        window.show()
        window.tabs.setCurrentIndex(2)
        app.processEvents()
        assert window.settings_scroll.isHidden()
        assert window.preview.height() >= 280
        window.toggle_rule_settings()
        app.processEvents()
        assert not window.settings_scroll.isHidden()
        assert window.type_rules_table.isVisible()
        window.toggle_rule_settings()
        app.processEvents()
        assert window.settings_scroll.isHidden()
        assert window.preview.height() >= 280
    finally:
        window.close()


def test_rule_status_and_existing_rules_survive_collapsing():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        rules = [
            TypeRule("岗位说明书", "{参考值}_岗位说明书"),
            TypeRule("劳动合同协议", "{参考值}_{匹配值}_劳动合同协议"),
        ]
        window._set_type_rules(rules)
        assert "2 条" in window.rule_status.text()
        window.toggle_rule_settings()
        window.toggle_rule_settings()
        assert window._settings().type_rules == rules
        window._set_type_rules([])
        assert "默认" in window.rule_status.text()
    finally:
        window.close()


def test_default_format_precedes_type_rules_in_settings():
    """Default matching settings must appear before the type-specific table."""
    from PySide6.QtWidgets import QGroupBox, QLabel

    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        settings = window.settings_scroll.widget().layout()
        first_widget = settings.itemAt(0).widget()
        assert isinstance(first_widget, QGroupBox)
        assert first_widget.title().startswith("文件名匹配与默认格式")
        type_header = settings.itemAt(1).layout()
        assert isinstance(type_header.itemAt(0).widget(), QLabel)
        assert type_header.itemAt(0).widget().text().startswith("按文件类型使用不同命名格式")
        assert settings.itemAt(2).widget() is window.type_rules_table
    finally:
        window.close()
