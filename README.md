# Task Harness v3.1 — Codex Native

这是 `hdsas2980-cmyk/Task-Harness` 的 Codex 专用适配分支：`codex-native-v3.1`。

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

在项目中初始化 `.harness/`，复制 `references/templates/` 的模板，然后每个 Codex 任务先运行：

```powershell
powershell -ExecutionPolicy Bypass -File <绝对路径>\references\templates\init.ps1
```

或：

```bash
bash <绝对路径>/references/templates/init.sh
```

具体规则见 `SKILL.md`、`references/codex-adapter.md` 和 `references/review/`。
