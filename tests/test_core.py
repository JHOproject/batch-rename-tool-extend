from pathlib import Path
import json
import pytest
from batchrename.core import (
    ReferenceSource, RenameSettings, plan_renames, execute_plan, undo_latest,
    save_project, load_project, remove_match, template_fields,
)
from batchrename.reference_io import parse_tsv, read_csv, export_grid_csv


def setup_plan(tmp_path, filenames=None, grid=None, template=None, mode="segment", delimiter="_"):
    filenames = filenames if filenames is not None else ["職位及薪資調整通知書_Position & Compensation Adjustment Statement_姜江蕙.pdf"]
    grid = grid if grid is not None else [["姓名", "員工編號", "部門"], ["姜江蕙", "31234567", "人資"]]
    for name in filenames:
        (tmp_path / name).write_bytes(b"PDF-contents")
    settings = RenameSettings([str(tmp_path)], False, mode, delimiter,
        template or "{參照值}_{移除比對值後的原檔名}")
    src = ReferenceSource("員工資料", grid, "姓名", "員工編號")
    return settings, [src]


def test_expected_filename(tmp_path):
    settings, sources = setup_plan(tmp_path)
    p = plan_renames(settings, sources)[0]
    assert p.status == "可重命名"
    assert Path(p.proposed).name == "31234567_職位及薪資調整通知書_Position & Compensation Adjustment Statement.pdf"


def test_execute_and_undo(tmp_path):
    settings, sources = setup_plan(tmp_path)
    plan = plan_renames(settings, sources)
    old, new = Path(plan[0].original), Path(plan[0].proposed)
    history_path = tmp_path.parent / "history.json"
    done, errors = execute_plan(plan, history_path)
    assert done == 1 and not errors
    assert not old.exists() and new.read_bytes() == b"PDF-contents"
    assert json.loads(history_path.read_text())['transactions'][0]['entries'][0]['original'] == str(old)
    reverted, errors = undo_latest(history_path)
    assert reverted == 1 and not errors
    assert old.read_bytes() == b"PDF-contents" and not new.exists()


def test_unmatched(tmp_path):
    settings, src = setup_plan(tmp_path, ["文件_未知的人.pdf"])
    assert plan_renames(settings, src)[0].status == "未匹配"


def test_duplicate_name_different_ids(tmp_path):
    settings, src = setup_plan(tmp_path, grid=[["姓名", "員工編號"], ["姜江蕙", "31234567"], ["姜江蕙", "31234568"]])
    assert plan_renames(settings, src)[0].status == "多项匹配"


def test_duplicate_name_same_ids_ok(tmp_path):
    settings, src = setup_plan(tmp_path, grid=[["姓名", "員工編號"], ["姜江蕙", "31234567"], ["姜江蕙", "31234567"]])
    assert plan_renames(settings, src)[0].status == "可重命名"


def test_ambiguous_match(tmp_path):
    settings, src = setup_plan(tmp_path, filenames=["文件_王小明_王大明.pdf"],
        grid=[["姓名", "員工編號"], ["王小明", "010"], ["王大明", "020"]])
    assert plan_renames(settings, src)[0].status == "多项匹配"


def test_dest_occupied(tmp_path):
    settings, src = setup_plan(tmp_path)
    p = plan_renames(settings, src)[0]
    Path(p.proposed).write_bytes(b"DO NOT OVERWRITE")
    results = plan_renames(settings, src)
    assert any(x.status == "文件名冲突" for x in results)
    assert Path(p.proposed).read_bytes() == b"DO NOT OVERWRITE"


def test_same_dest_for_two_sources(tmp_path):
    settings, src = setup_plan(tmp_path, filenames=["通知_姜江蕙.pdf", "通知_王莉萍.pdf"],
        grid=[["姓名", "員工編號"], ["姜江蕙", "777"], ["王莉萍", "777"]])
    outcomes = plan_renames(settings, src)
    assert all(p.status == "文件名冲突" for p in outcomes)


def test_last_second_occupied(tmp_path):
    settings, src = setup_plan(tmp_path)
    p = plan_renames(settings, src)[0]
    Path(p.proposed).write_bytes(b"occupied")
    count, errors = execute_plan([p], tmp_path.parent / "history2.json")
    assert count == 0 and errors
    assert Path(p.proposed).read_bytes() == b"occupied"


def test_last_second_modified(tmp_path):
    settings, src = setup_plan(tmp_path)
    p = plan_renames(settings, src)[0]
    Path(p.original).write_bytes(b"updated CONTENT")
    count, errors = execute_plan([p], tmp_path.parent / "history3.json")
    assert count == 0 and errors


def test_undo_occupied_original(tmp_path):
    settings, src = setup_plan(tmp_path)
    p = plan_renames(settings, src)[0]
    h = tmp_path.parent / "history4.json"
    execute_plan([p], h)
    Path(p.original).write_bytes(b"new competing file")
    count, errors = undo_latest(h)
    assert count == 0 and errors
    assert Path(p.original).read_bytes() == b"new competing file"


def test_rule_can_use_extra_column(tmp_path):
    settings, src = setup_plan(tmp_path, template="{部門}_{員工編號}_{移除比對值後的原檔名}")
    assert Path(plan_renames(settings, src)[0].proposed).name.startswith("人資_31234567_")


def test_multiple_sources_with_different_headers(tmp_path):
    settings, src = setup_plan(tmp_path, filenames=["文件_姜江蕙.pdf", "文件_王莉萍.pdf"],
        grid=[["姓名", "員工編號"], ["姜江蕙", "31234567"]])
    src.append(ReferenceSource("員工二", [["Employee Name", "Staff ID"], ["王莉萍", "09876543"]], "Employee Name", "Staff ID"))
    result = plan_renames(settings, src)
    assert {Path(x.proposed).name for x in result} == {"31234567_文件.pdf", "09876543_文件.pdf"}


def test_contains_mode(tmp_path):
    settings, src = setup_plan(tmp_path, filenames=["文件-姜江蕙-完成.pdf"], mode="contains")
    outcome = plan_renames(settings, src)[0]
    assert outcome.status == "可重命名"
    assert Path(outcome.proposed).name == "31234567_文件-完成.pdf"


def test_no_malicious_format(tmp_path):
    settings, src = setup_plan(tmp_path, template="{姓名.__class__}")
    with pytest.raises(ValueError):
        plan_renames(settings, src)


def test_invalid_characters(tmp_path):
    settings, src = setup_plan(tmp_path, template="bad:name")
    assert plan_renames(settings, src)[0].status == "字段或文件名无效"


def test_project_save_reload(tmp_path):
    settings, src = setup_plan(tmp_path)
    path = tmp_path.parent / 'myproject.json'
    save_project(path, settings, src)
    loaded_settings, loaded_sources = load_project(path)
    assert loaded_settings == settings and loaded_sources == src


def test_tsv_paste_unicode_zeros_quotes():
    tsv = '姓名\t員工編號\r\n姜江蕙\t00123456\r\n王莉萍\t"two\twords"\r\n'
    assert parse_tsv(tsv) == [["姓名", "員工編號"], ["姜江蕙", "00123456"], ["王莉萍", "two\twords"]]


def test_csv_chinese_and_zeros(tmp_path):
    path = tmp_path / "測試.csv"
    grid = [["姓名", "員工編號"], ["姜江蕙", "00123456"]]
    export_grid_csv(path, grid)
    assert read_csv(path) == grid


def test_empty_reference_value_ignored(tmp_path):
    settings, src = setup_plan(tmp_path, grid=[["姓名", "員工編號"], ["姜江蕙", ""]])
    assert plan_renames(settings, src)[0].status == "字段或文件名无效"


def test_preserve_suffix(tmp_path):
    settings, src = setup_plan(tmp_path, filenames=["文件_姜江蕙.DOCX"])
    assert Path(plan_renames(settings, src)[0].proposed).suffix == ".DOCX"


def test_recursion(tmp_path):
    nested = tmp_path / "child"
    nested.mkdir()
    settings, src = setup_plan(tmp_path, filenames=[])
    (nested / "文件_姜江蕙.pdf").write_text("test")
    assert plan_renames(settings, src) == []
    settings.recursive = True
    assert len(plan_renames(settings, src)) == 1


def test_xlsx_number_formats_without_excel_coercion():
    from batchrename.reference_io import _xlsx_value
    class Cell:
        def __init__(self, value, number_format="General"):
            self.value = value
            self.number_format = number_format
    assert _xlsx_value(Cell("00123456")) == "00123456"
    assert _xlsx_value(Cell(123456, "00000000")) == "00123456"
    assert _xlsx_value(Cell(123456.0, "00000000")) == "00123456"


def test_file_not_reverted_if_modified_after_execution(tmp_path):
    settings, src = setup_plan(tmp_path)
    p = plan_renames(settings, src)[0]
    h = tmp_path.parent / "history5.json"
    execute_plan([p], h)
    Path(p.proposed).write_bytes(b"changed after rename")
    done, errors = undo_latest(h)
    assert done == 0 and errors
    assert Path(p.proposed).read_bytes() == b"changed after rename"


def test_windows_reserved_filename(tmp_path):
    settings, src = setup_plan(tmp_path, template="CON")
    assert plan_renames(settings, src)[0].status == "字段或文件名无效"


def test_default_simplified_template(tmp_path):
    settings, sources = setup_plan(tmp_path)
    settings.template = RenameSettings().template
    plan = plan_renames(settings, sources)[0]
    assert plan.executable
    assert Path(plan.proposed).name.startswith("31234567_")


def test_legacy_traditional_template_still_supported(tmp_path):
    settings, sources = setup_plan(tmp_path)
    settings.template = "{參照值}_{移除比對值後的原檔名}"
    plan = plan_renames(settings, sources)[0]
    assert plan.executable
    assert Path(plan.proposed).name.startswith("31234567_")


def test_dynamic_simplified_column_name(tmp_path):
    settings, sources = setup_plan(tmp_path, grid=[["姓名", "员工编号", "部门"], ["姜江蕙", "00123456", "人事"]])
    sources[0].output_field = "员工编号"
    settings.template = "{部门}_{参考值}_{移除匹配值后的原文件名}"
    plan = plan_renames(settings, sources)[0]
    assert plan.executable
    assert Path(plan.proposed).name.startswith("人事_00123456_")
