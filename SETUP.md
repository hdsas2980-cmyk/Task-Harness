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

不要单独复制 init.ps1；它需要同目录的生成器与模板。通过已安装技能绝对路径调用：

```powershell
$skill = Join-Path $(if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $HOME ".codex" }) "skills/task-harness"
& (Join-Path $skill "references/templates/init.ps1") -ProjectDir (Get-Location).Path
```

初始化自动创建 `.harness/task-harness.html`。完成 tasks.json 编排后再次调用，首次自动打开项目页面；之后仅更新快照。可用 `-Open` 重新打开，测试用 `-NoOpen`。不创建示例任务，不修改任务真相源。

每次更新任务、证据、评审或日志后重新调用以刷新内嵌快照。双击 HTML 即可查看；实时读取需授权选择目录或通过 HTTP 打开。完整说明见 SKILL.md 的“项目看板”。

Git Bash/Linux/macOS：

```bash
bash "$HOME/.codex/skills/task-harness/references/templates/init.sh" "$PWD"
```

## 评审

实现者把当前任务、变更范围、证据和必要代码交给独立 Codex 上下文。评审者按 `references/review/completion-review.md` 检查，最后输出：

```text
HARNESS_REVIEW: pass|fail | <task-id> | <一句理由>
```

没有独立上下文时记为 `blocked`，不要把同轮自检伪装为独立评审。
