"""Copy the standalone dashboard SPA and serve it on 127.0.0.1."""
from __future__ import annotations

import argparse
import json
import os
import posixpath
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

STATES = ("pending", "active", "evidence_ready", "passed", "blocked", "regressed")
FILES = {
    "/task-harness.html": ("text/html; charset=utf-8", "task-harness.html"),
    "/tasks.json": ("application/json; charset=utf-8", "tasks.json"),
    "/evidence.jsonl": ("application/octet-stream", "evidence.jsonl"),
    "/reviews.jsonl": ("application/octet-stream", "reviews.jsonl"),
    "/progress.txt": ("text/plain; charset=utf-8", "progress.txt"),
}
PORT_MIN, PORT_MAX = 8765, 8799
WAIT_SECONDS = 3


def local_urlopen(url, timeout=1):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    return opener.open(urllib.request.Request(url, method="GET"), timeout=timeout)


def resolve_paths(project):
    target = Path(project).expanduser().resolve()
    if target.name == ".harness":
        output = source = target
    else:
        output = target / ".harness"
        source = output if (output / "tasks.json").exists() or not (target / "tasks.json").exists() else target
    if not target.exists() and target.name != ".harness":
        raise ValueError("项目目录不存在: " + str(target))
    return output, source


def copy_spa(output):
    src = Path(__file__).with_name("task-harness.html")
    if not src.is_file():
        raise ValueError("缺少看板页面: " + str(src))
    output.mkdir(parents=True, exist_ok=True)
    dest = output / "task-harness.html"
    tmp_name = None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", delete=False, dir=output, prefix=".dash-") as tmp:
            tmp_name = tmp.name
            tmp.write(src.read_bytes())
        os.replace(tmp_name, dest)
    finally:
        if tmp_name and Path(tmp_name).exists():
            Path(tmp_name).unlink()
    return dest


def read_tasks(source):
    path = source / "tasks.json"
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return False
    if not isinstance(raw, dict) or not isinstance(raw.get("tasks"), list):
        return False
    return raw


def print_status(source):
    raw = read_tasks(source)
    if raw is None:
        print("尚未编排任务；已复制空白看板，任务文件未改动。")
        print("EXIT_SIGNAL: false  (完成门禁须由独立评审确认)")
        return
    if raw is False:
        print("任务文件无法解析；已启动看板服务，页面会显示错误。")
        print("EXIT_SIGNAL: false  (完成门禁须由独立评审确认)")
        return
    tasks = raw["tasks"]
    passed = sum(isinstance(t, dict) and t.get("status") == "passed" for t in tasks)
    print("PROGRESS: %s/%s  rev=%s" % (passed, len(tasks), raw.get("rev", 1)))
    if tasks and passed == len(tasks):
        print("EXIT_SIGNAL: true  — 全部任务状态为已通过。")
        print("注意: 看板不代替独立评审；passed 须有对应 evidence 与独立 pass review。")
    else:
        print("EXIT_SIGNAL: false  (完成门禁须由独立评审确认)")
    ids = {t["id"]: t for t in tasks if isinstance(t, dict) and isinstance(t.get("id"), str)}
    eligible = []
    for task in tasks:
        if not isinstance(task, dict) or task.get("status") not in ("pending", "regressed"):
            continue
        deps = task.get("depends_on", [])
        if not isinstance(deps, list):
            continue
        if all(ids.get(dep, {}).get("status") == "passed" for dep in deps if isinstance(dep, str)):
            eligible.append(task)

    def prio(task):
        try:
            value = float(task.get("priority", 999999))
        except (TypeError, ValueError):
            return 999999.0
        return value if value == value else 999999.0

    eligible.sort(key=prio)
    if eligible:
        print("下一个任务: " + json.dumps(eligible[0], ensure_ascii=False))
    for state, label in (("active", "进行中"), ("evidence_ready", "待独立评审"), ("blocked", "已阻塞")):
        items = [t["id"] for t in tasks if isinstance(t, dict) and t.get("status") == state and isinstance(t.get("id"), str)]
        if items:
            print(label + ": " + ", ".join(items))
    if not tasks:
        print("尚未编排任务；已复制空白看板，任务文件未改动。")


def pid_alive(pid):
    if not isinstance(pid, int) or pid <= 0:
        return False
    if os.name != "nt":
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False
    import ctypes
    handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
    if not handle:
        return False
    ctypes.windll.kernel32.CloseHandle(handle)
    return True


def http_ok(url):
    try:
        with local_urlopen(url, timeout=1) as resp:
            return getattr(resp, "status", 200) == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def meta_file(output):
    return output / ".dashboard-server.json"


def load_meta(output):
    path = meta_file(output)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def save_meta(output, data):
    meta_file(output).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def stop_pid(pid):
    if not isinstance(pid, int) or pid <= 0:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True, text=True)
    else:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
    deadline = time.time() + 2
    while time.time() < deadline and pid_alive(pid):
        time.sleep(0.05)


def dashboard_url(port):
    return "http://127.0.0.1:%s/task-harness.html" % port


def reuse_server(output, source):
    meta = load_meta(output)
    if not meta:
        return None
    port, pid = meta.get("port"), meta.get("pid")
    if not isinstance(port, int) or not isinstance(pid, int):
        return None
    if str(meta.get("source")) != str(source) or str(meta.get("output")) != str(output):
        if pid_alive(pid):
            stop_pid(pid)
        return None
    url = dashboard_url(port)
    if pid_alive(pid) and http_ok(url):
        return url
    if pid_alive(pid):
        stop_pid(pid)
    return None


class HarnessHandler(BaseHTTPRequestHandler):
    source = None
    output = None

    def log_message(self, format, *args):
        return

    def _file_for(self, path):
        path = posixpath.normpath(unquote(urlparse(path).path))
        if path in ("/", "/index.html"):
            path = "/task-harness.html"
        spec = FILES.get(path)
        if not spec:
            return None, None
        ctype, name = spec
        root = self.output if name == "task-harness.html" else self.source
        fp = root / name
        if not fp.is_file():
            return None, None
        return ctype, fp

    def do_GET(self):
        ctype, fp = self._file_for(self.path)
        if fp is None:
            self.send_error(404, "Not found")
            return
        data = fp.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_HEAD(self):
        ctype, fp = self._file_for(self.path)
        if fp is None:
            self.send_error(404, "Not found")
            return
        size = fp.stat().st_size
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(size))
        self.end_headers()


def listen(port, output, source):
    HarnessHandler.output = output
    HarnessHandler.source = source
    server = ThreadingHTTPServer(("127.0.0.1", port), HarnessHandler)
    server.serve_forever()


def spawn_server(output, source):
    reused = reuse_server(output, source)
    if reused:
        return reused
    script = str(Path(__file__).resolve())
    for port in range(PORT_MIN, PORT_MAX + 1):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("127.0.0.1", port))
        except OSError:
            sock.close()
            continue
        sock.close()
        cmd = [sys.executable, script, "--listen", "--port", str(port), "--output", str(output), "--source", str(source)]
        kwargs = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
        if os.name == "nt":
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            kwargs["start_new_session"] = True
            kwargs["close_fds"] = True
        proc = subprocess.Popen(cmd, **kwargs)
        url = dashboard_url(port)
        deadline = time.time() + WAIT_SECONDS
        while time.time() < deadline:
            if proc.poll() is not None:
                break
            if http_ok(url):
                save_meta(output, {"port": port, "pid": proc.pid, "source": str(source), "output": str(output)})
                # Intentionally detach: parent must not kill or warn about the listener.
                if proc.returncode is None:
                    proc.returncode = 0
                return url
            time.sleep(0.05)
        stop_pid(proc.pid)
    raise ValueError("无法在 127.0.0.1:8765-8799 启动看板服务")


def serve(project, no_open=False, force_open=False):
    output, source = resolve_paths(project)
    dest = copy_spa(output)
    url = spawn_server(output, source)
    print("DASHBOARD: " + url)
    print_status(source)
    raw = read_tasks(source)
    has_work = isinstance(raw, dict) and bool(raw.get("tasks"))
    marker = output / ".dashboard-opened"
    if has_work and not no_open and (force_open or not marker.exists()):
        if webbrowser.open(url):
            marker.write_text(url, encoding="utf-8")
        else:
            print("未能自动打开；请打开 DASHBOARD 地址。")
    return dest


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="在 127.0.0.1 打开项目任务看板")
    parser.add_argument("--listen", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--port", type=int, help=argparse.SUPPRESS)
    parser.add_argument("--output", help=argparse.SUPPRESS)
    parser.add_argument("--source", help=argparse.SUPPRESS)
    parser.add_argument("project", nargs="?", default=".")
    parser.add_argument("--no-open", action="store_true")
    parser.add_argument("--open", action="store_true")
    args = parser.parse_args()
    if args.listen:
        if not args.port or not args.output or not args.source:
            parser.exit(1, "listen 参数不完整\n")
        listen(args.port, Path(args.output), Path(args.source))
        return
    try:
        serve(args.project, args.no_open, args.open)
    except (OSError, ValueError) as exc:
        parser.exit(1, "看板启动失败: " + str(exc) + "\n")


if __name__ == "__main__":
    main()
