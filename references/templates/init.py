#!/usr/bin/env python3
"""Compact harness status. Does not modify task files."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def resolve_source(project: Path) -> Path:
    target = project.expanduser().resolve()
    if target.name == ".harness":
        return target
    output = target / ".harness"
    if (output / "tasks.json").exists() or not (target / "tasks.json").exists():
        return output
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Print compact task-harness status")
    parser.add_argument("--project", "-p", default=".", help="Project root or .harness directory")
    parser.add_argument("project_positional", nargs="?", help="Optional project path")
    args = parser.parse_args(argv)
    project = Path(args.project_positional or args.project)
    source = resolve_source(project)
    path = source / "tasks.json"
    if not path.is_file():
        print("tasks.json 不存在，先进入相 1 设计。")
        print("EXIT_SIGNAL: false  (完成门禁须由独立评审确认)")
        return 0
    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        print("任务文件无法解析。")
        print("EXIT_SIGNAL: false  (完成门禁须由独立评审确认)")
        return 1
    tasks = raw.get("tasks")
    if not isinstance(raw, dict) or not isinstance(tasks, list):
        print("任务文件结构无效。")
        return 1
    by_id = {t["id"]: t for t in tasks if isinstance(t, dict) and isinstance(t.get("id"), str)}
    passed = [t for t in tasks if isinstance(t, dict) and t.get("status") == "passed"]
    print(f"PROGRESS: {len(passed)}/{len(tasks)}  rev={raw.get('rev', 1)}")
    ready = [t for t in tasks if isinstance(t, dict) and t.get("status") == "evidence_ready"]
    if ready:
        print("待评审 (按 references/review/completion-review.md 独立评审): " + ", ".join(str(t.get("id")) for t in ready))
    blocked = [t for t in tasks if isinstance(t, dict) and t.get("status") == "blocked"]
    if blocked:
        print("阻塞: " + ", ".join(str(t.get("id")) for t in blocked))

    def deps_ok(task: dict) -> bool:
        deps = task.get("depends_on", [])
        if not isinstance(deps, list):
            return False
        return all(by_id.get(dep, {}).get("status") == "passed" for dep in deps if isinstance(dep, str))

    elig = [t for t in tasks if isinstance(t, dict) and t.get("status") in ("pending", "regressed") and deps_ok(t)]

    def prio(task: dict) -> float:
        try:
            value = float(task.get("priority", 999999))
        except (TypeError, ValueError):
            return 999999.0
        return value if value == value else 999999.0

    elig.sort(key=prio)
    if tasks and len(passed) == len(tasks):
        print("EXIT_SIGNAL: true  — 全部任务状态为已通过。")
        print("注意: passed 须有对应 evidence 与独立 pass review，声明不等于门禁完成。")
    elif elig:
        task = elig[0]
        print()
        print("下一个任务 (置 active):")
        print(f"  [{task.get('id')}] P{task.get('priority')}: {task.get('desc')}")
        print(f"  verify: {task.get('verify')}")
        deps = task.get("depends_on") or []
        if deps:
            print(f"  depends_on: {', '.join(map(str, deps))} (已满足)")
        print("EXIT_SIGNAL: false  (完成门禁须由独立评审确认)")
    else:
        print()
        print("无 eligible 任务：均处于评审中/阻塞/依赖未满足。先处理上面列出的项。")
        print("EXIT_SIGNAL: false  (完成门禁须由独立评审确认)")
    print()
    print("提醒: 只推进这一个任务；完成后追加 evidence.jsonl 并置 evidence_ready；结尾输出 HARNESS_STATUS 块。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
