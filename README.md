# Task Harness v3.1 — Codex Native

这是 OpenAI Codex 宿主分支（原 \codex\）。核心协议在 \main\。分支表见 [BRANCHES.md](BRANCHES.md)。

这是 `hdsas2980-cmyk/Task-Harness` 的 Codex 专用适配分支：`codex`。

## 保留的核心能力

- 一轮一任务，依赖门控和优先级调度；
- `tasks.json` 作为唯一真相源；
- `evidence.jsonl` + 独立 `reviews.jsonl` 才能判定 `passed`；
- `pending → active → evidence_ready → passed` 状态机及 `blocked/regressed` 回退；
- ponytail/YAGNI 阶梯；
- 追加式进度日志、可回放验证和破坏性命令护栏；
- 主上下文恒定、任务状态外置的长时工程哲学。

## Codex 专用改动

- 明确把“当前 Codex 任务”定义为一轮，不依赖 Claude Code 会话语义；
- 优先 PowerShell，同时保留 Git Bash/Linux/macOS 的 `init.sh`；
- 评审协议改为独立 Codex 上下文，review 记录增加 `reviewer_context`；
- 删除对 gstack、Claude Skill、CC Switch、MCP 的运行时依赖和兜底暗示；
- 安装脚本只写 `$CODEX_HOME/skills/task-harness`，不创建 Claude/CC Switch 副本；
- 安装前自动把既有 Codex Skill 隔离备份，禁止盲目覆盖；
- 不安装 `commands/`，避免把 Claude 专属 slash command 带入 Codex。

## 安装（只写 Codex）

Windows PowerShell：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1
```

Git Bash/Linux/macOS：

```bash
bash scripts/install.sh
```

目标默认是：

```text
%USERPROFILE%\.codex\skills\task-harness
```

也可以用 `CODEX_HOME` 指定 Codex 根目录。脚本会对既有目标做时间戳备份；它不会读取或写入 `.cc-switch`、`.claude`。

## 使用

安装到 `$CODEX_HOME/skills/task-harness` 后，每个 Codex 任务先按下方“项目看板”用技能绝对路径初始化。不要把工作目录切到 skill，也不要把 `init.ps1` 单独复制到项目——它依赖同目录的 `serve_dashboard.py` 与 `task-harness.html`。

状态文件建议放在项目 `.harness/`：`tasks.json`、`evidence.jsonl`、`reviews.jsonl`、`progress.txt`。

具体规则见 `SKILL.md`、`references/codex-adapter.md` 和 `references/review/`。

## 项目看板

依赖 Python 3（仅标准库）。使用技能绝对路径调用，不把工作目录切到 skill 目录。

- Windows：`& "<skill>/references/templates/init.ps1" -ProjectDir "<项目绝对路径>"`；兼容旧参数 `-HarnessDir`。
- Git Bash/Linux/macOS：`bash "<skill>/references/templates/init.sh" "<项目绝对路径>"`。
- 输入为项目根或 `.harness`；旧版根目录 `tasks.json` 保持原位读取，不迁移。初始无任务也复制空白看板并启动服务，不创建示例任务，不自动打开浏览器。
- 技能只携带一份静态 SPA。初始化把它复制到项目 `.harness/task-harness.html`，然后仅绑定 `127.0.0.1` 提供 HTTP；输出 `DASHBOARD: http://127.0.0.1:<port>/task-harness.html`。
- 编排完成首次自动打开该 URL；后续初始化复用已有端口。`-Open` / `--open` 重新打开；自动化测试用 `-NoOpen` / `--no-open`。Codex 内用浏览器面板打开 http 地址，不要打开 `file://`。
- 更新任务、证据、评审、日志后重新初始化或在页面点「刷新任务」。服务只读，绝不写任务真相源。
- 「载入任务」选择项目任务目录；独立桌面壳 `TaskHarness.exe` 启动时先探测当前工作目录和 exe 所在目录的 `tasks.json`（或 `.harness/tasks.json`），没有再弹出选择框。技能初始化仍可先载入当前 HTTP 项目。
- 页面状态中文，JSON 枚举仍保持英文；已通过只表示任务声明，缺少关联证据及评审必须显示门禁缺口，不代替独立评审。

不要手工再开一套 `python -m http.server`；初始化脚本会复用 `.harness/.dashboard-server.json` 里的本机端口。`.harness/task-harness.html`、`.dashboard-opened` 与 `.dashboard-server.json` 为项目派生产物。初始化不创建任务定义。

测试：`python -m unittest discover -s tests -v`。测试通过不等于独立评审通过。
