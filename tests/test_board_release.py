import hashlib
import json
import os
import shutil
import socket
import time
import urllib.request
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
from harness_db import convert_legacy  # noqa: E402

class BoardReleaseTests(unittest.TestCase):
    def test_build_is_exact_and_includes_same_checker(self):
        builder = ROOT / "scripts/build_board_release.py"
        self.assertTrue(builder.is_file(), "缺少统一发布入口")
        with tempfile.TemporaryDirectory(prefix="release-test-", dir=ROOT) as temp:
            output = Path(temp).resolve(); self.assertEqual(output.parent, ROOT)
            result = subprocess.run([sys.executable, str(builder), "--output", str(output)], capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            bundle = output / "TaskBoard"
            manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
            with zipfile.ZipFile(output / "TaskBoard-windows.zip") as archive:
                self.assertEqual(set(archive.namelist()), {"TaskBoard/" + name for name in [*manifest, "manifest.json"]})
                for name, sha in manifest.items():
                    data = (bundle / name).read_bytes()
                    self.assertEqual(hashlib.sha256(data).hexdigest(), sha)
                    self.assertEqual(data, archive.read("TaskBoard/" + name))
            self.assertEqual((bundle / "static/app.js").read_bytes(), (ROOT / "board/static/app.js").read_bytes())
            self.assertEqual((bundle / "scripts/check_task_harness_language.py").read_bytes(), (ROOT / "scripts/check_task_harness_language.py").read_bytes())
            self.assertEqual((bundle / "harness_db.py").read_bytes(), (ROOT / "harness_db.py").read_bytes())
            for name in ("static/app.js", "static/index.html"):
                text = (bundle / name).read_text(encoding="utf-8")
                for forbidden in ("parseI18n", "translated(", "name_zh", "summary_zh"):
                    self.assertNotIn(forbidden, text)
            probe = subprocess.run([sys.executable, "-B", "-c",
                "import importlib.util,sys; from pathlib import Path; "
                "p=Path(sys.argv[1]); s=importlib.util.spec_from_file_location('release_serve',p/'serve.py'); "
                "m=importlib.util.module_from_spec(s); s.loader.exec_module(m); "
                "assert m.CHECKER.resolve()==(p/'scripts/check_task_harness_language.py').resolve(); "
                "assert m.snapshot(None)['contract'] is None; assert (p/'harness_db.py').is_file()", str(bundle)],
                cwd=output, capture_output=True)
            self.assertEqual(probe.returncode, 0, probe.stderr)
            # 正常运行的路径记忆和字节码缓存应保留本地，但不得进入发布包。
            (bundle / ".last-source").write_text("本地上次任务目录", encoding="utf-8")
            cache = bundle / "__pycache__"; cache.mkdir()
            (cache / "sessions.cpython-311.pyc").write_bytes(b"runtime cache")
            rebuilt = subprocess.run([sys.executable, str(builder), "--output", str(output)], capture_output=True)
            self.assertEqual(rebuilt.returncode, 0, rebuilt.stderr)
            self.assertEqual((bundle / ".last-source").read_text(encoding="utf-8"), "本地上次任务目录")
            with zipfile.ZipFile(output / "TaskBoard-windows.zip") as archive:
                self.assertFalse(any(".last-source" in name or "__pycache__" in name for name in archive.namelist()))
            # 意外遗留文件必须阻断打包，不得被不加检查地放进 ZIP。
            (bundle / "stale.js").write_text("stale", encoding="utf-8")
            failed = subprocess.run([sys.executable, str(builder), "--output", str(output)], capture_output=True)
            self.assertNotEqual(failed.returncode, 0)

    def test_detached_zip_session_loading_over_real_http(self):
        node = shutil.which("node")
        self.assertIsNotNone(node, "此发布回归需要 Node.js 执行真实前端按钮链路")
        with tempfile.TemporaryDirectory(prefix="live-release-", dir=ROOT) as temp:
            temp = Path(temp)
            built = subprocess.run([sys.executable, str(ROOT / "scripts/build_board_release.py"), "--output", str(temp / "output")], capture_output=True)
            self.assertEqual(built.returncode, 0, built.stderr)
            detached = temp / "独立解压"
            with zipfile.ZipFile(temp / "output/TaskBoard-windows.zip") as archive:
                archive.extractall(detached)
            bundle = detached / "TaskBoard"
            sessions = temp / "isolated-codex/sessions"
            sessions.mkdir(parents=True)
            originals = {}
            for label, name in (("A", "甲"), ("B", "乙")):
                project = temp / ("测试项目" + name)
                source = project / ".harness"; source.mkdir(parents=True)
                data = {"project":"隔离测试", "description":"验证真实会话载入", "tasks":[
                    {"id":"task-" + label,"name":"任务" + name,"desc":"验证独立载入","reason":"暂无阻塞","next":"核对接口结果","status":"active"}]}
                files = {"tasks.json":json.dumps(data,ensure_ascii=False),"evidence.jsonl":"","reviews.jsonl":"",
                    "progress.txt":"## 2026-09-12 | task-" + label + " | 执行\n- 进展：正在验证会话加载\n"}
                for filename, content in files.items():
                    path=source/filename; path.write_text(content,encoding="utf-8"); originals[path]=path.read_bytes()
                convert_legacy(source)
                originals[source/"harness.db"]=(source/"harness.db").read_bytes()
                session=sessions/("session-" + label + ".jsonl")
                session.write_text(json.dumps({"type":"session_meta","payload":{"id":"session-"+label,"cwd":str(project),"timestamp":"2026-09-12T10:00:00Z"}}),encoding="utf-8")
                originals[session]=session.read_bytes()
            index=sessions.parent/"session_index.jsonl"
            index.write_text("\n".join(json.dumps({"id":"session-"+label,"thread_name":"会话"+name},ensure_ascii=False) for label,name in (("A","甲"),("B","乙"))),encoding="utf-8")
            originals[index]=index.read_bytes()
            with socket.socket() as sock:
                sock.bind(("127.0.0.1",0)); port=sock.getsockname()[1]
            base="http://127.0.0.1:"+str(port)
            env=os.environ.copy()
            env.update({"PYTHONUTF8":"1","PYTHONIOENCODING":"utf-8","CODEX_HOME":str(sessions.parent),
                "TASK_HARNESS_LAST_SOURCE":str(bundle/".last-source"),"TASK_BOARD_TEST_URL":base,
                "TASK_BOARD_TEST_TARGET":str(temp/"测试项目乙"),"TASK_BOARD_TEST_STATIC":str(bundle/"static")})
            env.pop("CODEX_SESSIONS_DIR",None)
            with (temp/"server.log").open("wb") as log:
                server=subprocess.Popen([sys.executable,"-X","utf8",str(bundle/"serve.py"),str(temp/"测试项目甲"),"--port",str(port),"--no-open","--no-prompt"],cwd=detached,env=env,stdout=log,stderr=log,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
                try:
                    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
                    for attempt in range(100):
                        self.assertIsNone(server.poll(), "独立服务提前退出")
                        try:
                            with opener.open(base+"/api/snapshot",timeout=.3) as response:
                                self.assertEqual(json.load(response)["contract"]["errors"],[])
                            break
                        except OSError: time.sleep(.05)
                    else: self.fail("独立服务启动超时")
                    probe=subprocess.run([node,str(ROOT/"board/tests/test_live_load.cjs")],env=env,cwd=detached,capture_output=True,timeout=20)
                    self.assertEqual(probe.returncode,0,probe.stdout.decode("utf-8",errors="replace")+probe.stderr.decode("utf-8",errors="replace"))
                    for path, before in originals.items(): self.assertEqual(path.read_bytes(),before,str(path))
                finally:
                    server.terminate(); server.wait(timeout=5)
            # 运行过的发布目录仍可重新构建，运行文件只留本地。
            rebuilt=subprocess.run([sys.executable,str(ROOT/"scripts/build_board_release.py"),"--output",str(detached)],env=env,capture_output=True)
            self.assertEqual(rebuilt.returncode,0,rebuilt.stderr)
