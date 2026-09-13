#!/usr/bin/env python3
"""Rust snapshot 必须对齐 harness_db.HarnessDB.read_snapshot()。"""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from harness_db import HarnessDB, SCHEMA_VERSION  # noqa: E402

TAURI = ROOT / "board" / "tauri" / "src-tauri"
VCVARS = Path(r"C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat")


def _write_fixture(db_path: Path) -> dict:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE meta (key TEXT PRIMARY KEY, value_json TEXT NOT NULL);
            CREATE TABLE tasks (id TEXT PRIMARY KEY, payload_json TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE evidence (id TEXT PRIMARY KEY, task_id TEXT, payload_json TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE reviews (id TEXT PRIMARY KEY, task_id TEXT, evidence_id TEXT, payload_json TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE progress (id INTEGER PRIMARY KEY AUTOINCREMENT, content TEXT NOT NULL, content_hash TEXT UNIQUE NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
            """
        )
        conn.execute("INSERT INTO meta VALUES ('schema_version', ?)", (json.dumps(SCHEMA_VERSION),))
        conn.execute("INSERT INTO meta VALUES ('project', ?)", (json.dumps("测试项目"),))
        conn.execute("INSERT INTO meta VALUES ('description', ?)", (json.dumps("对齐快照"),))
        conn.execute(
            "INSERT INTO tasks(id, payload_json) VALUES (?, ?)",
            ("t-000", json.dumps({"id": "t-000", "name": "任务", "unknown_task_field": {"nested": 0}}, ensure_ascii=False)),
        )
        conn.execute("INSERT INTO progress(content, content_hash) VALUES ('第一段', 'a')")
        conn.execute("INSERT INTO progress(content, content_hash) VALUES ('第二段', 'b')")
        conn.commit()
    with HarnessDB(db_path) as db:
        return db.read_snapshot()


class SnapshotParityTests(unittest.TestCase):
    def test_python_snapshot_shape_is_canonical(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            db_path = Path(tmp) / "harness.db"
            snap = _write_fixture(db_path)
            before = db_path.read_bytes()
            self.assertEqual(snap["schema_version"], 1)
            self.assertEqual(snap["storage"]["type"], "sqlite")
            self.assertIsInstance(snap["tasks"], list)
            self.assertEqual(snap["tasks"][0]["id"], "t-000")
            self.assertEqual(snap["tasks"][0]["payload"]["unknown_task_field"]["nested"], 0)
            self.assertEqual(snap["meta"]["project"], "测试项目")
            self.assertEqual(snap["board"], {})
            self.assertEqual(snap["progress"], "第一段" + chr(10) + chr(10) + "第二段")
            self.assertEqual(db_path.read_bytes(), before)
            self.assertFalse((Path(tmp) / "harness.db-wal").exists())
            self.assertFalse((Path(tmp) / "harness.db-shm").exists())

    def test_readonly_uri_does_not_create_missing_db(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "missing.db"
            self.assertFalse(missing.exists())
            uri = "file:" + missing.as_posix() + "?mode=ro"
            with self.assertRaises(sqlite3.Error):
                sqlite3.connect(uri, uri=True)
            self.assertFalse(missing.exists())

    def test_rust_unit_tests_cover_same_unpack_rules(self) -> None:
        if os.environ.get("SKIP_CARGO_TESTS") == "1":
            self.skipTest("SKIP_CARGO_TESTS=1")
        args = ["cargo", "test", "--lib", "--", "--test-threads=1"]
        if VCVARS.is_file():
            command = "call " + subprocess.list2cmdline([str(VCVARS)]) + " && " + subprocess.list2cmdline(args)
            completed = subprocess.run(command, cwd=str(TAURI), shell=True)
        else:
            completed = subprocess.run(args, cwd=str(TAURI))
        self.assertEqual(completed.returncode, 0, "cargo test --lib 必须通过")


if __name__ == "__main__":
    unittest.main()
