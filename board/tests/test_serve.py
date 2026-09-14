import importlib.util
import json
import os
import socket
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
from harness_db import HarnessDB
spec = importlib.util.spec_from_file_location("board_serve", ROOT / "serve.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def fetch(url, data=None, method=None):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    headers = {}
    body = None
    if data is not None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"
        method = method or "POST"
    req = urllib.request.Request(url, data=body, headers=headers, method=method or "GET")
    with opener.open(req, timeout=3) as resp:
        return resp.status, resp.read()


class BoardServeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="board ")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        harness = self.root / ".harness"
        harness.mkdir()
        self.tasks = harness / "tasks.json"
        self.tasks.write_text(
            json.dumps({"project": "测试项目", "rev": 1, "tasks": [
                {"id": "a", "status": "pending", "desc": "中文任务", "depends_on": [], "priority": 1}
            ]}, ensure_ascii=False),
            encoding="utf-8-sig",
        )
        self.other = self.root / "other"
        other_h = self.other / ".harness"
        other_h.mkdir(parents=True)
        (other_h / "tasks.json").write_text(
            json.dumps({"project": "另一个", "tasks": [{"id": "b", "status": "active", "desc": "会话任务"}]}, ensure_ascii=False),
            encoding="utf-8",
        )
        sessions = self.root / "sessions"
        sess = sessions / "2026" / "09" / "11"
        sess.mkdir(parents=True)
        (sess / "rollout.jsonl").write_text(
            json.dumps({
                "timestamp": "2026-09-11T12:00:00Z",
                "type": "session_meta",
                "payload": {"id": "sid-1", "cwd": str(self.other), "timestamp": "2026-09-11T12:00:00Z"},
            }, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        (self.root / "session_index.jsonl").write_text(
            json.dumps({"id": "sid-1", "thread_name": "从会话载入"}, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        self._old_sessions = os.environ.get("CODEX_SESSIONS_DIR")
        self._old_last = os.environ.get("TASK_HARNESS_LAST_SOURCE")
        os.environ["CODEX_SESSIONS_DIR"] = str(sessions)
        self.last_file = self.root / "last-source.txt"
        os.environ["TASK_HARNESS_LAST_SOURCE"] = str(self.last_file)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", 0))
        self.port = sock.getsockname()[1]
        sock.close()
        self.httpd = mod.make_server(mod.resolve_source(self.root), self.port)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.httpd.server_close)
        self.addCleanup(self.httpd.shutdown)
        self.addCleanup(self._restore_env)
        self.base = "http://127.0.0.1:%s" % self.port
        deadline = time.time() + 2
        while time.time() < deadline:
            try:
                fetch(self.base + "/")
                break
            except OSError:
                time.sleep(0.05)

    def _restore_env(self):
        if self._old_sessions is None:
            os.environ.pop("CODEX_SESSIONS_DIR", None)
        else:
            os.environ["CODEX_SESSIONS_DIR"] = self._old_sessions
        if self._old_last is None:
            os.environ.pop("TASK_HARNESS_LAST_SOURCE", None)
        else:
            os.environ["TASK_HARNESS_LAST_SOURCE"] = self._old_last

    def test_snapshot_chinese_and_readonly(self):
        before = self.tasks.read_bytes()
        status, body = fetch(self.base + "/api/snapshot")
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertIn("测试项目", data["files"]["tasks.json"])
        self.assertIn("中文任务", data["files"]["tasks.json"])
        self.assertTrue(data["source"].endswith(".harness"))
        status, html = fetch(self.base + "/")
        self.assertEqual(status, 200)
        self.assertIn(b"app.js", html)
        self.assertIn("load-drawer".encode("utf-8"), html)
        self.assertEqual(self.tasks.read_bytes(), before)

    def test_poll_sees_update(self):
        _, body = fetch(self.base + "/api/snapshot")
        first = json.loads(body.decode("utf-8"))["files"]["tasks.json"]
        raw = json.loads(self.tasks.read_text(encoding="utf-8-sig"))
        raw["tasks"][0]["desc"] = "已更新"
        self.tasks.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8-sig")
        _, body = fetch(self.base + "/api/snapshot")
        second = json.loads(body.decode("utf-8"))["files"]["tasks.json"]
        self.assertNotEqual(first, second)
        self.assertIn("已更新", second)

    def test_post_snapshot_rejected(self):
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        req = urllib.request.Request(self.base + "/api/snapshot", data=b"{}", method="POST")
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            opener.open(req, timeout=2)
        self.assertEqual(ctx.exception.code, 405)

    def test_sessions_and_switch_source(self):
        before = self.tasks.read_bytes()
        status, body = fetch(self.base + "/api/sessions")
        self.assertEqual(status, 200)
        catalog = json.loads(body.decode("utf-8"))
        self.assertTrue(catalog["projects"])
        match = [row for row in catalog["projects"] if Path(row["cwd"]) == self.other]
        self.assertEqual(len(match), 1)
        self.assertTrue(match[0]["has_harness"])
        self.assertEqual(match[0]["latest_title"], "从会话载入")
        status, body = fetch(self.base + "/api/source", {"path": str(self.other)})
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertIn("会话任务", data["files"]["tasks.json"])
        self.assertTrue(data["source"].endswith(".harness"))
        self.assertEqual(self.tasks.read_bytes(), before)
        _, body = fetch(self.base + "/api/snapshot")
        live = json.loads(body.decode("utf-8"))
        self.assertIn("会话任务", live["files"]["tasks.json"])

    def test_unbound_server(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()
        httpd = mod.make_server(None, port)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            deadline = time.time() + 2
            while time.time() < deadline:
                try:
                    status, body = fetch("http://127.0.0.1:%s/api/snapshot" % port)
                    break
                except OSError:
                    time.sleep(0.05)
            self.assertEqual(status, 200)
            data = json.loads(body.decode("utf-8"))
            self.assertIsNone(data["source"])
            self.assertEqual(data["files"], {})
        finally:
            httpd.shutdown()
            httpd.server_close()


    def test_snapshot_reports_language_failure_without_rewriting_source(self):
        original = self.tasks.read_bytes()
        _, body = fetch(self.base + "/api/snapshot")
        result = json.loads(body.decode("utf-8"))
        self.assertIn("contract", result)
        self.assertTrue(result["contract"]["errors"])
        self.assertIn("description", "\n".join(result["contract"]["errors"]))
        self.assertEqual(self.tasks.read_bytes(), original)

    def test_native_chinese_snapshot_uses_shared_checker(self):
        source = self.tasks.parent
        self.tasks.write_text(json.dumps({"project":"测试项目", "description":"验证只读看板", "tasks":[
            {"id":"a", "name":"实现任务", "desc":"实现验证", "reason":"暂无阻塞", "next":"执行验证", "status":"active"}
        ]}, ensure_ascii=False), encoding="utf-8")
        for filename in ("evidence.jsonl", "reviews.jsonl"):
            (source / filename).write_text("", encoding="utf-8")
        (source / "progress.txt").write_text("## 2026-09-12 | a | 执行\n- 进展：已开始实现\n", encoding="utf-8")
        _, body = fetch(self.base + "/api/snapshot")
        result = json.loads(body.decode("utf-8"))
        self.assertEqual(result["contract"]["errors"], [])
        (source / "board.i18n.json").write_text("{}", encoding="utf-8")
        _, body = fetch(self.base + "/api/snapshot")
        self.assertIn("board.i18n.json", str(json.loads(body.decode("utf-8"))["contract"]["errors"]))

    def test_switch_remembers_last_source(self):
        status, body = fetch(self.base + "/api/source", {"path": str(self.other)})
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertTrue(self.last_file.is_file())
        saved = self.last_file.read_text(encoding="utf-8").strip()
        self.assertEqual(saved, data["source"])
        self.assertEqual(data["last_source"], saved)
        _, body = fetch(self.base + "/api/snapshot")
        snap = json.loads(body.decode("utf-8"))
        self.assertEqual(snap["last_source"], saved)

    def test_choose_project_reuses_last_without_tty(self):
        harness = self.root / ".harness"
        self.last_file.write_text(str(harness) + "\n", encoding="utf-8")
        chosen = mod.choose_project(None, prompt=False)
        self.assertEqual(chosen, harness)

    def test_snapshot_prefers_harness_db_over_leftover_progress(self):
        source = self.tasks.parent
        leftover = "\n".join(["Task finished. Waiting for review."] * 20)
        leftover = leftover + "\n" + "\n".join(["English leftover line"] * 8)
        (source / "progress.txt").write_text(leftover, encoding="utf-8")
        with HarnessDB(source / "harness.db", create=True) as db:
            db.set_meta("project", "测试项目")
            db.set_meta("description", "验证看板读库")
            db.upsert_task({
                "id": "a",
                "name": "实现任务",
                "desc": "实现验证",
                "reason": "暂无阻塞",
                "next": "执行验证",
                "status": "active",
            })
            db.append_progress("## 2026-09-14 | a | 执行\n- 进展：数据库进度已写入")
        _, body = fetch(self.base + "/api/snapshot")
        result = json.loads(body.decode("utf-8"))
        self.assertEqual(result["contract"]["errors"], [])
        self.assertIn("数据库进度已写入", result["files"]["progress.txt"])
        self.assertNotIn("English leftover line", result["files"]["progress.txt"])

    def test_start_ps1_is_ascii(self):
        raw = (ROOT / "start.ps1").read_bytes()
        if raw.startswith(b"\xef\xbb\xbf"):
            raw = raw[3:]
        raw.decode("ascii")

if __name__ == "__main__":
    unittest.main()
