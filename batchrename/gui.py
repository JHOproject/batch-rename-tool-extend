"""Windows-oriented PySide6 GUI for the batch rename tool."""
from __future__ import annotations
import csv
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QAction
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QFormLayout, QLabel, QPushButton, QListWidget, QTableWidget,
    QTableWidgetItem, QTabWidget, QComboBox, QLineEdit, QCheckBox,
    QFileDialog, QMessageBox, QInputDialog, QSplitter, QGroupBox,
    QAbstractItemView, QTreeView, QListView, QHeaderView, QFrame, QDialog,
    QScrollArea, QSizePolicy,
)

from .core import (
    ReferenceSource, RenameSettings, TypeRule, PlannedFile, plan_renames, execute_plan,
    undo_latest, save_project, load_project,
)
from .grid import ExcelTableView, GridModel
from .reference_io import list_sheets, read_reference, export_grid_csv


@dataclass
class SourceEditor:
    name: str
    model: GridModel
    match_field: str = ""
    output_field: str = ""

    def collect(self):
        return ReferenceSource(self.name, self.model.export_grid(), self.match_field, self.output_field)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("批量文件重命名工具 · v1.1.2")
        self.resize(1210, 850)
        self.setMinimumSize(970, 620)
        self.sources: list[SourceEditor] = []
        self.plans: list[PlannedFile] = []
        self.current_project: Path | None = None
        self.is_preview_valid = False
        self._updating_fields = False
        self._setup_ui()
        self.add_manual(initial=True)
        self.statusBar().showMessage("请添加要处理的文件夹，并设置参考资料。")

    def _setup_ui(self):
        self._build_menu()
        root = QWidget()
        root.setObjectName("mainRoot")
        self.setCentralWidget(root)
        body = QVBoxLayout(root)
        body.setContentsMargins(22, 17, 22, 12)
        body.setSpacing(12)
        heading = QLabel("批量文件重命名工具")
        heading.setObjectName("title")
        body.addWidget(heading)
        sub = QLabel("可从 Excel／CSV 导入或手动输入参考资料，预览确认后批量重命名。所有文件只在本机处理。")
        sub.setObjectName("subtitle")
        body.addWidget(sub)
        self.tabs = QTabWidget()
        body.addWidget(self.tabs, 1)
        self._build_target_tab()
        self._build_sources_tab()
        self._build_preview_tab()
        self.tabs.currentChanged.connect(lambda _idx: self._refresh_insert_fields())

    def _build_menu(self):
        self.menuBar().setNativeMenuBar(False)
        menu = self.menuBar().addMenu("项目(&P)")
        for text, fn, shortcut in [
            ("新建项目", self.new_project, "Ctrl+N"),
            ("打开项目", self.open_project, "Ctrl+O"),
            ("保存项目", self.save_project_dialog, "Ctrl+S"),
        ]:
            act = QAction(text, self)
            act.setShortcut(shortcut)
            act.triggered.connect(fn)
            menu.addAction(act)
        menu.addSeparator()
        act = QAction("恢复上一次批量重命名", self)
        act.triggered.connect(self.undo_batch)
        menu.addAction(act)

    def _build_target_tab(self):
        page = QWidget()
        page.setObjectName("tabPage")
        layout = QVBoxLayout(page)
        intro = QLabel("01  选择要处理的文件夹")
        intro.setFont(QFont("", 15, QFont.Bold))
        layout.addWidget(intro)
        layout.addWidget(QLabel("可添加多个文件夹；重命名只修改文件名，不会更改文件内容或存放位置。"))
        controls = QHBoxLayout()
        add_btn = QPushButton("＋ 添加文件夹（可多选）")
        add_btn.clicked.connect(self.add_folders)
        remove_btn = QPushButton("移除选中的文件夹")
        remove_btn.clicked.connect(self.remove_folders)
        controls.addWidget(add_btn)
        controls.addWidget(remove_btn)
        controls.addStretch()
        layout.addLayout(controls)
        self.folder_list = QListWidget()
        self.folder_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        layout.addWidget(self.folder_list, 1)
        bottom = QHBoxLayout()
        self.recursive = QCheckBox("包含所有子文件夹")
        self.recursive.toggled.connect(self.invalidate)
        bottom.addWidget(self.recursive)
        bottom.addStretch()
        layout.addLayout(bottom)
        tip = QLabel("提醒：请确认文件夹是否正确。正式重命名前，先到「规则与预览」检查结果。")
        tip.setObjectName("subtitle")
        layout.addWidget(tip)
        self.tabs.addTab(page, "① 目标文件")

    def _build_sources_tab(self):
        page = QWidget()
        page.setObjectName("tabPage")
        layout = QVBoxLayout(page)
        intro = QLabel("02  参考资料（支持直接粘贴 Excel 表格）")
        intro.setFont(QFont("", 15, QFont.Bold))
        layout.addWidget(intro)
        layout.addWidget(QLabel("第 1 行是字段名称；在 A1 粘贴 Excel 多行多列资料，表格会自动扩展。"))
        controls = QHBoxLayout()
        for text, func in [
            ("＋ 新建资料表", self.add_manual),
            ("＋ 导入 Excel／CSV", self.import_files),
            ("修改资料表名称", self.rename_source),
            ("移除资料表", self.remove_source),
        ]:
            btn = QPushButton(text)
            btn.clicked.connect(func)
            controls.addWidget(btn)
        controls.addStretch()
        layout.addLayout(controls)
        split = QSplitter(Qt.Horizontal)
        self.source_list = QListWidget()
        self.source_list.setMinimumWidth(170)
        self.source_list.setMaximumWidth(245)
        self.source_list.currentRowChanged.connect(self.select_source)
        split.addWidget(self.source_list)
        edit_area = QWidget()
        edit_lay = QVBoxLayout(edit_area)
        edit_lay.setContentsMargins(0, 0, 0, 0)
        fields = QHBoxLayout()
        fields.addWidget(QLabel("匹配字段"))
        self.match_combo = QComboBox()
        self.match_combo.setMinimumWidth(110)
        self.match_combo.currentTextChanged.connect(self.source_fields_changed)
        fields.addWidget(self.match_combo)
        fields.addWidget(QLabel("输出字段"))
        self.output_combo = QComboBox()
        self.output_combo.setMinimumWidth(110)
        self.output_combo.currentTextChanged.connect(self.source_fields_changed)
        fields.addWidget(self.output_combo)
        fields.addStretch()
        edit_lay.addLayout(fields)
        self.table = ExcelTableView()
        edit_lay.addWidget(self.table, 1)
        tools = QHBoxLayout()
        for text, func in [
            ("添加行", self.add_row), ("添加列", self.add_column),
            ("删除选中的行", self.delete_row), ("删除选中的列", self.delete_column),
            ("导出 CSV", self.export_source),
        ]:
            btn = QPushButton(text)
            btn.clicked.connect(func)
            tools.addWidget(btn)
        tools.addStretch()
        edit_lay.addLayout(tools)
        help_text = QLabel("Excel 快捷键：Windows 用 Ctrl，Mac 用 ⌘；支持 C／V／X、Z／Y、A、Delete，多格复制和粘贴。")
        help_text.setObjectName("subtitle")
        edit_lay.addWidget(help_text)
        split.addWidget(edit_area)
        split.setStretchFactor(1, 1)
        layout.addWidget(split, 1)
        self.tabs.addTab(page, "② 参考资料")

    def _build_preview_tab(self):
        page = QWidget()
        page.setObjectName("tabPage")
        layout = QVBoxLayout(page)
        intro = QLabel("03  设置规则、预览结果、开始重命名")
        intro.setFont(QFont("", 15, QFont.Bold))
        layout.addWidget(intro)

        # Keep the file list large by default; editing rules is one click away.
        settings_header = QHBoxLayout()
        self.rule_status = QLabel("当前使用默认命名格式")
        self.rule_status.setObjectName("subtitle")
        settings_header.addWidget(self.rule_status)
        settings_header.addStretch()
        self.toggle_settings_btn = QPushButton("展开命名规则设置")
        self.toggle_settings_btn.clicked.connect(self.toggle_rule_settings)
        settings_header.addWidget(self.toggle_settings_btn)
        layout.addLayout(settings_header)

        self.settings_scroll = QScrollArea()
        self.settings_scroll.setObjectName("ruleSettingsScroll")
        self.settings_scroll.setWidgetResizable(True)
        self.settings_scroll.setFrameShape(QFrame.NoFrame)
        self.settings_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.settings_scroll.setMaximumHeight(305)
        self.settings_scroll.setMinimumHeight(180)
        self.settings_scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        settings_body = QWidget()
        settings_body.setObjectName("ruleSettingsBody")
        settings_layout = QVBoxLayout(settings_body)
        settings_layout.setContentsMargins(0, 3, 4, 3)
        settings_layout.setSpacing(8)

        group = QGroupBox("文件名匹配与默认格式（无类型规则时使用）")
        form = QFormLayout(group)
        line = QHBoxLayout()
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("分段完全匹配（推荐）", "segment")
        self.mode_combo.addItem("文件名包含字段文字", "contains")
        self.mode_combo.currentIndexChanged.connect(self.invalidate)
        line.addWidget(self.mode_combo)
        line.addWidget(QLabel("分隔符"))
        self.delimiter = QLineEdit("_")
        self.delimiter.setMaximumWidth(80)
        self.delimiter.textChanged.connect(self.invalidate)
        line.addWidget(self.delimiter)
        line.addStretch()
        form.addRow("匹配方式", line)
        self.template_input = QLineEdit("{参考值}_{移除匹配值后的原文件名}")
        self.template_input.setPlaceholderText("例如：{参考值}_{移除匹配值后的原文件名}")
        self.template_input.textChanged.connect(self.invalidate)
        form.addRow("默认格式（单规则）", self.template_input)
        insert = QHBoxLayout()
        self.insert_combo = QComboBox()
        self.insert_combo.setMinimumWidth(195)
        insert.addWidget(self.insert_combo)
        insert_btn = QPushButton("插入字段变量")
        insert_btn.clicked.connect(self.insert_field)
        insert.addWidget(insert_btn)
        insert.addStretch()
        form.addRow("快速插入", insert)
        hint = QLabel("{参考值} 对应所选的「输出字段」；{移除匹配值后的原文件名} 会删除匹配文字。扩展名保持不变。")
        hint.setWordWrap(True)
        hint.setObjectName("subtitle")
        form.addRow("", hint)
        settings_layout.addWidget(group)

        # File-type rules follow the file-name matching and default-format settings.
        rule_header = QHBoxLayout()
        rule_header.addWidget(QLabel("按文件类型使用不同命名格式（可选）"))
        rule_header.addStretch()
        add_rule_btn = QPushButton("＋ 添加类型规则")
        add_rule_btn.clicked.connect(self.add_type_rule)
        rule_header.addWidget(add_rule_btn)
        delete_rule_btn = QPushButton("删除所选规则")
        delete_rule_btn.clicked.connect(self.remove_type_rules)
        rule_header.addWidget(delete_rule_btn)
        settings_layout.addLayout(rule_header)
        self.type_rules_table = QTableWidget(0, 2)
        self.type_rules_table.setHorizontalHeaderLabels(["原文件名包含的关键字", "对应的新文件名格式"])
        self.type_rules_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.type_rules_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.type_rules_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Interactive)
        self.type_rules_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.type_rules_table.setColumnWidth(0, 230)
        self.type_rules_table.setMinimumHeight(100)
        self.type_rules_table.setMaximumHeight(145)
        self.type_rules_table.itemChanged.connect(self.invalidate)
        settings_layout.addWidget(self.type_rules_table)
        rule_hint = QLabel("每行填一个关键字和格式。添加类型规则后，只处理命中一条规则的文件；未命中或命中多条都会跳过。"
                           "例如：岗位说明书 → {参考值}_岗位说明书；劳动合同协议 → {参考值}_{匹配值}_劳动合同协议。")
        rule_hint.setWordWrap(True)
        rule_hint.setObjectName("subtitle")
        settings_layout.addWidget(rule_hint)

        settings_layout.addStretch()
        self.settings_scroll.setWidget(settings_body)
        layout.addWidget(self.settings_scroll)
        self.settings_scroll.hide()

        row = QHBoxLayout()
        self.summary = QLabel("还没生成预览")
        row.addWidget(self.summary)
        row.addStretch()
        refresh_btn = QPushButton("刷新预览")
        refresh_btn.clicked.connect(self.refresh_preview)
        row.addWidget(refresh_btn)
        export_btn = QPushButton("导出预览 CSV")
        export_btn.clicked.connect(self.export_preview)
        row.addWidget(export_btn)
        layout.addLayout(row)
        self.preview = QTableWidget(0, 5)
        self.preview.setHorizontalHeaderLabels(["状态", "文件夹", "原文件名", "新文件名", "参考资料／原因"])
        self.preview.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.preview.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.preview.setAlternatingRowColors(True)
        self.preview.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.preview.horizontalHeader().setSectionResizeMode(1, QHeaderView.Interactive)
        self.preview.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.preview.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.preview.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        layout.addWidget(self.preview, 1)
        actions = QHBoxLayout()
        actions.addStretch()
        undo_btn = QPushButton("恢复上一次批量重命名")
        undo_btn.clicked.connect(self.undo_batch)
        actions.addWidget(undo_btn)
        self.execute_btn = QPushButton("开始重命名")
        self.execute_btn.setObjectName("primary")
        self.execute_btn.setEnabled(False)
        self.execute_btn.clicked.connect(self.execute_batch)
        actions.addWidget(self.execute_btn)
        layout.addLayout(actions)
        self.tabs.addTab(page, "③ 规则与预览")

    def toggle_rule_settings(self):
        """Keep the preview spacious without removing access to any rule settings."""
        is_expanding = self.settings_scroll.isHidden()
        self.settings_scroll.setVisible(is_expanding)
        self.toggle_settings_btn.setText("收起规则设置 · 放大预览" if is_expanding else "展开命名规则设置")

    def _update_rule_status(self):
        count = sum(
            bool(self.type_rules_table.item(row, 0) and self.type_rules_table.item(row, 0).text().strip())
            for row in range(self.type_rules_table.rowCount())
        )
        if count:
            self.rule_status.setText(f"当前已设置 {count} 条文件类型规则")
        else:
            self.rule_status.setText("当前使用默认命名格式（尚无文件类型规则）")

    def add_type_rule(self):
        row = self.type_rules_table.rowCount()
        self.type_rules_table.insertRow(row)
        self.type_rules_table.setItem(row, 0, QTableWidgetItem(""))
        self.type_rules_table.setItem(row, 1, QTableWidgetItem(self.template_input.text()))
        self.type_rules_table.setCurrentCell(row, 0)
        self.type_rules_table.editItem(self.type_rules_table.item(row, 0))
        self.invalidate()

    def remove_type_rules(self):
        rows = sorted({index.row() for index in self.type_rules_table.selectedIndexes()}, reverse=True)
        for row in rows:
            self.type_rules_table.removeRow(row)
        if rows:
            self.invalidate()

    def _set_type_rules(self, rules: list[TypeRule]):
        self.type_rules_table.blockSignals(True)
        try:
            self.type_rules_table.setRowCount(0)
            for rule in rules:
                row = self.type_rules_table.rowCount()
                self.type_rules_table.insertRow(row)
                self.type_rules_table.setItem(row, 0, QTableWidgetItem(rule.keyword))
                self.type_rules_table.setItem(row, 1, QTableWidgetItem(rule.template))
        finally:
            self.type_rules_table.blockSignals(False)
        self.invalidate()

    def _message(self, title: str, text: str, icon=QMessageBox.Information):
        dialog = QMessageBox(self)
        dialog.setWindowTitle(title)
        dialog.setText(text)
        dialog.setIcon(icon)
        dialog.setStandardButtons(QMessageBox.Ok)
        dialog.button(QMessageBox.Ok).setText("确定")
        dialog.exec()

    def _confirm(self, title: str, text: str) -> bool:
        dialog = QMessageBox(self)
        dialog.setWindowTitle(title)
        dialog.setText(text)
        dialog.setIcon(QMessageBox.Question)
        dialog.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        dialog.button(QMessageBox.Yes).setText("确定")
        dialog.button(QMessageBox.No).setText("取消")
        return dialog.exec() == QMessageBox.Yes

    def show_error(self, text: str):
        self._message("操作未完成", text, QMessageBox.Warning)

    @staticmethod
    def _localize_picker(dialog: QFileDialog):
        dialog.setOption(QFileDialog.DontUseNativeDialog, True)
        dialog.setLabelText(QFileDialog.LookIn, "位置")
        dialog.setLabelText(QFileDialog.FileName, "文件名")
        dialog.setLabelText(QFileDialog.FileType, "文件类型")
        dialog.setLabelText(QFileDialog.Accept, "确定")
        dialog.setLabelText(QFileDialog.Reject, "取消")
        return dialog

    def _pick_files(self, title: str, name_filter: str) -> list[str]:
        dlg = self._localize_picker(QFileDialog(self, title))
        dlg.setFileMode(QFileDialog.ExistingFiles)
        dlg.setNameFilter(name_filter)
        return dlg.selectedFiles() if dlg.exec() == QDialog.Accepted else []

    def _pick_file(self, title: str, name_filter: str) -> str:
        dlg = self._localize_picker(QFileDialog(self, title))
        dlg.setFileMode(QFileDialog.ExistingFile)
        dlg.setNameFilter(name_filter)
        return dlg.selectedFiles()[0] if dlg.exec() == QDialog.Accepted and dlg.selectedFiles() else ""

    def _save_file(self, title: str, proposed: str, name_filter: str) -> str:
        dlg = self._localize_picker(QFileDialog(self, title))
        dlg.setAcceptMode(QFileDialog.AcceptSave)
        dlg.setFileMode(QFileDialog.AnyFile)
        dlg.setNameFilter(name_filter)
        dlg.selectFile(proposed)
        return dlg.selectedFiles()[0] if dlg.exec() == QDialog.Accepted and dlg.selectedFiles() else ""

    def _input_item(self, title: str, prompt: str, choices: list[str]):
        dlg = QInputDialog(self)
        dlg.setWindowTitle(title)
        dlg.setLabelText(prompt)
        dlg.setComboBoxItems(choices)
        dlg.setComboBoxEditable(False)
        dlg.setOkButtonText("确定")
        dlg.setCancelButtonText("取消")
        return dlg.textValue(), dlg.exec() == QDialog.Accepted

    def _input_int(self, title: str, prompt: str, initial=1):
        dlg = QInputDialog(self)
        dlg.setWindowTitle(title)
        dlg.setLabelText(prompt)
        dlg.setInputMode(QInputDialog.IntInput)
        dlg.setIntRange(1, 100000)
        dlg.setIntValue(initial)
        dlg.setOkButtonText("确定")
        dlg.setCancelButtonText("取消")
        accepted = dlg.exec() == QDialog.Accepted
        return dlg.intValue(), accepted

    def _input_text(self, title: str, prompt: str, value: str):
        dlg = QInputDialog(self)
        dlg.setWindowTitle(title)
        dlg.setLabelText(prompt)
        dlg.setInputMode(QInputDialog.TextInput)
        dlg.setTextValue(value)
        dlg.setOkButtonText("确定")
        dlg.setCancelButtonText("取消")
        accepted = dlg.exec() == QDialog.Accepted
        return dlg.textValue(), accepted

    def invalidate(self, *_args):
        self._update_rule_status()
        self.is_preview_valid = False
        self.execute_btn.setEnabled(False)
        self.summary.setText("资料或设置已更改，请刷新预览")

    def add_folders(self):
        # Force the non-native chooser so multiple directories can be selected.
        dlg = QFileDialog(self, "选择一个或多个文件夹")
        self._localize_picker(dlg)
        dlg.setFileMode(QFileDialog.Directory)
        for view in dlg.findChildren(QListView) + dlg.findChildren(QTreeView):
            view.setSelectionMode(QAbstractItemView.ExtendedSelection)
        if dlg.exec():
            existing = {self.folder_list.item(i).text().casefold() for i in range(self.folder_list.count())}
            for folder in dlg.selectedFiles():
                p = str(Path(folder).resolve())
                if Path(p).is_dir() and p.casefold() not in existing:
                    self.folder_list.addItem(p)
                    existing.add(p.casefold())
            self.invalidate()

    def remove_folders(self):
        for item in self.folder_list.selectedItems():
            self.folder_list.takeItem(self.folder_list.row(item))
        self.invalidate()

    def _attach_source(self, source: SourceEditor):
        source.model.content_changed.connect(lambda: self._source_data_changed(source))
        self.sources.append(source)
        self.source_list.addItem(source.name)
        self.source_list.setCurrentRow(len(self.sources) - 1)
        self.invalidate()

    def add_manual(self, checked=False, initial=False):
        if initial:
            name = "手动输入 1"
        else:
            name = f"手动输入 {sum(s.name.startswith('手动输入') for s in self.sources) + 1}"
        src = SourceEditor(name, GridModel(), "姓名", "员工编号")
        self._attach_source(src)

    def import_files(self):
        paths = self._pick_files("导入参考文件", "Excel／CSV 文件 (*.xlsx *.xls *.csv)")
        for name in paths:
            try:
                path = Path(name)
                sheet = ""
                if path.suffix.lower() in {".xlsx", ".xls"}:
                    choices = list_sheets(path)
                    if not choices:
                        raise ValueError("找不到工作表")
                    sheet, okay = self._input_item("选择工作表", f"{path.name} 的工作表", choices)
                    if not okay:
                        continue
                heading, okay = self._input_int("选择标题行", f"{path.name}：字段名称在第几行？")
                if not okay:
                    continue
                grid = read_reference(path, sheet, heading)
                if not grid or not any(grid[0]):
                    raise ValueError("标题行是空白的")
                headers = [str(x).strip() for x in grid[0] if x]
                match = "姓名" if "姓名" in headers else (headers[0] if headers else "")
                out = next((h for h in ("员工编号", "員工編號") if h in headers), headers[1] if len(headers) > 1 else "")
                self._attach_source(SourceEditor(f"{path.name}" + (f" / {sheet}" if sheet else ""), GridModel(grid), match, out))
            except (OSError, ValueError, ImportError, KeyError) as exc:
                self.show_error(f"导入 {name} 失败：\n{exc}")

    def current_source(self) -> SourceEditor | None:
        row = self.source_list.currentRow()
        return self.sources[row] if 0 <= row < len(self.sources) else None

    def _source_data_changed(self, source):
        if source is self.current_source():
            self._set_mapping_choices(source)
        self._refresh_insert_fields()
        self.invalidate()

    def select_source(self, row):
        source = self.current_source()
        if source is not None:
            self.table.setModel(source.model)
            self._set_mapping_choices(source)
        else:
            self.table.setModel(None)
            self._set_mapping_choices(None)
        self._refresh_insert_fields()

    def _set_mapping_choices(self, source):
        self._updating_fields = True
        try:
            headers = [h for h in (source.model.cells[0] if source else []) if h.strip()]
            self.match_combo.clear()
            self.output_combo.clear()
            self.match_combo.addItems(headers)
            self.output_combo.addItems(headers)
            if source is not None:
                for combo, selected in [(self.match_combo, source.match_field), (self.output_combo, source.output_field)]:
                    if selected in headers:
                        combo.setCurrentText(selected)
                    elif headers:
                        combo.setCurrentIndex(0)
                source.match_field = self.match_combo.currentText()
                source.output_field = self.output_combo.currentText()
        finally:
            self._updating_fields = False

    def source_fields_changed(self, *_):
        if self._updating_fields:
            return
        src = self.current_source()
        if src:
            src.match_field = self.match_combo.currentText()
            src.output_field = self.output_combo.currentText()
        self.invalidate()

    def _refresh_insert_fields(self):
        selected = self.insert_combo.currentText() if hasattr(self, 'insert_combo') else ""
        self.insert_combo.clear()
        options = ["参考值", "匹配值", "原文件名", "移除匹配值后的原文件名"]
        for src in self.sources:
            for header in src.model.cells[0]:
                if header and header not in options:
                    options.append(header)
        self.insert_combo.addItems(options)
        if selected in options:
            self.insert_combo.setCurrentText(selected)

    def insert_field(self):
        variable = self.insert_combo.currentText()
        if variable:
            self.template_input.insert("{" + variable + "}")
            self.template_input.setFocus()

    def rename_source(self):
        src = self.current_source()
        if not src:
            return
        name, okay = self._input_text("修改资料表名称", "资料表名称", src.name)
        if okay and name.strip():
            src.name = name.strip()
            self.source_list.currentItem().setText(src.name)
            self.invalidate()

    def remove_source(self):
        index = self.source_list.currentRow()
        if index < 0:
            return
        self.sources.pop(index)
        self.source_list.takeItem(index)
        self.select_source(self.source_list.currentRow())
        self.invalidate()

    def add_row(self):
        if self.current_source():
            self.current_source().model.add_rows()

    def add_column(self):
        if self.current_source():
            self.current_source().model.add_column()

    def delete_row(self):
        src = self.current_source()
        if src:
            indexes = sorted({x.row() for x in self.table.selectedIndexes() if x.row() > 0})
            src.model.delete_rows(indexes)

    def delete_column(self):
        src = self.current_source()
        if src:
            indexes = sorted({x.column() for x in self.table.selectedIndexes()})
            src.model.delete_columns(indexes)

    def export_source(self):
        src = self.current_source()
        if not src:
            return
        filename = self._save_file("导出参考资料", "参考资料.csv", "CSV (*.csv)")
        if filename:
            try:
                export_grid_csv(Path(filename), src.model.export_grid())
            except OSError as exc:
                self.show_error(str(exc))

    def _settings(self):
        return RenameSettings(
            folders=[self.folder_list.item(i).text() for i in range(self.folder_list.count())],
            recursive=self.recursive.isChecked(),
            match_mode=self.mode_combo.currentData(),
            delimiter=self.delimiter.text(),
            template=self.template_input.text(),
            type_rules=[
                TypeRule(self.type_rules_table.item(row, 0).text() if self.type_rules_table.item(row, 0) else "",
                         self.type_rules_table.item(row, 1).text() if self.type_rules_table.item(row, 1) else "")
                for row in range(self.type_rules_table.rowCount())
            ],
        )

    def refresh_preview(self):
        if not self.folder_list.count():
            self.show_error("请先添加至少一个目标文件夹")
            return
        try:
            plans = plan_renames(self._settings(), [x.collect() for x in self.sources])
        except (ValueError, OSError, KeyError) as exc:
            self.show_error(str(exc))
            return
        self.plans = plans
        self.is_preview_valid = True
        self.preview.setRowCount(len(plans))
        count = {}
        for row, p in enumerate(plans):
            count[p.status] = count.get(p.status, 0) + 1
            ref_or_reason = p.detail or ((f"类型：{p.rule}｜" if p.rule else "") + p.source)
            vals = [p.status, str(Path(p.original).parent), Path(p.original).name,
                    Path(p.proposed).name if p.proposed else "—", ref_or_reason]
            for col, val in enumerate(vals):
                cell = QTableWidgetItem(val)
                cell.setToolTip(val)
                if col == 0:
                    cell.setForeground(QColor("#116A3A" if p.executable else "#9A4612" if p.status == "未匹配" else "#ae2530"))
                self.preview.setItem(row, col, cell)
        parts = [f"总数 {len(plans)}", f"可重命名 {count.get('可重命名', 0)}"]
        parts.extend(f"{key} {num}" for key, num in count.items() if key != "可重命名")
        self.summary.setText("　｜　".join(parts))
        self.execute_btn.setEnabled(count.get("可重命名", 0) > 0)
        self.statusBar().showMessage("预览已更新。有问题的文件会自动跳过。")
        # After previewing, return the freed height to the results table.
        if not self.settings_scroll.isHidden():
            self.toggle_rule_settings()

    def execute_batch(self):
        if not self.is_preview_valid:
            self.show_error("资料已更改，请先刷新预览")
            return
        count = sum(p.executable for p in self.plans)
        if count == 0:
            return
        if not self._confirm("确认批量重命名", f"即将重命名 {count} 个文件。\n不会覆盖已有文件，其他有问题的文件会跳过。确定继续吗？"):
            return
        try:
            completed, errors = execute_plan(self.plans)
        except (OSError, ValueError) as exc:
            self.show_error(str(exc))
            return
        text = f"成功重命名 {completed} 个文件。"
        if errors:
            text += "\n\n失败或跳过：\n" + "\n".join(errors[:15])
            if len(errors) > 15:
                text += f"\n…另外还有 {len(errors) - 15} 项（请刷新预览查看）"
        self._message("处理结果", text)
        self.invalidate()
        self.refresh_preview()

    def undo_batch(self):
        if not self._confirm("恢复文件名", "将尝试恢复最近一次批量重命名。\n如果文件已更改或原文件名被占用，会自动跳过。确定继续吗？"):
            return
        try:
            count, errors = undo_latest()
        except (OSError, ValueError) as exc:
            self.show_error(str(exc))
            return
        detail = f"已恢复 {count} 个文件。"
        if errors:
            detail += "\n" + "\n".join(errors[:15])
        self._message("恢复结果", detail)
        self.invalidate()

    def export_preview(self):
        if not self.is_preview_valid:
            self.show_error("请先刷新预览")
            return
        path = self._save_file("导出预览", "重命名预览.csv", "CSV (*.csv)")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["状态", "原文件完整路径", "新文件完整路径", "参考来源", "类型规则", "原因"])
                writer.writerows([[p.status, p.original, p.proposed, p.source, p.rule, p.detail] for p in self.plans])
        except OSError as exc:
            self.show_error(str(exc))

    def new_project(self):
        if not self._confirm("新建项目", "将清空当前项目，未保存的修改会丢失。确定继续吗？"):
            return
        self.folder_list.clear()
        self.sources.clear()
        self.source_list.clear()
        self.recursive.setChecked(False)
        self.mode_combo.setCurrentIndex(0)
        self.delimiter.setText("_")
        self.template_input.setText("{参考值}_{移除匹配值后的原文件名}")
        self._set_type_rules([])
        self.current_project = None
        self.add_manual(initial=True)
        self.plans = []
        self.preview.setRowCount(0)
        self.invalidate()
        self.tabs.setCurrentIndex(0)

    def save_project_dialog(self):
        if self.current_project is None:
            name = self._save_file("保存项目", "批量重命名项目.brproj.json", "项目 (*.json)")
            if not name:
                return
            self.current_project = Path(name)
        try:
            save_project(self.current_project, self._settings(), [s.collect() for s in self.sources])
            self.statusBar().showMessage(f"项目已保存：{self.current_project}")
        except (OSError, ValueError) as exc:
            self.show_error(str(exc))

    @staticmethod
    def _modern_template(template: str) -> str:
        for legacy, current in (
            ("{參照值}", "{参考值}"),
            ("{比對值}", "{匹配值}"),
            ("{原檔名}", "{原文件名}"),
            ("{移除比對值後的原檔名}", "{移除匹配值后的原文件名}"),
        ):
            template = template.replace(legacy, current)
        return template

    def open_project(self):
        path = self._pick_file("打开项目", "项目 (*.json)")
        if not path:
            return
        try:
            settings, sources = load_project(Path(path))
            self.folder_list.clear()
            self.sources.clear()
            self.source_list.clear()
            for folder in settings.folders:
                self.folder_list.addItem(folder)
            self.recursive.setChecked(settings.recursive)
            self.mode_combo.setCurrentIndex(0 if settings.match_mode == "segment" else 1)
            self.delimiter.setText(settings.delimiter)
            # Reserved variables from projects made with v1.0 are displayed
            # using the new simplified-Chinese names. Original reference
            # headers and file names are never translated.
            modern_template = self._modern_template(settings.template)
            self.template_input.setText(modern_template)
            self._set_type_rules([TypeRule(rule.keyword, self._modern_template(rule.template))
                                  for rule in settings.type_rules])
            for src in sources:
                display_name = src.name
                if display_name.startswith("手動輸入 "):
                    display_name = display_name.replace("手動輸入 ", "手动输入 ", 1)
                self._attach_source(SourceEditor(display_name, GridModel(src.grid), src.match_field, src.output_field))
            self.current_project = Path(path)
            self.plans = []
            self.preview.setRowCount(0)
            self.invalidate()
            self.statusBar().showMessage(f"项目已打开：{path}")
        except (OSError, ValueError, KeyError, TypeError) as exc:
            self.show_error(f"打开项目失败：{exc}")
