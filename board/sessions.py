#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read Codex session jsonl and map cwd -> harness directory. Read-only."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

MAX_FIRST_LINE = 256 * 1024
MAX_TAIL = 64 * 1024
BACKUP_DIR = "__backups__"


def sessions_dir() -> Path:
    env = os.environ.get("CODEX_SESSIONS_DIR")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".codex" / "sessions"


def resolve_source(project: Path, must_exist: bool = True) -> Path:
    target = project.expanduser()
    try:
        target = target.resolve()
    except OSError:
        target = Path(os.path.normpath(str(target)))
    if must_exist and not target.exists():
        raise ValueError("项目目录不存在: " + str(target))
    if target.is_file():
        target = target.parent
    if target.name == ".harness":
        return target
    nested = target / ".harness"
    if (nested / "tasks.json").is_file() or not (target / "tasks.json").is_file():
        return nested
    return target


def cwd_key(cwd: str) -> str:
    return os.path.normcase(os.path.normpath(str(cwd).strip().rstrip("\\/")))


def walk_session_files(root: Path):
    if not root.is_dir():
        return
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            name
            for name in dirnames
            if name != BACKUP_DIR and not name.startswith("__backup_")
        ]
        for name in filenames:
            if name.endswith(".jsonl"):
                yield Path(dirpath) / name


def _first_line(path: Path) -> str:
    with path.open("rb") as fh:
        data = fh.read(MAX_FIRST_LINE)
    if b"\n" in data:
        data = data.split(b"\n", 1)[0]
    return data.decode("utf-8-sig", errors="replace").strip()


def parse_session_meta(path: Path) -> dict | None:
    try:
        line = _first_line(path)
        if not line:
            return None
        record = json.loads(line)
    except Exception:
        return None
    if not isinstance(record, dict):
        return None
    payload = record.get("payload") if isinstance(record.get("payload"), dict) else None
    if record.get("type") == "session_meta" and payload is not None:
        meta = dict(payload)
    elif payload is not None and payload.get("cwd"):
        meta = dict(payload)
    else:
        return None
    if not meta.get("id") and meta.get("session_id"):
        meta["id"] = meta["session_id"]
    if not meta.get("timestamp"):
        meta["timestamp"] = record.get("timestamp") or ""
    if not meta.get("cwd"):
        meta["cwd"] = extract_tail_cwd(path)
    return meta


def extract_tail_cwd(path: Path) -> str:
    try:
        size = path.stat().st_size
        with path.open("rb") as fh:
            if size > MAX_TAIL:
                fh.seek(size - MAX_TAIL)
            chunk = fh.read()
        text = chunk.decode("utf-8", errors="replace")
        lines = text.splitlines()
        if size > MAX_TAIL and lines:
            lines = lines[1:]
        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except Exception:
                continue
            if not isinstance(record, dict):
                continue
            payload = record.get("payload") if isinstance(record.get("payload"), dict) else record
            cwd = ""
            if isinstance(payload, dict):
                cwd = str(payload.get("cwd") or "").strip()
            if cwd and record.get("type") in ("turn_context", "session_meta", "event_msg", None):
                return cwd
        return ""
    except OSError:
        return ""


def load_titles(root: Path) -> dict[str, str]:
    index = root.parent / "session_index.jsonl"
    titles: dict[str, str] = {}
    if not index.is_file():
        return titles
    try:
        raw = index.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return titles
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if not isinstance(row, dict):
            continue
        sid = str(row.get("id") or "").strip()
        name = str(row.get("thread_name") or row.get("title") or "").strip()
        if sid and name:
            titles[sid] = name
    return titles


def probe_harness(cwd: str) -> dict:
    info = {
        "cwd": cwd,
        "cwd_exists": False,
        "has_harness": False,
        "source": None,
        "tasks_file": None,
        "project_name": None,
        "task_count": None,
    }
    if not cwd:
        return info
    target = Path(cwd).expanduser()
    info["cwd_exists"] = target.exists()
    if not target.exists():
        nested = target / ".harness" if target.name != ".harness" else target
        info["source"] = str(nested)
        return info
    try:
        source = resolve_source(target, must_exist=True)
    except ValueError:
        return info
    info["source"] = str(source)
    tasks = source / "tasks.json"
    if tasks.is_file():
        info["has_harness"] = True
        info["tasks_file"] = str(tasks)
        name, count = _task_meta(tasks)
        info["project_name"] = name
        info["task_count"] = count
    return info


def _task_meta(tasks_file: Path) -> tuple[str | None, int | None]:
    try:
        data = json.loads(tasks_file.read_text(encoding="utf-8-sig"))
    except Exception:
        return None, None
    if not isinstance(data, dict):
        return None, None
    name = data.get("project")
    tasks = data.get("tasks")
    count = len(tasks) if isinstance(tasks, list) else None
    return (str(name) if name else None), count


def _iso_mtime(path: Path) -> str:
    try:
        ts = path.stat().st_mtime
    except OSError:
        return ""
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def list_session_catalog(current_source: Path | None = None, root: Path | None = None) -> dict:
    root = root or sessions_dir()
    titles = load_titles(root)
    groups: dict[str, dict] = {}
    scanned = 0
    skipped = 0
    for path in walk_session_files(root):
        scanned += 1
        meta = parse_session_meta(path)
        if not meta:
            skipped += 1
            continue
        cwd = str(meta.get("cwd") or "").strip()
        sid = str(meta.get("id") or "").strip()
        timestamp = str(meta.get("timestamp") or "")
        mtime = _iso_mtime(path)
        latest = max(timestamp, mtime)
        title = titles.get(sid) or Path(cwd).name or sid or path.stem
        rel = str(path.relative_to(root)) if root in path.parents or path.parent == root else str(path)
        key = cwd_key(cwd) if cwd else ("session:" + (sid or path.name))
        group = groups.get(key)
        if group is None:
            probe = probe_harness(cwd) if cwd else {
                "cwd": "",
                "cwd_exists": False,
                "has_harness": False,
                "source": None,
                "tasks_file": None,
                "project_name": None,
                "task_count": None,
            }
            group = {
                **probe,
                "cwd": cwd,
                "latest": latest,
                "session_count": 0,
                "sessions": [],
            }
            groups[key] = group
        session = {
            "id": sid,
            "title": title,
            "timestamp": timestamp or mtime,
            "mtime": mtime,
            "cwd": cwd,
            "file": rel,
        }
        group["sessions"].append(session)
        group["session_count"] += 1
        if latest > str(group.get("latest") or ""):
            group["latest"] = latest
            if title:
                group["latest_title"] = title
        elif not group.get("latest_title") and title:
            group["latest_title"] = title
        if not group.get("project_name"):
            group["project_name"] = Path(cwd).name if cwd else None

    projects = list(groups.values())
    for project in projects:
        project["sessions"].sort(
            key=lambda row: str(row.get("timestamp") or ""),
            reverse=True,
        )
        if project["sessions"] and not project.get("latest_title"):
            project["latest_title"] = project["sessions"][0].get("title")
    projects.sort(key=lambda row: str(row.get("cwd") or ""))
    projects.sort(key=lambda row: 0 if row.get("has_harness") else 1)
    projects.sort(key=lambda row: str(row.get("latest") or ""), reverse=True)

    suggested = _suggest(projects, current_source)
    current = str(current_source) if current_source else None
    return {
        "sessions_dir": str(root),
        "source": current,
        "scanned": scanned,
        "skipped": skipped,
        "suggested": suggested,
        "projects": projects,
    }


def _suggest(projects: list[dict], current_source: Path | None) -> dict | None:
    ready = [row for row in projects if row.get("has_harness") and row.get("cwd_exists")]
    if not ready:
        return None
    newest = max(projects, key=lambda row: str(row.get("latest") or ""))
    if newest and newest.get("has_harness") and newest.get("cwd_exists"):
        return {
            "cwd": newest.get("cwd"),
            "source": newest.get("source"),
            "title": newest.get("latest_title") or newest.get("project_name"),
            "reason": "latest_session",
        }
    if len(ready) == 1:
        row = ready[0]
        return {
            "cwd": row.get("cwd"),
            "source": row.get("source"),
            "title": row.get("latest_title") or row.get("project_name"),
            "reason": "single_harness",
        }
    return None
