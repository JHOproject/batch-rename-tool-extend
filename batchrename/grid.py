"""Excel-like editable QTableView supporting multi-cell clipboard and single-step undo."""
from __future__ import annotations
import csv
import io
from copy import deepcopy
from PySide6.QtCore import Qt, QModelIndex, QAbstractTableModel, Signal
from PySide6.QtGui import QKeySequence, QUndoCommand, QUndoStack
from PySide6.QtWidgets import QTableView, QAbstractItemView
from .reference_io import parse_tsv


def column_label(number: int) -> str:
    result = ""
    number += 1
    while number:
        number, rem = divmod(number - 1, 26)
        result = chr(65 + rem) + result
    return result


class GridReplaceCommand(QUndoCommand):
    def __init__(self, model, after: list[list[str]], description: str):
        super().__init__(description)
        self.model = model
        self.before = deepcopy(model.cells)
        self.after = deepcopy(after)

    def redo(self):
        self.model.replace_cells(self.after)

    def undo(self):
        self.model.replace_cells(self.before)


class GridModel(QAbstractTableModel):
    content_changed = Signal()

    def __init__(self, data: list[list[str]] | None = None, parent=None):
        super().__init__(parent)
        self.cells = self.normalized(data if data is not None else [["姓名", "员工编号"]] + [["", ""] for _ in range(19)])
        self.undo_stack = QUndoStack(self)

    @staticmethod
    def normalized(data: list[list[str]]) -> list[list[str]]:
        if not data:
            data = [["", ""]]
        cols = max(2, *(len(row) for row in data))
        return [[str(x) if x is not None else "" for x in row] + [""] * (cols - len(row)) for row in data]

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.cells)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.cells[0])

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        if role in (Qt.DisplayRole, Qt.EditRole):
            return self.cells[index.row()][index.column()]
        if role == Qt.ForegroundRole:
            from PySide6.QtGui import QColor
            return QColor("#17263D")
        if role == Qt.BackgroundRole and index.row() == 0:
            from PySide6.QtGui import QColor
            return QColor("#e9eff9")
        if role == Qt.FontRole and index.row() == 0:
            from PySide6.QtGui import QFont
            font = QFont()
            font.setBold(True)
            return font
        return None

    def flags(self, index):
        return (Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable) if index.isValid() else Qt.NoItemFlags

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            return column_label(section) if orientation == Qt.Horizontal else str(section + 1)
        return None

    def setData(self, index, value, role=Qt.EditRole):
        if role != Qt.EditRole or not index.isValid():
            return False
        text = str(value)
        if self.cells[index.row()][index.column()] == text:
            return True
        updated = deepcopy(self.cells)
        updated[index.row()][index.column()] = text
        self.undo_stack.push(GridReplaceCommand(self, updated, "编辑单元格"))
        return True

    def replace_cells(self, grid):
        grid = self.normalized(grid)
        shape_changed = len(grid) != len(self.cells) or len(grid[0]) != len(self.cells[0])
        if shape_changed:
            self.beginResetModel()
            self.cells = deepcopy(grid)
            self.endResetModel()
        else:
            self.cells = deepcopy(grid)
            self.dataChanged.emit(self.index(0, 0), self.index(len(grid) - 1, len(grid[0]) - 1))
        self.content_changed.emit()

    def paste(self, start_row: int, start_col: int, pasted: list[list[str]]):
        if not pasted:
            return
        data = deepcopy(self.cells)
        width = max(len(row) for row in pasted)
        needed_cols = max(len(data[0]), start_col + width)
        for row in data:
            row.extend([""] * (needed_cols - len(row)))
        while len(data) < start_row + len(pasted):
            data.append([""] * needed_cols)
        for ri, row in enumerate(pasted):
            for ci, value in enumerate(row):
                data[start_row + ri][start_col + ci] = value
        self.undo_stack.push(GridReplaceCommand(self, data, "批量粘贴"))

    def clear_selection(self, points: list[tuple[int, int]], description="清除单元格"):
        if not points:
            return
        data = deepcopy(self.cells)
        for r, c in points:
            data[r][c] = ""
        self.undo_stack.push(GridReplaceCommand(self, data, description))

    def add_rows(self, count=1):
        data = deepcopy(self.cells)
        data += [[""] * len(data[0]) for _ in range(count)]
        self.undo_stack.push(GridReplaceCommand(self, data, "添加行"))

    def add_column(self):
        data = [row + [""] for row in self.cells]
        self.undo_stack.push(GridReplaceCommand(self, data, "添加列"))

    def delete_rows(self, indexes: list[int]):
        data = [row for i, row in enumerate(self.cells) if i not in indexes or i == 0]
        if data != self.cells:
            self.undo_stack.push(GridReplaceCommand(self, data, "删除行"))

    def delete_columns(self, indexes: list[int]):
        data = [[value for i, value in enumerate(row) if i not in indexes] for row in self.cells]
        if data and data[0]:
            self.undo_stack.push(GridReplaceCommand(self, data, "删除列"))

    def export_grid(self):
        rows = deepcopy(self.cells)
        while len(rows) > 1 and not any(rows[-1]):
            rows.pop()
        while len(rows[0]) > 1 and not any(row[-1] for row in rows):
            for row in rows:
                row.pop()
        return rows


class ExcelTableView(QTableView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.setAlternatingRowColors(True)
        self.setWordWrap(False)
        self.horizontalHeader().setDefaultSectionSize(170)
        self.verticalHeader().setDefaultSectionSize(27)
        self.setTabKeyNavigation(True)

    def _points(self):
        return [(idx.row(), idx.column()) for idx in self.selectedIndexes()]

    def copy_cells(self):
        points = self._points()
        if not points:
            return
        rmin, rmax = min(r for r, _ in points), max(r for r, _ in points)
        cmin, cmax = min(c for _, c in points), max(c for _, c in points)
        grid = self.model().cells
        stream = io.StringIO(newline="")
        writer = csv.writer(stream, delimiter="\t", lineterminator="\r\n")
        selected = set(points)
        for r in range(rmin, rmax + 1):
            writer.writerow([grid[r][c] if (r, c) in selected else "" for c in range(cmin, cmax + 1)])
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(stream.getvalue().rstrip("\r\n"))

    def paste_cells(self):
        from PySide6.QtWidgets import QApplication
        pasted = parse_tsv(QApplication.clipboard().text())
        if not pasted:
            return
        current = self.currentIndex()
        r, c = (current.row(), current.column()) if current.isValid() else (0, 0)
        self.model().paste(r, c, pasted)

    def keyPressEvent(self, event):
        if event.matches(QKeySequence.Copy):
            self.copy_cells()
        elif event.matches(QKeySequence.Paste):
            self.paste_cells()
        elif event.matches(QKeySequence.Cut):
            self.copy_cells()
            self.model().clear_selection(self._points(), "剪切单元格")
        elif event.matches(QKeySequence.Undo):
            self.model().undo_stack.undo()
        elif event.matches(QKeySequence.Redo) or (event.key() == Qt.Key_Y and event.modifiers() == Qt.ControlModifier):
            self.model().undo_stack.redo()
        elif event.key() in (Qt.Key_Delete, Qt.Key_Backspace) and not self.state() == QAbstractItemView.EditingState:
            self.model().clear_selection(self._points())
        else:
            super().keyPressEvent(event)
