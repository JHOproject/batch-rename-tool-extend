"""Pure-Python rename planner and guarded executor (no GUI dependencies)."""
from __future__ import annotations

from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import string
import uuid
from typing import Any


@dataclass
class ReferenceSource:
    name: str
    grid: list[list[str]]  # First row is the header, like an Excel worksheet.
    match_field: str = ""
    output_field: str = ""

    @property
    def headers(self) -> list[str]:
        return [str(x).strip() for x in (self.grid[0] if self.grid else [])]

    def validate(self) -> list[str]:
        errors = []
        headers = self.headers
        active = [h for h in headers if h]
        if not active:
            return [f"「{self.name}」没有字段名称"]
        if len(set(active)) != len(active):
            errors.append(f"「{self.name}」有重复的字段名称")
        for label, name in [("匹配", self.match_field), ("输出", self.output_field)]:
            if not name or name not in headers:
                errors.append(f"「{self.name}」尚未设置有效的{label}字段")
        return errors

    def entries(self) -> list[dict[str, str]]:
        heads = self.headers
        result = []
        for values in self.grid[1:]:
            rec = {h: str(values[i]).strip() if i < len(values) else ""
                   for i, h in enumerate(heads) if h}
            if any(rec.values()):
                result.append(rec)
        return result


@dataclass
class TypeRule:
    """Choose a filename template by an identifying substring in the original stem."""
    keyword: str
    template: str


@dataclass
class RenameSettings:
    folders: list[str] = field(default_factory=list)
    recursive: bool = False
    match_mode: str = "segment"  # segment / contains
    delimiter: str = "_"
    template: str = "{参考值}_{移除匹配值后的原文件名}"
    type_rules: list[TypeRule] = field(default_factory=list)


@dataclass
class PlannedFile:
    original: str
    proposed: str
    status: str
    detail: str = ""
    source: str = ""
    size: int = 0
    mtime_ns: int = 0
    rule: str = ""  # Filename-type keyword, when multiple templates are in use.

    @property
    def executable(self) -> bool:
        return self.status == "可重命名"


ALLOWED_SPECIAL = {"参考值", "匹配值", "原文件名", "移除匹配值后的原文件名", "參照值", "比對值", "原檔名", "移除比對值後的原檔名"}
BAD_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
RESERVED = re.compile(r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?$", re.I)
FORMATTER = string.Formatter()


def template_fields(template: str) -> set[str]:
    fields: set[str] = set()
    try:
        parsed = list(FORMATTER.parse(template))
    except ValueError as exc:
        raise ValueError(f"文件名格式的大括号不完整：{exc}") from exc
    for _prefix, token, fmt, conversion in parsed:
        if token is None:
            continue
        if not token or any(ch in token for ch in ".[]") or fmt or conversion:
            raise ValueError("只支持 {字段名称}，不支持属性、索引或其他格式运算")
        fields.add(token)
    return fields


def valid_filename(name: str) -> str | None:
    if not name or name in {".", ".."}:
        return "新文件名不可留空"
    if BAD_CHARS.search(name):
        return "文件名含有 Windows 不允许的字符"
    if name.endswith((" ", ".")):
        return "文件名不可用空格或句号结尾"
    if RESERVED.match(name.split(".")[0]):
        return "文件名使用了 Windows 保留名称"
    if len(name.encode("utf-16-le")) // 2 > 240:
        return "文件名太长（超过 240 个 UTF-16 字符）"
    return None


def remove_match(stem: str, value: str, settings: RenameSettings) -> str:
    if settings.match_mode == "segment":
        return settings.delimiter.join([seg for seg in stem.split(settings.delimiter)
                                        if seg.strip() != value]).strip(" _-")
    # Remove only the matched string; collapse separators introduced by removal.
    return re.sub(r"([_\-])\1+", r"\1", stem.replace(value, "")).strip(" _-")


def find_target_files(settings: RenameSettings) -> list[Path]:
    found: dict[str, Path] = {}
    for folder in settings.folders:
        root = Path(folder).expanduser()
        if not root.is_dir():
            raise ValueError(f"文件夹不存在：{root}")
        iterator = root.rglob("*") if settings.recursive else root.iterdir()
        for path in iterator:
            if path.is_file() and not path.is_symlink():
                key = os.path.abspath(str(path)).casefold()
                found[key] = path
    return sorted(found.values(), key=lambda path: str(path).casefold())


def _match(stem: str, value: str, settings: RenameSettings) -> bool:
    if not value:
        return False
    if settings.match_mode == "segment":
        if not settings.delimiter:
            raise ValueError("分段匹配必须设置分隔符")
        return value in (part.strip() for part in stem.split(settings.delimiter))
    if settings.match_mode == "contains":
        return value in stem
    raise ValueError("未知的匹配方式")


def plan_renames(settings: RenameSettings, sources: list[ReferenceSource]) -> list[PlannedFile]:
    if not sources:
        raise ValueError("请先添加至少一份参考资料表")
    if settings.match_mode == "segment" and not settings.delimiter:
        raise ValueError("请输入文件名分隔符")
    all_fields = set(ALLOWED_SPECIAL)
    for src in sources:
        problems = src.validate()
        if problems:
            raise ValueError("；".join(problems))
        all_fields.update(src.headers)
    # With no type-specific rules, the legacy global template is used unchanged.
    # When rules exist, only files matching exactly one filename keyword are eligible.
    rules = settings.type_rules
    templates = [rule.template for rule in rules] if rules else [settings.template]
    normalized_keywords: set[str] = set()
    for index, rule in enumerate(rules, start=1):
        key = rule.keyword.strip()
        if not key:
            raise ValueError(f"第 {index} 条类型规则的关键字不可留空")
        if key.casefold() in normalized_keywords:
            raise ValueError(f"文件类型关键字重复：{key}")
        normalized_keywords.add(key.casefold())
    for index, template in enumerate(templates, start=1):
        if not template.strip():
            label = f"第 {index} 条类型规则" if rules else "命名规则"
            raise ValueError(f"{label}的新文件名格式不可留空")
        fields = template_fields(template)
        invalid_tokens = fields - all_fields
        if invalid_tokens:
            label = f"第 {index} 条类型规则" if rules else "命名规则"
            raise ValueError(f"{label}使用了未知字段：" + "、".join(sorted(invalid_tokens)))

    indexed: list[tuple[str, ReferenceSource, dict[str, str]]] = []
    for src in sources:
        for record in src.entries():
            val = record.get(src.match_field, "").strip()
            if val:
                indexed.append((val, src, record))
    plans: list[PlannedFile] = []
    for path in find_target_files(settings):
        st = path.stat()
        base = dict(original=str(path), proposed="", size=st.st_size,
                    mtime_ns=st.st_mtime_ns)
        if rules:
            applicable = [rule for rule in rules if rule.keyword.strip().casefold() in path.stem.casefold()]
            if not applicable:
                plans.append(PlannedFile(**base, status="未匹配", detail="文件名未命中任何类型关键字（已跳过）"))
                continue
            if len(applicable) > 1:
                names = "、".join(rule.keyword.strip() for rule in applicable)
                plans.append(PlannedFile(**base, status="多项匹配", detail=f"同时命中多个类型关键字：{names}（已跳过）"))
                continue
            selected_template = applicable[0].template
            base["rule"] = applicable[0].keyword.strip()
        else:
            selected_template = settings.template
        fields = template_fields(selected_template)
        matched = [(val, src, rec) for val, src, rec in indexed
                   if _match(path.stem, val, settings)]
        if not matched:
            plans.append(PlannedFile(**base, status="未匹配", detail="文件名找不到对应的参考资料"))
            continue
        names: dict[str, list[str]] = {}
        invalid: list[str] = []
        for val, src, rec in matched:
            out_val = rec.get(src.output_field, "")
            if not out_val:
                invalid.append(f"{src.name} 的输出字段没有资料")
                continue
            values = dict(rec)
            values.update({"参考值": out_val, "匹配值": val, "原文件名": path.stem,
                           "移除匹配值后的原文件名": remove_match(path.stem, val, settings),
                           "參照值": out_val, "比對值": val, "原檔名": path.stem,
                           "移除比對值後的原檔名": remove_match(path.stem, val, settings)})
            absent = fields - values.keys()
            if absent:
                invalid.append(f"{src.name} 缺少字段：{'、'.join(sorted(absent))}")
                continue
            stem = FORMATTER.vformat(selected_template, (), values)
            if not stem:
                invalid.append("新文件名是空白的")
                continue
            dest_name = stem + path.suffix  # Extension is never changed by a rule.
            err = valid_filename(dest_name)
            if err:
                invalid.append(err)
                continue
            names.setdefault(dest_name, []).append(src.name)
        if invalid:
            plans.append(PlannedFile(**base, status="字段或文件名无效", detail="；".join(dict.fromkeys(invalid))))
        elif len(names) != 1:
            plans.append(PlannedFile(**base, status="多项匹配", detail="参考资料产生了多个不同的文件名"))
        else:
            dest_name, srcs = next(iter(names.items()))
            dest = path.with_name(dest_name)
            plans.append(PlannedFile(**{**base, "proposed": str(dest),
                                        "status": "无需更改" if dest_name == path.name else "可重命名",
                                        "source": "、".join(sorted(set(srcs)))}))

    destinations: dict[str, list[PlannedFile]] = {}
    for p in plans:
        if p.executable:
            destinations.setdefault(os.path.abspath(p.proposed).casefold(), []).append(p)
    for ps in destinations.values():
        if len(ps) > 1:
            for p in ps:
                p.status = "文件名冲突"
                p.detail = "多个文件会产生相同的新文件名"
    for p in plans:
        if p.executable and Path(p.proposed).exists():
            p.status = "文件名冲突"
            p.detail = "目标文件已存在，不会覆盖"
    return plans


def _same_stat(path: Path, size: int, mtime_ns: int) -> bool:
    try:
        stat = path.stat()
        return stat.st_size == size and stat.st_mtime_ns == mtime_ns
    except OSError:
        return False


def app_data_dir() -> Path:
    base = Path(os.getenv("APPDATA") or Path.home() / ".batchrename")
    path = base / "BatchRenameTool" if os.getenv("APPDATA") else base
    path.mkdir(parents=True, exist_ok=True)
    return path


def _atomic_write(path: Path, data: dict[str, Any]):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + f".{uuid.uuid4().hex}.tmp")
    try:
        with temp.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def execute_plan(plans: list[PlannedFile], history_path: Path | None = None) -> tuple[int, list[str]]:
    """Execute only validated rows. Never overwrite, log successful renames."""
    history_path = history_path or (app_data_dir() / "history.json")
    history: dict[str, Any] = {"transactions": []}
    if history_path.exists():
        history = json.loads(history_path.read_text(encoding="utf-8"))
    tx = {"id": uuid.uuid4().hex, "time": datetime.now(timezone.utc).isoformat(),
          "entries": []}
    history["transactions"].append(tx)
    _atomic_write(history_path, history)
    errors: list[str] = []
    for p in plans:
        if not p.executable:
            continue
        source, dest = Path(p.original), Path(p.proposed)
        if not _same_stat(source, p.size, p.mtime_ns):
            errors.append(f"原文件已更改或不存在：{source}")
            continue
        if dest.exists() or dest.is_symlink():
            errors.append(f"目标文件已存在：{dest}")
            continue
        try:
            # On Windows rename fails instead of overwriting an existing destination.
            # The explicit check above prevents overwrites on POSIX during tests too.
            source.rename(dest)
            st = dest.stat()
            tx["entries"].append({"original": str(source), "new": str(dest),
                                  "size": st.st_size, "mtime_ns": st.st_mtime_ns,
                                  "undone": False})
            _atomic_write(history_path, history)  # Persist after *each* successful rename.
        except OSError as exc:
            errors.append(f"{source.name}：{exc}")
    return len(tx["entries"]), errors


def undo_latest(history_path: Path | None = None) -> tuple[int, list[str]]:
    history_path = history_path or (app_data_dir() / "history.json")
    if not history_path.exists():
        return 0, ["找不到可恢复的操作记录"]
    history = json.loads(history_path.read_text(encoding="utf-8"))
    transactions = history.get("transactions", [])
    tx = next((x for x in reversed(transactions)
               if any(not e.get("undone") for e in x.get("entries", []))), None)
    if tx is None:
        return 0, ["没有尚未恢复的重命名记录"]
    count, errors = 0, []
    for entry in reversed(tx["entries"]):
        if entry.get("undone"):
            continue
        src, dst = Path(entry["new"]), Path(entry["original"])
        if not _same_stat(src, entry["size"], entry["mtime_ns"]):
            errors.append(f"文件已更改，已跳过：{src}")
            continue
        if dst.exists() or dst.is_symlink():
            errors.append(f"原文件名已存在，已跳过：{dst}")
            continue
        try:
            src.rename(dst)
            entry["undone"] = True
            count += 1
            _atomic_write(history_path, history)
        except OSError as exc:
            errors.append(f"{src.name}：{exc}")
    return count, errors


def save_project(path: Path, settings: RenameSettings, sources: list[ReferenceSource]):
    _atomic_write(path, {"version": 1, "settings": asdict(settings),
                         "sources": [asdict(s) for s in sources]})


def load_project(path: Path) -> tuple[RenameSettings, list[ReferenceSource]]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if obj.get("version") != 1:
        raise ValueError("不支持的项目版本")
    settings_data = dict(obj["settings"])
    settings_data["type_rules"] = [TypeRule(**x) for x in settings_data.get("type_rules", [])]
    settings = RenameSettings(**settings_data)
    sources = [ReferenceSource(**x) for x in obj["sources"]]
    return settings, sources
