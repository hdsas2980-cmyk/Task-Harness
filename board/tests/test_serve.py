import importlib.util
import json
import socket
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("board_serve", ROOT / "serve.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def fetch(url):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(urllib.request.Request(url, method="GET"), timeout=2) as resp:
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
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", 0))
        self.port = sock.getsockname()[1]
        sock.close()
        self.httpd = mod.make_server(mod.resolve_source(self.root), self.port)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.httpd.server_close)
        self.addCleanup(self.httpd.shutdown)
        self.base = "http://127.0.0.1:%s" % self.port
        deadline = time.time() + 2
        while time.time() < deadline:
            try:
                fetch(self.base + "/")
                break
            except OSError:
                time.sleep(0.05)

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

    def test_post_rejected(self):
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        req = urllib.request.Request(self.base + "/api/snapshot", data=b"{}", method="POST")
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            opener.open(req, timeout=2)
        self.assertEqual(ctx.exception.code, 405)


if __name__ == "__main__":
    unittest.main()
