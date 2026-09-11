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

- 多会话编成、会话命名与多子代理并行见 `references/codex-parallel.md`；并行 = 多会话各持一卡，不是一轮多任务。
- 明确把“当前 Codex 任务”定义为一轮，不依赖 Claude Code 会话语义；
- 优先 PowerShell，Git Bash/Linux/macOS 用 POSIX 工具；可视化看板在独立目录 board/，不随技能安装；
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

安装到 `$CODEX_HOME/skills/task-harness` 后，每个 Codex 任务读取项目 `.harness/`（或根目录）的 `tasks.json`、`evidence.jsonl`、`reviews.jsonl`、`progress.txt`。不要把工作目录切到 skill。

具体规则见 `SKILL.md`、`references/codex-adapter.md` 和 `references/review/`。

## 可视化看板（独立目录，不随技能安装）

看板在仓库 `board/`，不是 skill 的一部分。`scripts/install.ps1` 不会安装它。

```powershell
powershell -ExecutionPolicy Bypass -File .\board\start.ps1 -ProjectDir "<项目绝对路径>"
```

浏览器打开 `http://127.0.0.1:<port>/`。页面轮询任务目录，改 `tasks.json` 会自己刷新。Windows 请走 `board\start.ps1` / `start.bat`（UTF-8），避免控制台乱码。

测试：`python -m unittest discover -s tests -v`。测试通过不等于独立评审通过。
