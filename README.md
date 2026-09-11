# Task Harness v3.1 — WorkBuddy

这是 WorkBuddy 宿主分支。核心协议在 `main`。本分支只安装到用户技能目录：

```text
%USERPROFILE%\.workbuddy\skills\task-harness
```

不要写入 `~/.claude`、`$CODEX_HOME` 或 `~/.trae-cn`。分支表见 [BRANCHES.md](BRANCHES.md)。

## 安装

Windows PowerShell：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install.ps1
```

Git Bash / Linux / macOS：

```bash
bash scripts/install.sh
```

覆盖前会把已有技能备份到 `~/.workbuddy/skill-backups/`。可用 `WORKBUDDY_HOME` 覆盖根目录。

装完后重载 WorkBuddy 技能面板，确认 `task-harness` 出现在用户技能里。

## 使用

1. 把 `references/templates/` 拷到项目 `.harness/`，起草 `tasks.json`。
2. 每个 WorkBuddy 会话只推进一个任务。
3. 跑 `verify`，追加 `evidence.jsonl`，状态置 `evidence_ready`。
4. 开一个**新的** WorkBuddy 会话做独立评审，只给任务对象、evidence、diff 和 `references/review/completion-review.md`。
5. 回收 `HARNESS_REVIEW:` 契约行后再改 `passed`。

初始化：

```powershell
& "$env:USERPROFILE\.workbuddy\skills\task-harness\references\templates\init.ps1" -ProjectDir "<项目绝对路径>"
```

协议细节见 [SKILL.md](SKILL.md)。
