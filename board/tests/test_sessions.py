import importlib.util
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from harness_db import HarnessDB, convert_legacy  # noqa: E402

spec = importlib.util.spec_from_file_location("board_sessions", ROOT / "sessions.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def write_session(path: Path, cwd: str, sid: str, ts: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "id": sid,
        "cwd": cwd,
        "timestamp": ts,
        "model_provider": "custom",
    }
    path.write_text(
        json.dumps({"timestamp": ts, "type": "session_meta", "payload": payload}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    modified = datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
    os.utime(path, (modified, modified))


class SessionCatalogTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="board-sess ")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.sessions = self.root / "sessions"
        self.proj = self.root / "proj"
        harness = self.proj / ".harness"
        harness.mkdir(parents=True)
        (harness / "tasks.json").write_text(
            json.dumps({"project": "演示项目", "tasks": [{"id": "a", "status": "pending"}]}, ensure_ascii=False),
            encoding="utf-8",
        )
        convert_legacy(harness)
        self.other = self.root / "other"
        self.other.mkdir()
        write_session(
            self.sessions / "2026" / "09" / "11" / "rollout-a.jsonl",
            str(self.proj),
            "sid-a",
            "2026-09-11T12:00:00Z",
        )
        write_session(
            self.sessions / "2026" / "09" / "10" / "rollout-b.jsonl",
            str(self.other),
            "sid-b",
            "2026-09-10T12:00:00Z",
        )
        (self.root / "session_index.jsonl").write_text(
            json.dumps({"id": "sid-a", "thread_name": "重整看板", "updated_at": "2026-09-11T12:00:01Z"}, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    def test_probe_harness_prefers_database_metadata(self):
        db_path = self.proj / ".harness" / "harness.db"
        db_path.unlink()
        with HarnessDB(db_path, create=True) as db:
            db.set_meta("project", "数据库项目")
            for i in range(100):
                db.upsert_task({"id": f"db-{i}", "status": "pending", "desc": f"数据库任务 {i}"})
        info = mod.probe_harness(str(self.proj))
        self.assertEqual(info["project_name"], "数据库项目")
        self.assertEqual(info["task_count"], 100)
        self.assertTrue(str(info["tasks_file"]).endswith("harness.db"))

    def test_json_only_project_is_not_harness(self):
        json_only = self.root / "json-only"
        harness = json_only / ".harness"
        harness.mkdir(parents=True)
        (harness / "tasks.json").write_text(
            json.dumps({"project": "伪装项目", "tasks": [{"id": "z"}]}, ensure_ascii=False),
            encoding="utf-8",
        )
        info = mod.probe_harness(str(json_only))
        self.assertFalse(info["has_harness"])
        self.assertIsNone(info["task_count"])

    def test_groups_cwd_and_detects_harness(self):
        catalog = mod.list_session_catalog(root=self.sessions)
        self.assertEqual(catalog["scanned"], 2)
        by_cwd = {row["cwd"]: row for row in catalog["projects"]}
        self.assertTrue(by_cwd[str(self.proj)]["has_harness"])
        self.assertEqual(by_cwd[str(self.proj)]["task_count"], 1)
        self.assertEqual(by_cwd[str(self.proj)]["latest_title"], "重整看板")
        self.assertFalse(by_cwd[str(self.other)]["has_harness"])
        self.assertEqual(catalog["suggested"]["reason"], "latest_session")
        self.assertEqual(Path(catalog["suggested"]["cwd"]), self.proj)

    def test_single_harness_suggested_if_latest_has_none(self):
        write_session(
            self.sessions / "2026" / "09" / "12" / "rollout-c.jsonl",
            str(self.other),
            "sid-c",
            "2026-09-12T12:00:00Z",
        )
        catalog = mod.list_session_catalog(root=self.sessions)
        self.assertEqual(catalog["suggested"]["reason"], "single_harness")
        self.assertEqual(Path(catalog["suggested"]["cwd"]), self.proj)

    def test_codex_home_and_explicit_sessions_root(self):
        with patch.dict(os.environ, {"CODEX_HOME": str(self.root / "custom-codex"), "USERPROFILE": str(self.root / "default-home"), "HOME": str(self.root / "default-home")}, clear=True):
            self.assertEqual(mod.sessions_dir(), self.root / "custom-codex" / "sessions")
            with patch.dict(os.environ, {"CODEX_SESSIONS_DIR": str(self.sessions)}):
                self.assertEqual(mod.sessions_dir(), self.sessions)

    def test_flat_metadata_and_tail_cwd_are_discoverable(self):
        # 历史迁移记录可直接保存 metadata；缺 cwd 时从末尾 turn_context 恢复。
        flat = self.sessions / "flat.jsonl"
        flat.write_text(json.dumps({"id":"flat-session", "cwd":str(self.proj), "timestamp":"2026-09-12T12:00:00Z"}), encoding="utf-8")
        tail = self.sessions / "tail.jsonl"
        tail.write_text(json.dumps({"type":"session_meta", "payload":{"id":"tail-session"}}) + "\n" + json.dumps({"type":"turn_context", "payload":{"cwd":str(self.proj)}}), encoding="utf-8")
        catalog = mod.list_session_catalog(root=self.sessions)
        project = next(row for row in catalog["projects"] if row["cwd"] == str(self.proj))
        self.assertTrue({"flat-session", "tail-session"}.issubset({s["id"] for s in project["sessions"]}))

    def test_resolve_prefers_nested_harness(self):
        source = mod.resolve_source(self.proj)
        self.assertEqual(source, self.proj / ".harness")


if __name__ == "__main__":
    unittest.main()
