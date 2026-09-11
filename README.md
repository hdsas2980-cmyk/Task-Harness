# Task Harness v3.1 — DeepSeek Harness (DSH)

这是 DeepSeek Harness 宿主分支。口头常说的 **dhs** 对应本分支 `dsh`。核心协议在 `main`。

默认安装到 DSH 用户技能根（文件系统 skill 提供方会扫描）：

```text
%USERPROFILE%\.dsh\skills\task-harness
```

项目级也可放：

```text
<repo>/.dsh/skills/task-harness
```

不要写入 `~/.claude`、`$CODEX_HOME`、`~/.trae-cn` 或 `~/.workbuddy`。也不默认写入 `~/.agents/skills`，以免污染共享 agent 目录。分支表见 [BRANCHES.md](BRANCHES.md)。

## 安装

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install.ps1
```

```bash
bash scripts/install.sh
```

可用 `DSH_HOME` 覆盖配置根。覆盖前备份到 `~/.dsh/skill-backups/`。

DSH 只识别单层 `<root>/<name>/SKILL.md`。frontmatter 需要 kebab-case 的 `name` 与 `description`。

## 使用

1. 模板拷到项目 `.harness/`，起草 `tasks.json`。
2. 每个 DSH 会话只推进一个任务。DSH 自带的 `tool-ralph` 是连推循环，**不能**代替 evidence + 独立评审。
3. `evidence_ready` 后，用新会话或只读 subagent 按 `references/review/completion-review.md` 评审。
4. 只回收一行 `HARNESS_REVIEW:`。

初始化：

```powershell
& "$env:USERPROFILE\.dsh\skills\task-harness\references\templates\init.ps1" -ProjectDir "<项目绝对路径>"
```

协议细节见 [SKILL.md](SKILL.md)。
