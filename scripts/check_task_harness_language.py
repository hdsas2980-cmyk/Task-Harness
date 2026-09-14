#!/usr/bin/env python3
"""只读中文文件契约校验。仅检查结构与语言最低条件，不判定任务完成。"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from harness_db import HarnessDB, find_db_path

FILES = ("tasks.json", "evidence.jsonl", "reviews.jsonl", "progress.txt")
STATES = {"pending", "active", "evidence_ready", "passed", "blocked", "regressed"}
CJK = re.compile(r"[\u3400-\u9fff]")
PLACEHOLDER = re.compile(r"\{\{.*?\}\}|^<[^>]+>$")
PROTOCOL = re.compile(r"(?:HARNESS_STATUS: \S+ (?:IN_PROGRESS|COMPLETE|BLOCKED)|PROGRESS: \d+/\d+|EXIT_SIGNAL: (?:false|true))$")
MACHINE_PROGRESS = re.compile(
    r"^(?:TASK_ID|EVENT_ID|AGENT_ID|THREAD_ID|CLIENT_THREAD_ID|HOST_ID|SESSION_ID|"
    r"REV|SHA-?256|SHA|COMMIT|CMD|PATH|FILE|URL|WORKDIR|BASELINE|SOURCE_REVISION|"
    r"EXIT_CODE|EXIT|NATIVE_RECEIPT)\s*[:：]\s*\S+",
    re.I,
)
MACHINE_LINE = re.compile(r"^(?:[0-9a-fA-F]{7,64}|https?://\S+|[A-Za-z]:\\[^\s]+|/(?:[^\s/]+/)*[^\s/]+)$")
REVIEW_LINE = re.compile(r"^HARNESS_REVIEW:\s*(pass|fail)\s*\|\s*(\S+)\s*\|\s*(.*)$", re.I)
PROSE_LABELS = {"目标", "技术栈", "进展", "状态", "原因", "下一步", "验证结论", "评审结论", "规格评审结论"}


def _snippet(value) -> str:
    text = " ".join(str(value or "").split())
    return text[:80] if text else "<empty>"


def _payloads(rows):
    result = []
    for row in rows or []:
        if not isinstance(row, dict):
            result.append(row)
            continue
        payload = dict(row.get("payload") or row)
        payload.pop("payload", None)
        result.append(payload)
    return result


def snapshot_to_files(snapshot: dict) -> dict[str, str]:
    meta = dict(snapshot.get("meta") or {})
    meta.pop("schema_version", None)
    board = meta.pop("board", None)
    tasks_doc = dict(meta)
    tasks_doc["tasks"] = _payloads(snapshot.get("tasks"))
    files = {
        "tasks.json": json.dumps(tasks_doc, ensure_ascii=False),
        "evidence.jsonl": "\n".join(json.dumps(row, ensure_ascii=False) for row in _payloads(snapshot.get("evidence")) if isinstance(row, dict)),
        "reviews.jsonl": "\n".join(json.dumps(row, ensure_ascii=False) for row in _payloads(snapshot.get("reviews")) if isinstance(row, dict)),
        "progress.txt": snapshot.get("progress") or "",
    }
    if isinstance(board, dict):
        files["board.json"] = json.dumps(board, ensure_ascii=False)
    return files


def validate_snapshot(snapshot: dict, *, templates: bool = False, extra_files: dict[str, str] | None = None) -> dict:
    files = snapshot_to_files(snapshot)
    if extra_files:
        files.update(extra_files)
    return validate_files(files, templates=templates)


def validate_progress_fragment(text: str, *, templates: bool = False) -> list[str]:
    files = {
        "tasks.json": json.dumps({"project": "写入门禁", "description": "仅校验进度片段", "tasks": []}, ensure_ascii=False),
        "evidence.jsonl": "",
        "reviews.jsonl": "",
        "progress.txt": text or "",
    }
    result = validate_files(files, templates=templates, require_progress_narrative=False)
    return [error for error in result["errors"] if error.startswith("progress.txt")]


def validate_task_payload(task: dict, *, templates: bool = False) -> list[str]:
    files = {
        "tasks.json": json.dumps({"project": "写入门禁", "description": "仅校验任务字段", "tasks": [task]}, ensure_ascii=False),
        "evidence.jsonl": "",
        "reviews.jsonl": "",
        "progress.txt": "## 2026-01-01 | write-gate | 执行\n- 进展：占位",
    }
    result = validate_files(files, templates=templates)
    return [error for error in result["errors"] if error.startswith("tasks.json.tasks[0]")]


def validate_record_payload(kind: str, row: dict, *, templates: bool = False) -> list[str]:
    encoded = json.dumps(row, ensure_ascii=False)
    files = {
        "tasks.json": json.dumps({"project": "写入门禁", "description": "仅校验记录字段", "tasks": []}, ensure_ascii=False),
        "evidence.jsonl": encoded if kind == "evidence" else "",
        "reviews.jsonl": encoded if kind == "reviews" else "",
        "progress.txt": "## 2026-01-01 | write-gate | 执行\n- 进展：占位",
    }
    result = validate_files(files, templates=templates)
    prefix = "evidence.jsonl" if kind == "evidence" else "reviews.jsonl"
    return [error for error in result["errors"] if error.startswith(prefix)]


def raise_language_errors(errors: list[str]) -> None:
    if errors:
        raise ValueError("中文契约失败：\n" + "\n".join(errors))


def validate_files(files: dict[str, str], *, templates: bool = False, require_progress_narrative: bool = True) -> dict:
    """供命令行、只读看板和写入门禁共用；files 为文件名到 UTF-8 文本的映射。"""
    errors: list[str] = []
    counts = {"tasks": 0, "evidence": 0, "reviews": 0}

    def prose(value, location):
        if not isinstance(value, str) or not value.strip() or not CJK.search(value):
            errors.append(
                f"{location}：必须是非空中文说明字符串；ID、命令、路径、SHA、退出码等机器字段可保留原文，但结论/原因/下一步必须写中文（摘录：{_snippet(value)}）"
            )
        elif not templates and PLACEHOLDER.search(value.strip()):
            errors.append(f"{location}：必须替换模板占位符")

    def forbidden(value, location):
        if isinstance(value, dict):
            for key, item in value.items():
                if key.endswith("_zh"):
                    errors.append(f"{location}.{key}：禁止旁挂翻译字段，请直接填写原字段")
                forbidden(item, f"{location}.{key}")
        elif isinstance(value, list):
            for i, item in enumerate(value):
                forbidden(item, f"{location}[{i}]")

    def parse(text, location):
        try:
            value = json.loads(text.lstrip("\ufeff"))
        except (json.JSONDecodeError, ValueError) as exc:
            errors.append(f"{location}：JSON 格式错误（{exc}）")
            return None
        forbidden(value, location)
        if not isinstance(value, dict):
            errors.append(f"{location}：必须为 JSON 对象")
            return None
        return value

    for name in FILES:
        if name not in files:
            errors.append(f"{name}：缺少契约文件；无记录的证据/评审文件可以为空")
    if "board.i18n.json" in files:
        errors.append("board.i18n.json：禁止看板翻译文件，请在任务原字段写中文")

    tasks = parse(files.get("tasks.json", "{}"), "tasks.json")
    ids: set[str] = set()

    def task(value, location, child=False):
        if not isinstance(value, dict):
            errors.append(f"{location}：任务必须是对象，bundle 不接受 ID 字符串数组")
            return
        identifier = value.get("id")
        if not isinstance(identifier, str) or not identifier.strip() or identifier in ids:
            errors.append(f"{location}.id：任务编号必须为非空、不重复的字符串")
        else:
            ids.add(identifier)
        for key in ("desc",) if child else ("name", "desc", "reason", "next"):
            prose(value.get(key), f"{location}.{key}")
        for key in ("name", "reason", "next") if child else ():
            if key in value:
                prose(value[key], f"{location}.{key}")
        if (not child or "status" in value) and (not isinstance(value.get("status"), str) or value["status"] not in STATES):
            errors.append(f"{location}.status：必须使用规定的英文状态枚举")
        if child and (not isinstance(value.get("verify"), str) or not value["verify"].strip()):
            errors.append(f"{location}.verify：束内任务必须提供非空验证命令字符串")
        for key in ("wave", "title", "description"):
            if key in value:
                prose(value[key], f"{location}.{key}")
        if "phase" in value and not isinstance(value["phase"], (int, float)):
            prose(value["phase"], f"{location}.phase")
        if "bundle" in value:
            if not isinstance(value["bundle"], list) or not value["bundle"]:
                errors.append(f"{location}.bundle：必须为非空任务对象数组")
            else:
                for i, member in enumerate(value["bundle"]):
                    task(member, f"{location}.bundle[{i}]", child=True)

    if tasks is not None:
        for key in ("project", "description"):
            prose(tasks.get(key), f"tasks.json.{key}")
        rows = tasks.get("tasks")
        if not isinstance(rows, list):
            errors.append("tasks.json.tasks：必须为任务数组，不能省略")
        else:
            counts["tasks"] = len(rows)
            for i, row in enumerate(rows):
                task(row, f"tasks.json.tasks[{i}]")

    for filename, field, counter in (("evidence.jsonl", "summary", "evidence"), ("reviews.jsonl", "reason", "reviews")):
        for number, line in enumerate(files.get(filename, "").lstrip("\ufeff").splitlines(), 1):
            if not line.strip():
                continue
            location = f"{filename}:{number}"
            row = parse(line, location)
            if row is None:
                continue
            if "_comment" in row:
                if set(row) != {"_comment"}:
                    errors.append(f"{location}：注释必须是仅含 _comment 的对象，不能混入业务记录")
                else:
                    prose(row["_comment"], f"{location}._comment")
                continue
            counts[counter] += 1
            prose(row.get(field), f"{location}.{field}")

    progress = files.get("progress.txt", "").lstrip("\ufeff")
    narrative = 0
    fence = None
    for number, raw in enumerate(progress.splitlines(), 1):
        line = raw.strip()
        location = f"progress.txt:{number}"
        if line.startswith(("```", "~~~")):
            marker = line[:3]
            if fence is None:
                fence = marker
            elif line.startswith(fence):
                fence = None
            continue
        if fence or not line or re.fullmatch(r"[-=*_\s]+", line) or PROTOCOL.fullmatch(line):
            continue
        if MACHINE_PROGRESS.fullmatch(line) or MACHINE_LINE.fullmatch(line):
            continue
        review = REVIEW_LINE.fullmatch(line)
        if review:
            narrative += 1
            prose(review.group(3).strip(), location)
            continue
        narrative += 1
        content = re.sub(r"^[#*\-\s]+", "", line)
        pair = re.split(r"[：:]", content, maxsplit=1)
        if len(pair) == 2 and pair[0].strip() in PROSE_LABELS:
            prose(pair[1].strip(), location)
        else:
            prose(content, location)
    if fence:
        errors.append("progress.txt：命令代码围栏未闭合")
    if require_progress_narrative and not narrative:
        errors.append("progress.txt：必须包含至少一条非空中文进度叙事；机器回执只能使用协议行或明确机器前缀，不能替代中文结论/原因/下一步")

    if "board.json" in files:
        board = parse(files["board.json"], "board.json")
        def map_prose(value, location):
            if isinstance(value, dict):
                for key, item in value.items():
                    if key in {"where", "what", "why", "see", "problem", "name", "desc", "description"} and not isinstance(item, (dict, list)):
                        prose(item, f"{location}.{key}")
                    map_prose(item, f"{location}.{key}")
            elif isinstance(value, list):
                for i, item in enumerate(value):
                    map_prose(item, f"{location}[{i}]")
        map_prose(board, "board.json")
    return {"errors": errors, "counts": counts}


def main(argv=None):
    parser = argparse.ArgumentParser(description="只读检查 harness.db 中文契约；不翻译、不改库、不判定完成。--templates 仅用于技能种子 JSON。")
    parser.add_argument("root", nargs="?", default=".", help="项目根目录或任务文件目录")
    parser.add_argument("--templates", action="store_true", help="仅维护技能模板时允许占位符；任务交付禁止使用")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    harness = root / ".harness" if (root / ".harness").is_dir() else root
    try:
        extra = {name: "" for name in ("board.i18n.json",) if (harness / name).is_file() or (root / name).is_file()}
        if args.templates:
            source = harness if (harness / "tasks.json").is_file() else root
            files = {name: (source / name).read_text(encoding="utf-8-sig")
                     for name in (*FILES, "board.json", "board.i18n.json") if (source / name).is_file()}
            files.update(extra)
            result = validate_files(files, templates=True)
        else:
            db_path = find_db_path(root)
            if db_path is None:
                expected = harness / "harness.db"
                print(f"未初始化 {expected}，禁止回退 JSON/JSONL/TXT。旧项目先运行 scripts/convert_harness_json.py 一次性导入。", file=sys.stderr)
                return 2
            with HarnessDB(db_path, create=False) as db:
                snapshot = db.read_snapshot()
            result = validate_snapshot(snapshot, extra_files=extra)
    except (OSError, UnicodeError, RecursionError, ValueError) as exc:
        print(f"无法校验任务目录 {root}：{exc}", file=sys.stderr)
        return 2
    if result["errors"]:
        print("\n".join(result["errors"]), file=sys.stderr)
        return 1
    count = result["counts"]
    mode = "模板检查" if args.templates else "中文契约检查"
    print(f"{mode}通过：任务 {count['tasks']}，证据 {count['evidence']}，评审 {count['reviews']}。")
    print("仅确认结构与中文最低条件；不代表内容准确、验证成功或独立评审通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
