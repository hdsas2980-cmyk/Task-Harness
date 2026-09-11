import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
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

    def test_resolve_prefers_nested_harness(self):
        source = mod.resolve_source(self.proj)
        self.assertEqual(source, self.proj / ".harness")


if __name__ == "__main__":
    unittest.main()
