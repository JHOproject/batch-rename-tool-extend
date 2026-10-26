"""Run with PySide6 installed; Qt test is skipped if the dependency is absent."""
import pytest
pytest.importorskip("PySide6")
from batchrename.grid import GridModel


def test_excel_100x5_paste_and_single_undo():
    model = GridModel()
    before = [row[:] for row in model.cells]
    pasted = [[f"R{r}C{c}" for c in range(5)] for r in range(100)]
    pasted[0] = ["姓名", "員工編號", "部門", "來源", "日期"]
    pasted[1][1] = "00123456"
    model.paste(0, 0, pasted)
    assert model.rowCount() == 100
    assert model.columnCount() == 5
    assert model.cells[1][1] == "00123456"
    assert model.undo_stack.count() == 1
    model.undo_stack.undo()
    assert model.cells == before
    model.undo_stack.redo()
    assert model.cells[1][1] == "00123456"
