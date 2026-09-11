#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read-only HTTP board. Polls a harness directory. Never writes task files."""
from __future__ import annotations

import argparse
import json
import os
import posixpath
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

HERE = Path(__file__).resolve().parent
STATIC = HERE / "static"
OPTIONAL = ("evidence.jsonl", "reviews.jsonl", "progress.txt", "board.json")
PORT_MIN, PORT_MAX = 8765, 8799


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


def resolve_source(project: Path) -> Path:
    target = project.expanduser().resolve()
    if not target.exists():
        raise ValueError("项目目录不存在: " + str(target))
    if target.name == ".harness":
        return target
    nested = target / ".harness"
    if (nested / "tasks.json").is_file() or not (target / "tasks.json").is_file():
        return nested
    return target


def snapshot(source: Path) -> dict:
    files = {}
    tasks = source / "tasks.json"
    if tasks.is_file():
        files["tasks.json"] = tasks.read_text(encoding="utf-8-sig")
    for name in OPTIONAL:
        fp = source / name
        if fp.is_file():
            files[name] = fp.read_text(encoding="utf-8-sig")
    return {"source": str(source), "files": files}


class Handler(BaseHTTPRequestHandler):
    source = Path(".")
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
            self._send_json(snapshot(self.source))
            return
        name = path.lstrip("/")
        allowed = ("tasks.json",) + OPTIONAL
        if name in allowed:
            fp = self.source / name
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
        self.send_error(405, "read-only")

    def do_PUT(self):
        self.send_error(405, "read-only")

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

    def _send_json(self, obj) -> None:
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def make_server(source: Path, port: int) -> ThreadingHTTPServer:
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


def serve(project: Path, port: int = 0, open_browser: bool = True) -> ThreadingHTTPServer:
    source = resolve_source(project)
    chosen = pick_port(port)
    httpd = make_server(source, chosen)
    url = "http://127.0.0.1:%s/" % chosen
    emit("看板 " + url)
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
    parser.add_argument("project", nargs="?", default=".", help="项目根或 .harness 目录")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--no-open", action="store_true")
    args = parser.parse_args()
    try:
        httpd = serve(Path(args.project), args.port, not args.no_open)
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
