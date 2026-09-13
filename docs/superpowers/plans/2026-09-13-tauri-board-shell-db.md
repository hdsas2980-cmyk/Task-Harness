# Task Harness 看板 Tauri 壳 Implementation Plan（数据库优先）

> **For agentic workers:** 按本计划实现；旧计划 `docs/superpowers/plans/2026-09-13-tauri-board-shell.md` 已废止。

**Goal:** 保留现有 Web 看板的同时，新增只依赖系统 WebView2 的 Windows 单文件 `TaskBoard.exe`。主存储为 `harness.db` schema v1。

**Spec:** `docs/superpowers/specs/2026-09-13-tauri-board-shell-db-design.md`

**Architecture:** `board/start.ps1` + Python HTTP + ZIP 不变。新增 `board/tauri/` Tauri v2。Rust 在 `127.0.0.1:8765-8799` 提供只读 HTTP，编译期嵌入 `board/static`，窗口加载本地 URL。用 `rusqlite` `mode=ro` 读 `harness.db`。无数据库文件就是未初始化，禁止回退 JSON/JSONL/TXT。不写库、不导入、不携带 WebView2。

## Global Constraints

- 规范 snapshot 跟随 `harness_db.read_snapshot()`：`tasks` 为数组，`project` 在 `meta`。
- 禁止复制 `board/serve.py::_snapshot_from_db` 的 id 字典 / `board` 表 / 跳过契约。
- 禁止 `immutable=1`、禁止读写连接建库、禁止 `import_legacy`。
- 最近来源只写 `%APPDATA%\\TaskHarness\\TaskBoard\\last-source.txt`。
- `bundle.active=false`，`webviewInstallMode.type=skip`。
- 不回退或覆盖工作区其它未提交看板/UI 改动；共用前端只做 snapshot 适配。
- Web ZIP 脚本保持独立。

## File Map

- Create: `board/tauri/package.json`、`src-tauri/*`
- Create: `scripts/build_board_desktop.py`
- Create: `board/tauri/tests/test_desktop_build.py`、`test_snapshot_parity.py`
- Modify: `board/static/app.js`（数组+`meta.project`+`revision` stamp）
- Modify: `board/.gitignore`、`board/README.md`（追加桌面入口，不改 Web 发布链）

## Tasks

1. Tauri 工程、资源嵌入、无安装包/无 WebView2 配置。
2. 只读来源解析、SQLite snapshot、禁止 JSON 回退、结构化中文契约。
3. 会话扫描、原生目录选择、最近来源。
4. 回环 HTTP 与前端适配。
5. 桌面发布脚本与回归测试。
