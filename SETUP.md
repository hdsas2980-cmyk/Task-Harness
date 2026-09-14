# Task-Harness v3.1 — Codex Native 设置说明

## 目标

本分支 `codex` 面向 Codex 的 task/thread、Windows PowerShell、技能目录和独立评审上下文设计。它保留 v3.1 的问责核心，不把 Claude/CC Switch 的同步机制带进 Codex。

## 安装前检查

```powershell
git --version
python --version  # 需要 Python 3.10+
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
2. 使用 staging 目录复制 `SKILL.md`、`harness_db.py`、`references/`、`scripts/check_task_harness_language.py` 与 `scripts/convert_harness_json.py`，完成后移动到目标；
3. 不安装 `commands/`、`board/`、开发测试或发布构建脚本；
4. 不读取、不写入、不创建 `.cc-switch` 或 `.claude`。

## 项目初始化

技能不再启动看板。唯一真相源是项目 `.harness/harness.db`。JSON/JSONL/TXT 不是活路径。

先按 [中文原字段契约](references/language-contract.md)用 `HarnessDB` 写入项目与任务说明、证据摘要、评审理由及进度正文。旧项目先跑 `scripts/convert_harness_json.py` 一次性导入。尚未执行时，证据/评审可为空，禁止伪装为执行结果。保留 ID、payload 键、机器枚举和原始技术输出；不加 `_zh` 字段，不创建翻译文件。

在项目根目录执行：

```powershell
$CodexRoot = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $HOME '.codex' }
python -X utf8 (Join-Path $CodexRoot 'skills/task-harness/scripts/check_task_harness_language.py') .
```

退出码 `0` 表示结构与最低语言检查通过，`1` 表示契约不合格，`2` 表示无法读取或处理。正常任务禁止传 `--templates`。推进状态前先检查；失败修正源字段后重检，不让看板翻译兜底。通过不等于内容准确或任务通过独立评审。

可视化看板是独立目录 `board/`，不随技能安装：

```powershell
powershell -ExecutionPolicy Bypass -File .\board\start.ps1 -ProjectDir (Get-Location).Path
```

Windows 用该脚本（UTF-8），不要双击 HTML，也不要为了刷新看板再跑技能安装脚本。

## 更新已有安装与看板

拉取 `codex` 分支只更新仓库文件，不会自动更新 `$CODEX_HOME/skills/task-harness`，也不会重启看板。

**技能重大变更必须卸载重装。** 调度协议、任务束、`SKILL.md`、`references/codex-parallel.md` 的改动都算重大变更。只拉仓库、只拷文件、手工覆盖安装目录，agent 仍读旧副本，可能继续使用旧的会话优先规则或混淆 `wait_agent` 与 `wait_threads`。

1. 技能：从更新后的仓库重新执行安装脚本。脚本会先把旧 `$CODEX_HOME/skills/task-harness` 移到 `skill-backups/`，再写入新副本。不要手工覆盖。
2. 源码看板：停止自己启动的旧进程，从更新后的 `board/start.ps1` 重新启动。
3. 独立发布包：在仓库运行 `python -X utf8 scripts/build_board_release.py`，使用生成的完整 `board/release/TaskBoard-windows.zip`，不要混用旧服务端或旧校验器。
4. 在授权范围内检查目标项目的源文件，按错误位置修正中文原字段；安装和看板均不会自动迁移项目数据。

## 评审

实现者把当前任务、变更范围、证据和必要代码交给独立 Codex 上下文。评审者按 `references/review/completion-review.md` 检查，最后输出：

```text
HARNESS_REVIEW: pass|fail | <task-id> | <一句中文理由>
```

没有独立上下文时记为 `blocked`，不要把同轮自检伪装为独立评审。
