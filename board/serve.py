#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read-only HTTP board. Polls a harness directory. Never writes task files."""
from __future__ import annotations

import argparse
import json
import os
import posixpath
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from pick_dir import pick_directory_subprocess  # noqa: E402
from sessions import list_session_catalog, resolve_source  # noqa: E402

STATIC = HERE / "static"
OPTIONAL = ("evidence.jsonl", "reviews.jsonl", "progress.txt", "board.json")
PORT_MIN, PORT_MAX = 8765, 8799
SOURCE_LOCK = threading.Lock()
PICK_LOCK = threading.Lock()


def configure_stdio() -> None:
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    os.environ.setdefault("PYTHONUTF8", "1")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def emit(msg: str) -> None:
    data = (msg + "\n").encode("utf-8", errors="replace")
    buf = getattr(sys.stdout, "buffer", None)
    if buf is not None:
        buf.write(data)
        buf.flush()
        return
    print(msg)


def snapshot(source: Path | None) -> dict:
    if source is None:
        return {"source": None, "files": {}}
    files = {}
    tasks = source / "tasks.json"
    if tasks.is_file():
        files["tasks.json"] = tasks.read_text(encoding="utf-8-sig")
    for name in OPTIONAL:
        fp = source / name
        if fp.is_file():
            files[name] = fp.read_text(encoding="utf-8-sig")
    return {"source": str(source), "files": files}


def bind_source(path_str: str) -> Path:
    raw = str(path_str or "").strip()
    if not raw:
        raise ValueError("请提供项目根或 .harness 目录")
    source = resolve_source(Path(raw), must_exist=True)
    with SOURCE_LOCK:
        Handler.source = source
    return source


class Handler(BaseHTTPRequestHandler):
    source: Path | None = None
    static = STATIC

    def log_message(self, format, *args):
        return

    def do_GET(self):
        path = posixpath.normpath(unquote(urlparse(self.path).path))
        if path in ("/", "/index.html", "/task-harness.html"):
            self._send_file(self.static / "index.html", "text/html; charset=utf-8")
            return
        if path == "/app.js":
            self._send_file(self.static / "app.js", "text/javascript; charset=utf-8")
            return
        if path == "/api/snapshot":
            with SOURCE_LOCK:
                source = self.source
            self._send_json(snapshot(source))
            return
        if path == "/api/sessions":
            with SOURCE_LOCK:
                source = self.source
            self._send_json(list_session_catalog(current_source=source))
            return
        name = path.lstrip("/")
        allowed = ("tasks.json",) + OPTIONAL
        if name in allowed:
            with SOURCE_LOCK:
                source = self.source
            if source is None:
                self.send_error(404, "Not found")
                return
            fp = source / name
            if not fp.is_file():
                self.send_error(404, "Not found")
                return
            if name.endswith(".json"):
                ctype = "application/json; charset=utf-8"
            elif name.endswith(".jsonl"):
                ctype = "application/octet-stream"
            else:
                ctype = "text/plain; charset=utf-8"
            self._send_file(fp, ctype)
            return
        self.send_error(404, "Not found")

    def do_POST(self):
        path = posixpath.normpath(unquote(urlparse(self.path).path))
        if path == "/api/source":
            self._post_source()
            return
        if path == "/api/pick-dir":
            self._post_pick_dir()
            return
        self.send_error(405, "read-only")

    def do_PUT(self):
        self.send_error(405, "read-only")

    def _post_source(self):
        try:
            body = self._read_json()
            path = body.get("path") or body.get("cwd") or body.get("source") or ""
            source = bind_source(str(path))
        except ValueError as exc:
            self._send_json({"error": str(exc)}, 400)
            return
        except json.JSONDecodeError:
            self._send_json({"error": "JSON 无效"}, 400)
            return
        data = snapshot(source)
        emit("轮询 " + str(source))
        self._send_json(data)

    def _post_pick_dir(self):
        if not PICK_LOCK.acquire(blocking=False):
            self._send_json({"error": "已有目录对话框打开", "cancelled": True}, 409)
            return
        try:
            path = pick_directory_subprocess("选择 harness / 项目目录")
        finally:
            PICK_LOCK.release()
        if not path:
            self._send_json({"cancelled": True})
            return
        self._send_json({"path": path, "cancelled": False})

    def _read_json(self) -> dict:
        raw_len = int(self.headers.get("Content-Length") or 0)
        if raw_len > 1_000_000:
            raise ValueError("请求过大")
        raw = self.rfile.read(raw_len) if raw_len else b"{}"
        data = json.loads(raw.decode("utf-8-sig") or "{}")
        if not isinstance(data, dict):
            raise ValueError("JSON 必须是对象")
        return data

    def _send_file(self, fp: Path, ctype: str) -> None:
        if not fp.is_file():
            self.send_error(404, "Not found")
            return
        data = fp.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_json(self, obj, code: int = 200) -> None:
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def make_server(source: Path | None, port: int) -> ThreadingHTTPServer:
    Handler.source = source
    Handler.static = STATIC
    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def pick_port(preferred: int) -> int:
    if preferred:
        return preferred
    import socket
    for port in range(PORT_MIN, PORT_MAX + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise ValueError("无法在 127.0.0.1:8765-8799 找到空闲端口")


def serve(project: Path | None, port: int = 0, open_browser: bool = True) -> ThreadingHTTPServer:
    source = resolve_source(project, must_exist=True) if project is not None else None
    chosen = pick_port(port)
    httpd = make_server(source, chosen)
    url = "http://127.0.0.1:%s/" % chosen
    emit("看板 " + url)
    if source is None:
        emit("未绑定任务目录，请在页面指定 harness 或选择 Codex 会话。")
    else:
        emit("轮询 " + str(source))
    emit("只读，不写 tasks.json。Ctrl+C 停止。")
    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:
            emit("未能自动打开浏览器，请手动打开上面的地址。")
    return httpd


def main() -> None:
    configure_stdio()
    parser = argparse.ArgumentParser(description="只读轮询任务看板")
    parser.add_argument("project", nargs="?", default=None, help="项目根或 .harness 目录；省略则在页面选择")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--no-open", action="store_true")
    args = parser.parse_args()
    project = Path(args.project) if args.project else None
    try:
        httpd = serve(project, args.port, not args.no_open)
    except (OSError, ValueError) as exc:
        emit("看板启动失败: " + str(exc))
        sys.exit(1)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        emit("已停止")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
