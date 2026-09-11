import contextlib
import importlib.util
import io
import json
import socket
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("dashboard", ROOT / "references/templates/serve_dashboard.py")
dashboard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dashboard)


def fetch(url):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(urllib.request.Request(url, method="GET"), timeout=2) as resp:
        return resp.status, resp.read()


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="harness space ")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.killed = set()

    def kill_harness(self, harness):
        meta_path = harness / ".dashboard-server.json"
        if not meta_path.is_file():
            return
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        pid = meta.get("pid")
        if pid in self.killed:
            return
        dashboard.stop_pid(pid)
        self.killed.add(pid)

    def tasks(self, parent=None, desc="任务"):
        parent = parent or self.root / ".harness"
        parent.mkdir(exist_ok=True)
        path = parent / "tasks.json"
        path.write_text(json.dumps({"project": "测试项目", "rev": 1, "tasks": [
            {"id": "a", "status": "pending", "desc": desc, "depends_on": [], "priority": 1}
        ]}, ensure_ascii=False), encoding="utf-8-sig")
        return path

    def run_serve(self, target=None, **kwargs):
        with contextlib.redirect_stdout(io.StringIO()) as buf:
            out = dashboard.serve(target or self.root, **kwargs)
        self.last_stdout = buf.getvalue()
        self.addCleanup(self.kill_harness, out.parent)
        return out

    def meta(self, html):
        return json.loads((html.parent / ".dashboard-server.json").read_text(encoding="utf-8"))

    def test_empty_project_creates_no_fake_tasks_and_no_open(self):
        with patch.object(dashboard.webbrowser, "open") as opener:
            out = self.run_serve()
        self.assertTrue(out.exists())
        self.assertFalse((out.parent / "tasks.json").exists())
        opener.assert_not_called()
        self.assertIn("http://127.0.0.1:", self.last_stdout)

    def test_first_orchestration_opens_once_and_explicit_open(self):
        self.tasks()
        with patch.object(dashboard.webbrowser, "open", return_value=True) as opener:
            out = self.run_serve()
            self.run_serve()
            self.run_serve(force_open=True)
            self.assertEqual(opener.call_count, 2)
            url = opener.call_args.args[0]
            self.assertTrue(url.startswith("http://127.0.0.1:"))
            self.assertIn("/task-harness.html", url)
            self.assertEqual(url, "http://127.0.0.1:%s/task-harness.html" % self.meta(out)["port"])

    def test_no_open_does_not_consume_first_open(self):
        self.tasks()
        with patch.object(dashboard.webbrowser, "open", return_value=True) as opener:
            self.run_serve(no_open=True)
            opener.assert_not_called()
            self.run_serve()
            opener.assert_called_once()

    def test_existing_harness_and_http_preserve_source(self):
        src = self.tasks()
        before = src.read_bytes()
        out = self.run_serve(self.root / ".harness", no_open=True)
        self.assertEqual(src.read_bytes(), before)
        self.assertFalse((out.parent / ".harness").exists())
        html = out.read_text(encoding="utf-8")
        self.assertIn("载入任务", html)
        self.assertNotIn("__HARNESS_SNAPSHOT__", html)
        self.tasks(desc="更新任务")
        updated = src.read_bytes()
        self.run_serve(no_open=True)
        self.assertEqual(src.read_bytes(), updated)
        status, body = fetch("http://127.0.0.1:%s/tasks.json" % self.meta(out)["port"])
        self.assertEqual(status, 200)
        self.assertEqual(body, updated)

    def test_root_layout_preserved(self):
        src = self.tasks(self.root)
        before = src.read_bytes()
        out = self.run_serve(no_open=True)
        self.assertEqual(src.read_bytes(), before)
        self.assertFalse((out.parent / "tasks.json").exists())
        status, body = fetch("http://127.0.0.1:%s/tasks.json" % self.meta(out)["port"])
        self.assertEqual(status, 200)
        self.assertEqual(body, before)

    def test_http_serves_spa_not_snapshot(self):
        self.tasks(desc="</script><img src=x onerror=alert(1)>")
        out = self.run_serve(no_open=True)
        status, body = fetch("http://127.0.0.1:%s/task-harness.html" % self.meta(out)["port"])
        html = body.decode("utf-8")
        self.assertEqual(status, 200)
        self.assertIn("载入任务", html)
        self.assertNotIn("</script><img", html)
        self.assertNotIn("__HARNESS_SNAPSHOT__", html)
        with self.assertRaises(urllib.error.HTTPError) as err:
            fetch("http://127.0.0.1:%s/secret.txt" % self.meta(out)["port"])
        self.assertEqual(err.exception.code, 404)

    def test_bad_jsonl_does_not_block_serving(self):
        self.tasks()
        out = self.run_serve(no_open=True)
        before = (out.parent / "tasks.json").read_bytes()
        (out.parent / "reviews.jsonl").write_text("{bad", encoding="utf-8")
        self.run_serve(no_open=True)
        self.assertEqual(before, (out.parent / "tasks.json").read_bytes())
        status, _body = fetch("http://127.0.0.1:%s/task-harness.html" % self.meta(out)["port"])
        self.assertEqual(status, 200)

    def test_unknown_status_does_not_block_serving(self):
        src = self.tasks()
        data = json.loads(src.read_text(encoding="utf-8-sig"))
        data["tasks"][0]["status"] = "injected"
        src.write_text(json.dumps(data), encoding="utf-8")
        out = self.run_serve(no_open=True)
        status, _body = fetch("http://127.0.0.1:%s/tasks.json" % self.meta(out)["port"])
        self.assertEqual(status, 200)

    def test_reuses_port_and_pid(self):
        self.tasks()
        out = self.run_serve(no_open=True)
        first = self.meta(out)
        self.run_serve(no_open=True)
        second = self.meta(out)
        self.assertEqual(first["port"], second["port"])
        self.assertEqual(first["pid"], second["pid"])

    def free_port_block(self, span=6):
        """占用一段连续空闲端口的首个，返回 (blocker, lo, hi)。"""
        class Other(BaseHTTPRequestHandler):
            def log_message(self, *args):
                return

            def do_GET(self):
                body = b'{"project":"other","rev":1,"tasks":[]}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        for lo in range(18900, 19100, 10):
            hi = lo + span - 1
            probes = []
            try:
                for port in range(lo, hi + 1):
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.bind(("127.0.0.1", port))
                    probes.append(sock)
            except OSError:
                continue
            finally:
                for sock in probes:
                    sock.close()
            blocker = ThreadingHTTPServer(("127.0.0.1", lo), Other)
            self.addCleanup(blocker.server_close)
            self.addCleanup(blocker.shutdown)
            threading.Thread(target=blocker.serve_forever, daemon=True).start()
            return blocker, lo, hi
        self.skipTest("找不到连续空闲端口段")
        return None, 0, 0

    def test_occupied_port_is_not_hijacked(self):
        """端口被别的项目看板占用时，必须换端口而不是复用对方的地址。"""
        _blocker, lo, hi = self.free_port_block()
        with patch.object(dashboard, "PORT_MIN", lo), patch.object(dashboard, "PORT_MAX", hi):
            self.tasks(desc="本项目任务")
            out = self.run_serve(no_open=True)
            meta = self.meta(out)
            self.assertNotEqual(meta["port"], lo)
            status, body = fetch("http://127.0.0.1:%s/tasks.json" % meta["port"])
            self.assertEqual(status, 200)
            self.assertEqual(body, (out.parent / "tasks.json").read_bytes())

    def test_packaging(self):
        self.assertTrue((ROOT / "references/templates/task-harness.html").exists())
        self.assertTrue((ROOT / "references/templates/serve_dashboard.py").exists())
        self.assertFalse((ROOT / "references/templates/task-harness.html.template").exists())
        self.assertFalse((ROOT / "references/templates/render_dashboard.py").exists())
        self.assertFalse((ROOT / "references/visualizer/task-harness.html").exists())
        text = (ROOT / "references/templates/task-harness.html").read_text(encoding="utf-8")
        js = (ROOT / "references/templates/app.js").read_text(encoding="utf-8")
        self.assertNotIn("载入示例", text)
        self.assertNotIn("清空", text)
        self.assertNotIn("type=\"file\"", text)
        self.assertIn("刷新任务", text)
        self.assertIn("评审未通过", js)
        self.assertIn("选择项目任务目录", js)
        self.assertIn("./app.js", text)
        self.assertIn("showDirectoryPicker", js)
        self.assertNotIn("isTauri", js)
        self.assertNotIn("__TAURI__", js)
        self.assertNotIn("probe_harness_dir", js)
        self.assertTrue((ROOT / "dashboard/TaskHarness.sln").exists())
        self.assertTrue((ROOT / "dashboard/TaskHarness/TaskHarness.csproj").exists())
        self.assertTrue((ROOT / "dashboard/TaskHarness.Core/TaskHarness.Core.csproj").exists())
        self.assertTrue((ROOT / "dashboard/Build.ps1").exists())
        self.assertFalse((ROOT / "dashboard/ui").exists())
        self.assertFalse((ROOT / "dashboard/src-tauri").exists())
        self.assertFalse((ROOT / "dashboard/package.json").exists())


if __name__ == "__main__":
    unittest.main()
