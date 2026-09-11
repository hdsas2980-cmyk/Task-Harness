# 长任务看板（独立项目）

这不是 Codex skill。技能只负责 `tasks.json` / 证据 / 评审；本目录是单独的只读 Web 看板。

不要把 HTML 拷进项目 `.harness/`，不要随 `scripts/install.ps1` 安装。

## 启动（Windows，注意编码）

脚本按 UTF-8 运行：`chcp 65001` + `PYTHONUTF8=1` + `python -X utf8`。

```bat
board\start.bat
board\start.bat -ProjectDir "E:\path\to\project"
```

或：

```powershell
powershell -ExecutionPolicy Bypass -File .\board\start.ps1
powershell -ExecutionPolicy Bypass -File .\board\start.ps1 -ProjectDir "E:\path\to\project"
```

浏览器打开输出的 `http://127.0.0.1:<port>/`。

- 传了 `-ProjectDir`：直接轮询该项目的 `.harness`（或根目录 `tasks.json`）。
- 没传：页面「载入任务」指定绝对路径，或从本机 Codex 会话选择工作目录。最近一条会话若已有 `tasks.json`，会自动载入。

进程在前台轮询任务目录；改 `tasks.json` 后页面会自己刷新。Ctrl+C 停止。

Git Bash / Linux / macOS：

```bash
bash board/start.sh
bash board/start.sh "/path/to/project"
```

## 载入任务

| 路径 | 行为 |
|------|------|
| 指定目录 | 粘贴项目根 / `.harness` 绝对路径，或点「浏览」弹出本机文件夹对话框 |
| Codex 会话 | 扫描 `%USERPROFILE%\.codex\sessions`（可用 `CODEX_SESSIONS_DIR`），按 `cwd` 汇总，探测 `cwd/.harness/tasks.json` 或 `cwd/tasks.json` |
| 自动 | 启动参数优先；否则若最近会话已有看板则自动选中；否则打开选择面板 |

会话只读，不会改 jsonl / 不会写 `tasks.json`。

## 行为

| 项 | 说明 |
|----|------|
| 输入 | 项目根或 `.harness`。优先读 `.harness/tasks.json`，旧版根目录 `tasks.json` 保持原位 |
| 协议 | 只读 HTTP，绑定 `127.0.0.1`。`POST /api/source` 只切换内存里的轮询目录 |
| 更新 | 浏览器每 2 秒拉 `/api/snapshot`，文件变了才重绘 |
| 写入 | 绝不写 `tasks.json` / evidence / reviews / progress |

依赖：Python 3 标准库。
