"""Regression tests for v1.1.0 filename-category rules."""
import json
from pathlib import Path

import pytest

from batchrename.core import (ReferenceSource, RenameSettings, TypeRule,
                              plan_renames, execute_plan, undo_latest, save_project, load_project)


def scenario(tmp_path, filenames=None):
    filenames = filenames or ["岗位说明书_依婷.pdf", "劳动合同协议_依婷.docx",
                              "岗位说明书_小明.txt", "其他材料_依婷.pdf"]
    for filename in filenames:
        (tmp_path / filename).write_bytes(b"original content")
    settings = RenameSettings(
        folders=[str(tmp_path)],
        type_rules=[
            TypeRule("岗位说明书", "{参考值}_岗位说明书"),
            TypeRule("劳动合同协议", "{参考值}_{匹配值}_劳动合同协议"),
        ],
    )
    source = ReferenceSource("员工名单", [["姓名", "员工编号"],
                                        ["依婷", "12334"], ["小明", "00789"]],
                             "姓名", "员工编号")
    return settings, [source]


def test_different_templates_apply_in_one_batch(tmp_path):
    settings, sources = scenario(tmp_path)
    plans = plan_renames(settings, sources)
    expected = {
        "岗位说明书_依婷.pdf": ("可重命名", "12334_岗位说明书.pdf", "岗位说明书"),
        "劳动合同协议_依婷.docx": ("可重命名", "12334_依婷_劳动合同协议.docx", "劳动合同协议"),
        "岗位说明书_小明.txt": ("可重命名", "00789_岗位说明书.txt", "岗位说明书"),
        "其他材料_依婷.pdf": ("未匹配", "", ""),
    }
    assert {Path(p.original).name: (p.status, Path(p.proposed).name if p.proposed else "", p.rule)
            for p in plans} == expected
    assert "类型关键字" in next(p.detail for p in plans if not p.executable)


def test_execute_undo_multi_type_batch(tmp_path):
    settings, sources = scenario(tmp_path)
    original_files = {p.name for p in tmp_path.iterdir()}
    plans = plan_renames(settings, sources)
    history_file = tmp_path.parent / "type_rules_history.json"
    n, errors = execute_plan(plans, history_file)
    assert (n, errors) == (3, [])
    assert (tmp_path / "12334_岗位说明书.pdf").read_bytes() == b"original content"
    assert (tmp_path / "其他材料_依婷.pdf").exists()
    undone, errors = undo_latest(history_file)
    assert (undone, errors) == (3, [])
    assert {p.name for p in tmp_path.iterdir()} == original_files


def test_overlapping_keywords_are_skipped_not_guessed(tmp_path):
    settings, sources = scenario(tmp_path, ["岗位说明书_依婷.pdf"])
    settings.type_rules.append(TypeRule("岗位", "{参考值}_其他"))
    plan = plan_renames(settings, sources)[0]
    assert plan.status == "多项匹配"
    assert "岗位说明书" in plan.detail and "岗位" in plan.detail
    assert not plan.executable


def test_duplicate_category_keyword_rejected(tmp_path):
    settings, sources = scenario(tmp_path, ["岗位说明书_依婷.pdf"])
    settings.type_rules.append(TypeRule(" 岗位说明书 ", "{参考值}_文件"))
    with pytest.raises(ValueError, match="关键字重复"):
        plan_renames(settings, sources)


def test_empty_keyword_and_empty_template_rejected(tmp_path):
    settings, sources = scenario(tmp_path, ["岗位说明书_依婷.pdf"])
    settings.type_rules[0].keyword = "  "
    with pytest.raises(ValueError, match="关键字不可留空"):
        plan_renames(settings, sources)
    settings.type_rules[0].keyword = "岗位说明书"
    settings.type_rules[0].template = "  "
    with pytest.raises(ValueError, match="格式不可留空"):
        plan_renames(settings, sources)


def test_unknown_field_and_unsafe_templates_rejected(tmp_path):
    settings, sources = scenario(tmp_path, ["岗位说明书_依婷.pdf"])
    settings.type_rules[0].template = "{不存在}"
    with pytest.raises(ValueError, match="未知字段"):
        plan_renames(settings, sources)
    settings.type_rules[0].template = "{姓名.__class__}"
    with pytest.raises(ValueError):
        plan_renames(settings, sources)
    settings.type_rules[0].template = "{参考值}:岗位说明书"
    assert plan_renames(settings, sources)[0].status == "字段或文件名无效"


def test_legacy_global_template_unchanged(tmp_path):
    settings, sources = scenario(tmp_path, ["岗位说明书_依婷.pdf"])
    settings.type_rules = []
    assert Path(plan_renames(settings, sources)[0].proposed).name == "12334_岗位说明书.pdf"


def test_project_roundtrip_and_old_project_compatibility(tmp_path):
    settings, sources = scenario(tmp_path, ["岗位说明书_依婷.pdf"])
    project_file = tmp_path.parent / "multi_type_project.json"
    save_project(project_file, settings, sources)
    loaded_settings, loaded_sources = load_project(project_file)
    assert loaded_settings == settings
    assert loaded_sources == sources
    assert loaded_settings.type_rules[0].keyword == "岗位说明书"
    assert plan_renames(loaded_settings, loaded_sources)[0].executable

    legacy = json.loads(project_file.read_text(encoding="utf-8"))
    del legacy["settings"]["type_rules"]
    project_file.write_text(json.dumps(legacy, ensure_ascii=False), encoding="utf-8")
    old_settings, _ = load_project(project_file)
    assert old_settings.type_rules == []


def test_case_insensitive_category_and_dont_rename_unrelated_files(tmp_path):
    settings, sources = scenario(tmp_path, ["HR_岗位说明书_依婷.PDF", "无关文件_小明.txt"])
    settings.type_rules[0].keyword = "hr_岗位说明书"
    plans = plan_renames(settings, sources)
    assert sum(p.executable for p in plans) == 1
    assert next(p for p in plans if p.executable).proposed.endswith("12334_岗位说明书.PDF")


def test_200_files_two_types_and_correct_employee_ids(tmp_path):
    people = [(f"员工{i:03d}", f"{i:05d}") for i in range(100)]
    for name, _ in people:
        (tmp_path / f"岗位说明书_{name}.pdf").write_bytes(b"safe")
        (tmp_path / f"劳动合同协议_{name}.pdf").write_bytes(b"safe")
    settings = RenameSettings(
        folders=[str(tmp_path)],
        type_rules=[TypeRule("岗位说明书", "{参考值}_岗位说明书"),
                    TypeRule("劳动合同协议", "{参考值}_劳动合同协议")],
    )
    sources = [ReferenceSource("员工名单", [["姓名", "员工编号"], *[list(p) for p in people]],
                               "姓名", "员工编号")]
    plans = plan_renames(settings, sources)
    assert len(plans) == 200
    assert all(p.executable for p in plans)
    assert {Path(p.proposed).name for p in plans} == {
        f"{num}_{kind}.pdf" for _name, num in people for kind in ("岗位说明书", "劳动合同协议")
    }
