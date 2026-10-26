"""UI integration tests. Run on Windows GitHub Actions with offscreen Qt."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest
pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication, QTableWidgetItem
from batchrename.gui import MainWindow
from batchrename.core import TypeRule


def test_rules_settings_and_preview_invalidation():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        assert window._settings().type_rules == []
        window.add_type_rule()
        assert window.type_rules_table.rowCount() == 1
        window.type_rules_table.closePersistentEditor(window.type_rules_table.item(0, 0))
        window.type_rules_table.item(0, 0).setText("岗位说明书")
        window.type_rules_table.item(0, 1).setText("{参考值}_岗位说明书")
        assert window._settings().type_rules == [TypeRule("岗位说明书", "{参考值}_岗位说明书")]
        window.is_preview_valid = True
        window.type_rules_table.item(0, 1).setText("{参考值}_{匹配值}")
        assert not window.is_preview_valid
        window.type_rules_table.selectRow(0)
        window.remove_type_rules()
        assert window.type_rules_table.rowCount() == 0
        assert window._settings().type_rules == []
    finally:
        window.close()


def test_loaded_rules_replace_existing_rows():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        rules = [TypeRule("岗位说明书", "{参考值}_岗位说明书"),
                 TypeRule("劳动合同协议", "{参考值}_{匹配值}_劳动合同协议")]
        window._set_type_rules(rules)
        assert window._settings().type_rules == rules
        window._set_type_rules([])
        assert window._settings().type_rules == []
    finally:
        window.close()
