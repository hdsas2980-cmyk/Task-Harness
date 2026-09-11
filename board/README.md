# 长任务看板（独立项目）

这不是 Codex skill。技能只负责 `tasks.json` / 证据 / 评审；本目录是单独的只读 Web 看板。

不要把 HTML 拷进项目 `.harness/`，不要随 `scripts/install.ps1` 安装。

## 启动（Windows，注意编码）

脚本按 UTF-8 运行：`chcp 65001` + `PYTHONUTF8=1` + `python -X utf8`。

```bat
board\start.bat -ProjectDir "E:\path\to\project"
```

或：

```powershell
powershell -ExecutionPolicy Bypass -File .\board\start.ps1 -ProjectDir "E:\path\to\project"
```

浏览器打开输出的 `http://127.0.0.1:<port>/`。进程在前台轮询任务目录；改 `tasks.json` 后页面会自己刷新。Ctrl+C 停止。

Git Bash / Linux / macOS：

```bash
bash board/start.sh "/path/to/project"
```

## 行为

| 项 | 说明 |
|----|------|
| 输入 | 项目根或 `.harness`。优先读 `.harness/tasks.json`，旧版根目录 `tasks.json` 保持原位 |
| 协议 | 只读 HTTP，绑定 `127.0.0.1` |
| 更新 | 浏览器每 2 秒拉 `/api/snapshot`，文件变了才重绘 |
| 写入 | 绝不写 `tasks.json` / evidence / reviews / progress |

依赖：Python 3 标准库。
