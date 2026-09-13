"""SQLite-only storage for Task Harness state.

Live reads and writes go to .harness/harness.db. JSON/JSONL/TXT files are not a
runtime store. Convert old files once with convert_legacy() or
scripts/convert_harness_json.py, then keep the old files only as read-only
backups.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable

SCHEMA_VERSION = 1
DB_NAME = "harness.db"
LEGACY_TASKS = "tasks.json"
LEGACY_EVIDENCE = "evidence.jsonl"
LEGACY_REVIEWS = "reviews.jsonl"
LEGACY_PROGRESS = "progress.txt"
LEGACY_BOARD = "board.json"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS evidence (
    id TEXT PRIMARY KEY,
    task_id TEXT,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS reviews (
    id TEXT PRIMARY KEY,
    task_id TEXT,
    evidence_id TEXT,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS progress (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    content_hash TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_evidence_task_id ON evidence(task_id);
CREATE INDEX IF NOT EXISTS idx_reviews_task_id ON reviews(task_id);
CREATE INDEX IF NOT EXISTS idx_reviews_evidence_id ON reviews(evidence_id);
"""

_UNINITIALIZED = "\u672a\u521d\u59cb\u5316 {path}\uff0c\u7981\u6b62\u56de\u9000 JSON/JSONL/TXT"
_TASKS_OBJECT = "tasks.json \u9876\u5c42\u5fc5\u987b\u662f\u5bf9\u8c61"
_TASKS_ARRAY = "tasks.json \u7684 tasks \u5fc5\u987b\u662f\u5bf9\u8c61\u6570\u7ec4"
_JSON_READ = "\u65e0\u6cd5\u8bfb\u53d6 JSON \u6587\u4ef6: {path}: {exc}"
_JSONL_READ = "\u65e0\u6cd5\u8bfb\u53d6 JSONL \u6587\u4ef6: {path}:{line_no}: {exc}"
_JSONL_OBJECT = "JSONL \u8bb0\u5f55\u5fc5\u987b\u662f\u5bf9\u8c61: {path}:{line_no}"
_TASK_ID = "\u4efb\u52a1\u5fc5\u987b\u662f\u5e26\u975e\u7a7a id \u7684\u5bf9\u8c61"
_RECORD_OBJECT = "\u8bb0\u5f55\u5fc5\u987b\u662f\u5bf9\u8c61"
_PROGRESS_EMPTY = "\u8fdb\u5ea6\u4e0d\u80fd\u4e3a\u7a7a"
_EVIDENCE_DUP = "\u8bc1\u636e id \u5df2\u5b58\u5728: {row_id}"
_REVIEW_DUP = "\u8bc4\u5ba1 id \u5df2\u5b58\u5728: {row_id}"
_NO_LEGACY = "\u672a\u627e\u5230\u53ef\u5bfc\u5165\u7684 tasks.json\uff1a{source}\u3002\u8f6c\u6362\u811a\u672c\u53ea\u7528\u4e8e\u65e7 JSON \u4e00\u6b21\u6027\u5bfc\u5165\uff0c\u4e0d\u662f\u8fd0\u884c\u65f6\u56de\u9000\u3002"


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(_JSON_READ.format(path=path, exc=exc)) from exc


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(_JSONL_READ.format(path=path, line_no=line_no, exc=exc)) from exc
        if not isinstance(value, dict):
            raise ValueError(_JSONL_OBJECT.format(path=path, line_no=line_no))
        if set(value) == {"_comment"}:
            continue
        rows.append(value)
    return rows


def _stable_id(prefix: str, value: dict[str, Any]) -> str:
    return f"{prefix}-{hashlib.sha256(_json(value).encode('utf-8')).hexdigest()}"


def _record_payload(row: Any) -> dict[str, Any]:
    if not isinstance(row, dict):
        raise ValueError(_RECORD_OBJECT)
    data = dict(row)
    nested = data.pop("payload", None)
    if isinstance(nested, dict):
        payload = dict(nested)
        for key, value in data.items():
            payload[key] = value
        data = payload
    return data


def find_db_path(project_root: str | Path) -> Path | None:
    root = Path(project_root).expanduser()
    try:
        root = root.resolve()
    except OSError:
        root = Path(root)
    if root.is_file():
        return root if root.name == DB_NAME else None
    candidates = []
    if root.name == ".harness":
        candidates.append(root / DB_NAME)
    else:
        candidates.extend((root / ".harness" / DB_NAME, root / DB_NAME))
    for path in candidates:
        if path.is_file():
            return path
    return None


def expected_db_path(project_root: str | Path) -> Path:
    root = Path(project_root).expanduser()
    try:
        root = root.resolve()
    except OSError:
        root = Path(root)
    if root.is_file() and root.name == DB_NAME:
        return root
    if root.name == ".harness":
        return root / DB_NAME
    nested = root / ".harness" / DB_NAME
    if nested.is_file() or not (root / DB_NAME).is_file():
        return nested
    return root / DB_NAME


def resolve_legacy_dir(source: str | Path) -> Path:
    root = Path(source).expanduser()
    try:
        root = root.resolve()
    except OSError:
        root = Path(root)
    if root.is_file():
        root = root.parent
    if (root / ".harness" / LEGACY_TASKS).is_file():
        return root / ".harness"
    if (root / LEGACY_TASKS).is_file():
        return root
    raise ValueError(_NO_LEGACY.format(source=root))


class HarnessDB:
    """SQLite persistence boundary. Not a JSON compatibility layer."""

    def __init__(self, path: str | Path, *, create: bool = True):
        self.path = Path(path)
        if create:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._connection = sqlite3.connect(self.path)
            self._connection.row_factory = sqlite3.Row
            self._connection.execute("PRAGMA foreign_keys = ON")
            self._connection.execute("PRAGMA journal_mode = DELETE")
            self._connection.execute("PRAGMA synchronous = NORMAL")
            self.initialize()
            return
        if not self.path.is_file():
            raise FileNotFoundError(_UNINITIALIZED.format(path=self.path))
        self._connection = sqlite3.connect(f"file:{self.path.resolve().as_posix()}?mode=ro", uri=True)
        self._connection.row_factory = sqlite3.Row

    @classmethod
    def open(cls, project_root: str | Path, *, create: bool = True) -> "HarnessDB":
        existing = find_db_path(project_root)
        if existing is not None:
            return cls(existing, create=create)
        path = expected_db_path(project_root)
        if not create:
            raise FileNotFoundError(_UNINITIALIZED.format(path=path))
        return cls(path, create=True)

    def initialize(self) -> None:
        with self._connection:
            self._connection.executescript(_SCHEMA)
            self._connection.execute(
                "INSERT INTO meta(key, value_json) VALUES('schema_version', ?) "
                "ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json",
                (_json(SCHEMA_VERSION),),
            )

    def schema_version(self) -> int:
        row = self._connection.execute("SELECT value_json FROM meta WHERE key='schema_version'").fetchone()
        return int(json.loads(row[0])) if row else 0

    def set_meta(self, key: str, value: Any) -> None:
        if not str(key or "").strip() or key == "schema_version":
            raise ValueError("meta key \u65e0\u6548")
        with self._connection:
            self._connection.execute(
                "INSERT INTO meta(key, value_json) VALUES(?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json",
                (key, _json(value)),
            )

    def get_meta(self, key: str, default: Any = None) -> Any:
        row = self._connection.execute("SELECT value_json FROM meta WHERE key=?", (key,)).fetchone()
        return default if row is None else json.loads(row[0])

    def upsert_task(self, task: dict[str, Any]) -> str:
        payload = _record_payload(task)
        task_id = str(payload.get("id") or "").strip()
        if not task_id:
            raise ValueError(_TASK_ID)
        payload["id"] = task_id
        with self._connection:
            self._connection.execute(
                "INSERT INTO tasks(id, payload_json) VALUES(?, ?) "
                "ON CONFLICT(id) DO UPDATE SET payload_json=excluded.payload_json",
                (task_id, _json(payload)),
            )
        return task_id

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        row = self._connection.execute("SELECT id, payload_json FROM tasks WHERE id=?", (task_id,)).fetchone()
        if row is None:
            return None
        return _unpack_row(row)

    def append_evidence(self, row: dict[str, Any]) -> str:
        payload = _record_payload(row)
        row_id = str(payload.get("id") or "").strip() or _stable_id("evidence", payload)
        payload["id"] = row_id
        task_id = payload.get("task") or payload.get("task_id")
        try:
            with self._connection:
                self._connection.execute(
                    "INSERT INTO evidence(id, task_id, payload_json) VALUES(?, ?, ?)",
                    (row_id, task_id, _json(payload)),
                )
        except sqlite3.IntegrityError as exc:
            raise ValueError(_EVIDENCE_DUP.format(row_id=row_id)) from exc
        return row_id

    def append_review(self, row: dict[str, Any]) -> str:
        payload = _record_payload(row)
        row_id = str(payload.get("id") or "").strip() or _stable_id("review", payload)
        payload["id"] = row_id
        task_id = payload.get("task") or payload.get("task_id")
        evidence_id = payload.get("ev") or payload.get("evidence_id")
        try:
            with self._connection:
                self._connection.execute(
                    "INSERT INTO reviews(id, task_id, evidence_id, payload_json) VALUES(?, ?, ?, ?)",
                    (row_id, task_id, evidence_id, _json(payload)),
                )
        except sqlite3.IntegrityError as exc:
            raise ValueError(_REVIEW_DUP.format(row_id=row_id)) from exc
        return row_id

    def append_progress(self, content: str) -> bool:
        text = str(content or "").strip("\n")
        if not text.strip():
            raise ValueError(_PROGRESS_EMPTY)
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        with self._connection:
            result = self._connection.execute(
                "INSERT OR IGNORE INTO progress(content, content_hash) VALUES(?, ?)",
                (text, digest),
            )
        return bool(result.rowcount)

    def import_legacy(self, source_dir: str | Path) -> dict[str, int]:
        """Bulk-import old files once. Existing IDs and progress entries stay unchanged."""
        root = Path(source_dir)
        tasks_path = root / LEGACY_TASKS
        if not tasks_path.is_file():
            raise ValueError(_NO_LEGACY.format(source=root))
        tasks_doc = _read_json(tasks_path)
        if not isinstance(tasks_doc, dict):
            raise ValueError(_TASKS_OBJECT)
        task_rows = tasks_doc.get("tasks", [])
        if not isinstance(task_rows, list) or not all(isinstance(row, dict) for row in task_rows):
            raise ValueError(_TASKS_ARRAY)
        evidence_rows = _read_jsonl(root / LEGACY_EVIDENCE)
        review_rows = _read_jsonl(root / LEGACY_REVIEWS)
        progress = (root / LEGACY_PROGRESS).read_text(encoding="utf-8") if (root / LEGACY_PROGRESS).exists() else ""
        board = _read_json(root / LEGACY_BOARD) if (root / LEGACY_BOARD).is_file() else None
        counts = {"tasks": 0, "evidence": 0, "reviews": 0, "progress": 0, "board": 0}
        with self._connection:
            for key, value in tasks_doc.items():
                if key != "tasks":
                    self._connection.execute(
                        "INSERT INTO meta(key, value_json) VALUES(?, ?) "
                        "ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json",
                        (key, _json(value)),
                    )
            if board is not None:
                existed = self._connection.execute("SELECT 1 FROM meta WHERE key='board'").fetchone()
                self._connection.execute(
                    "INSERT INTO meta(key, value_json) VALUES('board', ?) "
                    "ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json",
                    (_json(board),),
                )
                counts["board"] = 0 if existed else 1
            for row in task_rows:
                task_id = str(row.get("id") or _stable_id("task", row))
                result = self._connection.execute(
                    "INSERT OR IGNORE INTO tasks(id, payload_json) VALUES(?, ?)",
                    (task_id, _json(row)),
                )
                counts["tasks"] += result.rowcount
            for table, rows, key_name in (("evidence", evidence_rows, "evidence"), ("reviews", review_rows, "review")):
                for row in rows:
                    row_id = str(row.get("id") or _stable_id(key_name, row))
                    task_id = row.get("task") or row.get("task_id")
                    evidence_id = row.get("ev") or row.get("evidence_id")
                    if table == "evidence":
                        result = self._connection.execute(
                            "INSERT OR IGNORE INTO evidence(id, task_id, payload_json) VALUES(?, ?, ?)",
                            (row_id, task_id, _json(row)),
                        )
                    else:
                        result = self._connection.execute(
                            "INSERT OR IGNORE INTO reviews(id, task_id, evidence_id, payload_json) VALUES(?, ?, ?, ?)",
                            (row_id, task_id, evidence_id, _json(row)),
                        )
                    counts[table] += result.rowcount
            if progress:
                digest = hashlib.sha256(progress.encode("utf-8")).hexdigest()
                result = self._connection.execute(
                    "INSERT OR IGNORE INTO progress(content, content_hash) VALUES(?, ?)",
                    (progress, digest),
                )
                counts["progress"] += result.rowcount
        return counts

    def read_snapshot(self) -> dict[str, Any]:
        tasks = [_unpack_row(row) for row in self._connection.execute("SELECT id, payload_json FROM tasks ORDER BY rowid")]
        evidence = [_unpack_row(row) for row in self._connection.execute("SELECT id, payload_json FROM evidence ORDER BY rowid")]
        reviews = [_unpack_row(row) for row in self._connection.execute("SELECT id, payload_json FROM reviews ORDER BY rowid")]
        progress_rows = self._connection.execute("SELECT content FROM progress ORDER BY id").fetchall()
        meta = {row["key"]: json.loads(row["value_json"]) for row in self._connection.execute("SELECT key, value_json FROM meta")}
        progress = "\n\n".join(row["content"] for row in progress_rows)
        counts = {"tasks": len(tasks), "evidence": len(evidence), "reviews": len(reviews)}
        return {
            "schema_version": self.schema_version(),
            "storage": {"type": "sqlite", "path": str(self.path)},
            "meta": meta,
            "tasks": tasks,
            "evidence": evidence,
            "reviews": reviews,
            "progress": progress,
            "board": meta.get("board") if isinstance(meta.get("board"), dict) else {},
            "project": meta.get("project"),
            "counts": counts,
            "revision": {
                "schema_version": self.schema_version(),
                "counts": counts,
                "meta_rev": meta.get("rev"),
                "progress_hash": hashlib.sha256(progress.encode("utf-8")).hexdigest() if progress else "",
            },
        }

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> "HarnessDB":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


def _unpack_row(row: sqlite3.Row) -> dict[str, Any]:
    payload = json.loads(row["payload_json"])
    item = dict(payload)
    item.setdefault("id", row["id"])
    item["payload"] = payload
    return item


def convert_legacy(source: str | Path, db_path: str | Path | None = None) -> dict[str, Any]:
    """One-shot bulk import. Never the live read path."""
    root = resolve_legacy_dir(source)
    target = Path(db_path).expanduser().resolve() if db_path else root / DB_NAME
    with HarnessDB(target, create=True) as db:
        counts = db.import_legacy(root)
        return {
            "db": str(db.path),
            "schema_version": db.schema_version(),
            "imported": counts,
            "source": str(root),
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="\u5c06\u65e7 Task Harness JSON/JSONL/TXT \u4e00\u6b21\u6027\u5bfc\u5165 SQLite\uff1b\u5bfc\u5165\u540e\u4e0d\u518d\u8bfb\u65e7\u6587\u4ef6")
    parser.add_argument("source", type=Path, help="\u9879\u76ee\u6839\u6216 .harness \u76ee\u5f55")
    parser.add_argument("--db", type=Path, help="\u6570\u636e\u5e93\u8def\u5f84\uff0c\u9ed8\u8ba4 source/harness.db")
    args = parser.parse_args(argv)
    result = convert_legacy(args.source, args.db)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
