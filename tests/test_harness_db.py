import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from harness_db import HarnessDB, SCHEMA_VERSION, convert_legacy

ROOT = Path(__file__).resolve().parents[1]
CONVERT = ROOT / "scripts" / "convert_harness_json.py"


class HarnessDBTests(unittest.TestCase):
    def write_legacy(self, root: Path, task_count: int = 2, *, board: bool = False) -> None:
        tasks = {
            "project": "测试项目",
            "description": "SQLite 迁移测试",
            "rev": 7,
            "custom_top_level": {"keep": True},
            "tasks": [
                {
                    "id": f"t-{i:03d}",
                    "priority": i,
                    "name": f"任务 {i}",
                    "desc": "任务描述",
                    "status": "pending" if i else "active",
                    "unknown_task_field": {"nested": i},
                }
                for i in range(task_count)
            ],
        }
        (root / "tasks.json").write_text(json.dumps(tasks, ensure_ascii=False), encoding="utf-8")
        evidence = [
            {
                "id": "ev-1",
                "task": "t-000",
                "summary": "验证通过",
                "cmd": "pytest",
                "exit": 0,
                "unknown_evidence_field": ["x", "y"],
            },
            {"id": "ev-2", "task": "t-000", "summary": "第二条", "cmd": "pytest -q", "exit": 0},
        ]
        (root / "evidence.jsonl").write_text(
            "\n".join(
                [json.dumps({"_comment": "忽略模板注释"}, ensure_ascii=False)]
                + [json.dumps(item, ensure_ascii=False) for item in evidence]
            )
            + "\n",
            encoding="utf-8",
        )
        (root / "reviews.jsonl").write_text(
            json.dumps(
                {
                    "id": "rv-1",
                    "task": "t-000",
                    "ev": "ev-1",
                    "verdict": "pass",
                    "reason": "独立评审通过",
                    "reviewer_context": "reviewer",
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        (root / "progress.txt").write_text(
            "# 项目进度\n\n## 2026-09-13 | t-000 | 执行\n- 状态：已验证\n",
            encoding="utf-8",
        )
        if board:
            (root / "board.json").write_text(
                json.dumps({"where": "当前站在迁移闸", "next": [{"task": "t-000", "why": "先导入"}]}, ensure_ascii=False),
                encoding="utf-8",
            )

    def test_initialize_creates_versioned_schema_and_snapshot_api(self):
        with tempfile.TemporaryDirectory() as temp:
            db = HarnessDB(Path(temp) / "harness.db")
            self.assertEqual(db.schema_version(), SCHEMA_VERSION)
            snapshot = db.read_snapshot()
            self.assertEqual(snapshot["schema_version"], SCHEMA_VERSION)
            self.assertEqual(snapshot["tasks"], [])
            self.assertEqual(snapshot["progress"], "")
            self.assertEqual(snapshot["storage"]["type"], "sqlite")
            self.assertIn("revision", snapshot)
            db.close()

    def test_open_without_database_is_uninitialized_not_json_fallback(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "tasks.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(FileNotFoundError) as ctx:
                HarnessDB.open(root, create=False)
            self.assertIn("禁止回退", str(ctx.exception))
            self.assertIn("harness.db", str(ctx.exception))

    def test_import_is_idempotent_and_preserves_unknown_fields(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.write_legacy(root, board=True)
            db = HarnessDB(root / "harness.db")
            self.assertEqual(
                db.import_legacy(root),
                {"tasks": 2, "evidence": 2, "reviews": 1, "progress": 1, "board": 1},
            )
            self.assertEqual(
                db.import_legacy(root),
                {"tasks": 0, "evidence": 0, "reviews": 0, "progress": 0, "board": 0},
            )
            snapshot = db.read_snapshot()
            self.assertEqual(len(snapshot["tasks"]), 2)
            self.assertEqual(len(snapshot["evidence"]), 2)
            self.assertEqual(len(snapshot["reviews"]), 1)
            self.assertIn("unknown_evidence_field", snapshot["evidence"][0]["payload"])
            self.assertEqual(snapshot["tasks"][0]["payload"]["unknown_task_field"], {"nested": 0})
            self.assertTrue(snapshot["meta"]["custom_top_level"]["keep"])
            self.assertEqual(snapshot["board"]["where"], "当前站在迁移闸")
            self.assertEqual(snapshot["progress"].count("## 2026-09-13"), 1)
            db.close()

    def test_import_handles_one_hundred_tasks_and_large_audit_without_json_monolith(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.write_legacy(root, task_count=100)
            with (root / "evidence.jsonl").open("a", encoding="utf-8") as handle:
                for i in range(1000):
                    handle.write(
                        json.dumps(
                            {"id": f"ev-{i+100}", "task": "t-000", "summary": "审计" * 200, "exit": 0},
                            ensure_ascii=False,
                        )
                        + "\n"
                    )
            db = HarnessDB(root / "harness.db")
            counts = db.import_legacy(root)
            self.assertEqual(counts["tasks"], 100)
            self.assertEqual(counts["evidence"], 1002)
            snapshot = db.read_snapshot()
            self.assertEqual(len(snapshot["tasks"]), 100)
            self.assertEqual(len(snapshot["evidence"]), 1002)
            self.assertEqual(snapshot["counts"], {"tasks": 100, "evidence": 1002, "reviews": 1})
            db.close()

    def test_convert_legacy_writes_nested_harness_db_in_one_shot(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            harness = project / ".harness"
            harness.mkdir()
            self.write_legacy(harness, task_count=100, board=True)
            result = convert_legacy(project)
            self.assertEqual(Path(result["db"]), harness / "harness.db")
            self.assertEqual(result["imported"]["tasks"], 100)
            self.assertEqual(result["imported"]["board"], 1)
            with HarnessDB(result["db"], create=False) as db:
                snapshot = db.read_snapshot()
            self.assertEqual(len(snapshot["tasks"]), 100)
            self.assertEqual(snapshot["project"], "测试项目")

    def test_convert_script_bulk_imports_without_row_by_row_agent_writes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.write_legacy(root, task_count=20)
            completed = subprocess.run(
                [sys.executable, "-X", "utf8", str(CONVERT), str(root)],
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            payload = json.loads(completed.stdout)
            self.assertEqual(payload["imported"]["tasks"], 20)
            self.assertTrue(Path(payload["db"]).is_file())

    def test_agent_api_roundtrip_does_not_use_json_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "tasks.json").write_text('{"project":"应被忽略"}', encoding="utf-8")
            with HarnessDB.open(root, create=True) as db:
                db.set_meta("project", "接口项目")
                db.set_meta("description", "接口说明")
                db.upsert_task(
                    {
                        "id": "t-01",
                        "name": "写库",
                        "desc": "验证 API",
                        "reason": "暂无阻塞",
                        "next": "追加证据",
                        "status": "active",
                    }
                )
                db.append_evidence({"id": "ev-01", "task": "t-01", "summary": "命令已执行", "cmd": "pytest", "exit": 0})
                db.append_review(
                    {
                        "id": "rv-01",
                        "task": "t-01",
                        "ev": "ev-01",
                        "verdict": "pass",
                        "reason": "独立评审通过",
                        "reviewer_context": "reviewer",
                    }
                )
                db.append_progress("## 2026-09-13 | t-01 | 执行\n- 进展：接口写入")
                snapshot = db.read_snapshot()
            self.assertEqual(snapshot["project"], "接口项目")
            self.assertEqual(snapshot["tasks"][0]["id"], "t-01")
            self.assertEqual(snapshot["evidence"][0]["id"], "ev-01")
            self.assertEqual(snapshot["reviews"][0]["id"], "rv-01")
            self.assertIn("接口写入", snapshot["progress"])
            self.assertNotEqual(snapshot["project"], "应被忽略")

    def test_reopening_database_keeps_data_and_uses_sqlite(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.write_legacy(root)
            db = HarnessDB(root / "harness.db")
            db.import_legacy(root)
            db.close()
            reopened = HarnessDB(root / "harness.db", create=False)
            self.assertEqual(reopened.read_snapshot()["tasks"][0]["id"], "t-000")
            connection = sqlite3.connect(root / "harness.db")
            try:
                self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            finally:
                connection.close()
            reopened.close()


if __name__ == "__main__":
    unittest.main()
