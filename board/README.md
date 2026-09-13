# 长任务看板（独立项目）

这不是 Codex skill。技能只负责 `.harness/harness.db`；本目录是单独的只读 Web 看板。JSON 活路径已废弃，不兼容回退。

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

- 传了 `-ProjectDir`：直接轮询该项目的 `.harness/harness.db`。没有数据库就是未初始化，不会读旧 JSON。
- 没传：控制台询问目录（回车=上次路径，`s`=页面选会话）。页面里仍可改目录或选会话。

进程在前台轮询 `.harness/harness.db`；改库后页面会自己刷新。Ctrl+C 停止。

Git Bash / Linux / macOS：

```bash
bash board/start.sh
bash board/start.sh "/path/to/project"
```

## 当前版本与历史恢复

页面底栏标识为 **看板 UI 2026.09.12-r2**。历史要求与恢复边界见 [重构记录](RECOVERY.md)。如果你看到的是 EXE 窗口，或点击“载入任务”直接弹出文件窗口，则不是本次交付的这套载入流程。

源码启动需要保留本仓库目录结构；需要单独拷走时，使用完整 ZIP，而不是只拷 `board/` 目录遗漏校验器。解压 `TaskBoard-windows.zip` 后，从 `TaskBoard` 目录双击 `start.bat`，或者在该目录运行 `powershell -ExecutionPolicy Bypass -File .\start.ps1 -NoPrompt`。发布包内无需仓库父目录。

## 载入任务

| 路径 | 行为 |
|------|------|
| 指定目录 | 粘贴项目根 / `.harness` 绝对路径，或点「浏览」弹出本机文件夹对话框 |
| Codex 会话 | 优先使用 `CODEX_SESSIONS_DIR`，其次 `CODEX_HOME/sessions`，默认 `%USERPROFILE%\.codex\sessions`，按 `cwd` 汇总，探测 `cwd/.harness/harness.db` |
| 自动 | 启动参数优先；否则若最近会话已有看板则自动选中；否则打开选择面板 |

“载入任务”或快捷键 `L` 先打开会话面板并读取会话列表，不会直接打开文件窗口。按历史版式，上方是“1 指定任务目录”，下方是“2 从 Codex 会话中选择”；自动扫描会话保留，只有“浏览”才打开系统目录框。读取失败会在面板内显示原因，可刷新重试；慢轮询不会阻塞面板打开，关闭也不依赖请求完成。

会话只读，不会写 `harness.db`，也不会把旧 JSON 当活数据。

## 行为

| 项 | 说明 |
|----|------|
| 输入 | 项目根或 `.harness`。只读 `.harness/harness.db`。没有数据库 = 未初始化，禁止回退 JSON/JSONL/TXT。旧项目先跑 `python -X utf8 scripts/convert_harness_json.py <项目根>` 整目录导入 |
| 协议 | 只读 HTTP，绑定 `127.0.0.1`。`POST /api/source` 只切换内存里的轮询目录 |
| 更新 | 浏览器每 2 秒拉 `/api/snapshot`，只返回结构化快照，不生成完整 JSON/JSONL 大文本 |
| 写入 | 看板绝不写任务真相源；数据库由任务写入方通过 `harness_db.py` 或 `HarnessDB` 更新 |

依赖：Python 3.10+ 标准库。
## 中文原字段与只读契约

看板不翻译任务内容。服务端读取结构化快照，并用技能的 `scripts/check_task_harness_language.py` 做中文契约检查。保留原始中文字段与未知审计字段，不展示英文兜底、不读取翻译文件、不自动改写数据。技术细节里的命令、原始测试输出、ID、路径、哈希保持原文。

- 任务列表按中文阶段分组；卡片底部恢复四段状态条、审计简报、统一证据评审按钮与轨迹链接。
- 点击卡片上的按钮打开当前任务抽屉，摘要直接取中文 `summary` / `reason`；原始技术细节折叠展示。
- 任务轨迹没有下拉选择，跟随当前行，只关联精确任务 ID 的证据和评审，保持当前快照卡与审计时间轴结构，不推测历史状态。
- 进度日志恢复日志概览、最近 8 条非空原始行及折叠原文，来源行号保持真实。技能仍要求按 `## 时间 | task-id | 类型` 写入中文日志。
- 所有抽屉支持关闭按钮、遮罩和退出键；载入失败不会让用户无法关闭。

## 统一发布

在技能仓库运行：

```text
python -X utf8 scripts/build_board_release.py
```

生成 `board/release/TaskBoard` 和 `board/release/TaskBoard-windows.zip`。发布脚本仅从指定源码复制，附带同一份语言校验器和面向解压目录的独立使用说明（来源 `RELEASE-NOTES.md`）；`manifest.json` 记录每个文件的 SHA-256，打包后逐字节核对目录与 ZIP。正常运行生成的 `.last-source` 和已知模块字节码缓存留在本地且不进入 ZIP；其他未知残留文件仍会阻断打包，不静默混入发布物。发布目录和 ZIP 是生成物，不是另一套源码。

## 本次布局调整

- **阶段分组**：默认全部折叠，点击标题展开；展开另一阶段会收起前一个，再次点击可全部收起。轮询保留展开状态，切换任务来源后恢复折叠。键盘切换当前行时展开其所在阶段，阶段折叠本身不改变当前行。
- **键盘说明**：移至顶部“键盘操作”展开面板；左下不再占位，当前行详情向下延伸。
- **已通过**：左上增加数量与筛选，直接按任务的 `passed` 状态统计，不将待评审算作通过。

其余历史卡片、证据评审抽屉、任务轨迹和进度日志布局保持不变。

## 桌面入口（可选，不替代 Web）

Web ZIP 入口不变：`board/start.ps1` / `start.bat` / `start.sh`。

Windows 另提供单文件 `TaskBoard.exe`：

```text
python -X utf8 scripts/build_board_desktop.py
```

输出在 `board/release-desktop/`，只含 `TaskBoard.exe` 与 `manifest.json`。这不是安装包：不生成 MSI/NSIS，不携带 WebView2 Runtime/安装器/bootstrapper，只使用目标机器已安装的系统 WebView2。缺失 WebView2 时弹出中文诊断并退出，不会下载。

桌面入口只读 `.harness/harness.db`（schema v1）。没有数据库就是未初始化，禁止回退 JSON/JSONL。它不会写任务、证据、评审、进度，也不会执行 `import_legacy`。旧文件请用仓库里的转换脚本一次性导入。
