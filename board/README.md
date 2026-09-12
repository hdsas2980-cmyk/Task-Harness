# 长任务看板（独立项目）

这不是 Codex skill。技能只负责 `tasks.json` / 证据 / 评审；本目录是单独的只读 Web 看板。

不要把 HTML 拷进项目 `.harness/`，不要随 `scripts/install.ps1` 安装。

## 启动（Windows，注意编码）

脚本按 UTF-8 运行：`chcp 65001` + `PYTHONUTF8=1` + `python -X utf8`。`start.ps1` 只用 ASCII（带 UTF-8 BOM），避免 Windows PowerShell 5.1 按系统代码页把中文拆成语法错误。

双击 `board\start.bat` 会交互询问目录：回车用上次路径，输入 `s` 则打开页面从 Codex 会话选择。控制台会打印前端地址、后端地址、上次路径和当前路径。失败时窗口不会立刻关掉。

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
- 没传：控制台询问目录（回车=上次路径，`s`=页面选会话）。页面里仍可改目录或选会话。

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

依赖：Python 3.10+ 标准库。
## 中文原字段与只读契约

看板不翻译任务内容。服务端复用技能的 `scripts/check_task_harness_language.py`，检查任务、证据、评审和进度文件；失败时界面显示源文件位置，不展示英文兜底、不读取翻译文件、不自动改写数据。技术细节里的命令、原始测试输出、ID、路径、哈希保持原文。

- 任务列表按中文阶段分组；卡片底部是状态阶段条（不是估算完成百分比）、证据和评审按钮。
- 点击卡片上的按钮打开当前任务抽屉，摘要直接取中文 `summary` / `reason`；原始技术细节折叠展示。
- 任务轨迹没有下拉选择，跟随当前行，只关联精确任务 ID 的进度段、证据和评审，不推测历史状态。
- 进度日志按技能规定的 `## 时间 | task-id | 类型` 分段，最近记录优先，支持展开和查看原文。
- 所有抽屉支持关闭按钮、遮罩和退出键；载入失败不会让用户无法关闭。

## 统一发布

在技能仓库运行：

```text
python -X utf8 scripts/build_board_release.py
```

生成 `board/release/TaskBoard` 和 `board/release/TaskBoard-windows.zip`。发布脚本仅从指定源码复制，附带同一份语言校验器；`manifest.json` 记录每个文件的 SHA-256，打包后逐字节核对目录与 ZIP。未知残留文件会阻断打包，不静默混入发布物。发布目录和 ZIP 是生成物，不是另一套源码。
