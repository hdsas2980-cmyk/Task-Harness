# Task-Harness v3.1 — Codex Native 设置说明

## 目标

本分支 `codex-native-v3.1` 面向 Codex 的 task/thread、Windows PowerShell、技能目录和独立评审上下文设计。它保留 v3.1 的问责核心，不把 Claude/CC Switch 的同步机制带进 Codex。

## 安装前检查

```powershell
git --version
python --version
```

不需要为了 Harness 安装 gstack、MCP、Claude Code 或额外运行时。项目已有测试工具优先。

## 安装

从仓库根目录运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1
```

目标：`%USERPROFILE%\.codex\skills\task-harness`；设置 `CODEX_HOME` 后使用其指定根目录。

安装行为：

1. 既有 Codex `task-harness` 目录先移动到 `%CODEX_HOME%\skill-backups\` 的时间戳目录；
2. 使用 staging 目录复制 `SKILL.md` 和 `references/`，完成后原子移动到目标；
3. 不安装 `commands/`；
4. 不读取、不写入、不创建 `.cc-switch` 或 `.claude`。

## 项目初始化

建议把运行状态放到项目 `.harness/`，不要把大日志放进对话上下文：

```powershell
New-Item -ItemType Directory -Force .harness | Out-Null
Copy-Item <repo>\references\templates\tasks.json .harness\tasks.json
Copy-Item <repo>\references\templates\progress.txt .harness\progress.txt
Copy-Item <repo>\references\templates\evidence.jsonl .harness\evidence.jsonl
Copy-Item <repo>\references\templates\reviews.jsonl .harness\reviews.jsonl
Copy-Item <repo>\references\templates\init.ps1 .harness\init.ps1
```

每一轮在项目根执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\.harness\init.ps1 -HarnessDir (Get-Location).Path
```

脚本只输出进度、待评审/阻塞项和一个 eligible 任务。

## 评审

实现者把当前任务、变更范围、证据和必要代码交给独立 Codex 上下文。评审者按 `references/review/completion-review.md` 检查，最后输出：

```text
HARNESS_REVIEW: pass|fail | <task-id> | <一句理由>
```

没有独立上下文时记为 `blocked`，不要把同轮自检伪装为独立评审。
