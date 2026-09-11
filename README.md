# Task Harness v3.1

长时运行任务的最小骨架。一轮一任务、状态落盘、证据加独立评审判定完成，主会话上下文不随任务数增长。

`main` 只放**宿主无关的核心协议**。要装进某个 ADE / IDE，请切到对应分支，不要把 Claude 斜杠命令、Codex 安装路径或 TRAE 子智能体混进 `main`。

完整分支表见 [BRANCHES.md](BRANCHES.md)。新宿主适配见 [docs/ADAPTER.md](docs/ADAPTER.md)。

## 分支速查

| 你用的环境 | 检出 |
|------------|------|
| 只读协议 / 抄模板 / 写新适配 | `main` |
| Claude Code | `claude` |
| OpenAI Codex | `codex` |
| TRAE / Trae Work | `traework` |
| WorkBuddy | `workbuddy` |
| DeepSeek Harness（DSH / dhs） | `dsh` |

```bash
git clone https://github.com/hdsas2980-cmyk/Task-Harness.git
cd Task-Harness
git checkout <分支名>
```

宿主分支里有各自的 `scripts/install.ps1` 与 `scripts/install.sh`。`main` 没有安装器，因为它不写入任何 IDE 目录。

## 哲学

最小的骨架换最大的问责：

- **一轮一任务**（ralph）——每个任务在 fresh context 里推进，只加载单任务，结尾输出 `EXIT_SIGNAL` 状态块。
- **存在性先于实现**（ponytail）——7 级懒惰阶梯从源头砍掉伪任务；绝不为精简砍掉验证、安全、错误处理。
- **证据加独立评审判定完成**——`passed` 必须同时持有一条 evidence 记录加一条独立 `pass` 评审记录；实现者不等于评审者。

协议正文见 [SKILL.md](SKILL.md)。方法论背景见 [references/methodology.md](references/methodology.md)。

## `main` 里有什么

```
SKILL.md                 核心协议：不变式 / 态机 / 三相 / 护栏 / 契约
BRANCHES.md              分支职责与旧名对照
docs/ADAPTER.md          新增 ADE 分支的检查清单
LICENSE                  MIT-0
references/methodology.md
references/review/       内联规格评审 + 完成评审（改编自 gstack，无运行时依赖）
references/templates/    项目 .harness 模板
  tasks.json             唯一任务真相源
  evidence.jsonl / reviews.jsonl / progress.txt
  init.py                紧凑状态（不改任务文件）
  init.sh / init.ps1     默认启动本地看板；可用 --status-only 只要紧凑状态
  serve_dashboard.py     127.0.0.1 只读 HTTP 看板
  task-harness.html      看板 SPA
  next-step.md           单步 / 并行 / 连推提示词（无宿主斜杠命令）
tests/                   看板回归
```

`main` **没有** `commands/`、`agents/`、指向 `~/.claude` / `$CODEX_HOME` 的安装脚本。那些属于宿主分支。

## 在项目里使用核心协议

不装 IDE 技能时，把模板拷到项目后按三相推进即可：

```powershell
# 在目标项目
New-Item -ItemType Directory -Force .harness | Out-Null
Copy-Item <repo>\references\templates\* .harness -Force
# 编辑 .harness\tasks.json，然后：
python .harness\init.py
# 或打开看板（需 Python 3）：
powershell -NoProfile -File .harness\init.ps1 -ProjectDir (Get-Location)
```

状态文件建议放 `.harness/`：`tasks.json`、`evidence.jsonl`、`reviews.jsonl`、`progress.txt`。旧项目若把这些文件放在仓库根，初始化会原位读取，不强制迁移。

## 状态机

```
pending → active → evidence_ready → passed
                        │              │
                        └─(评审 fail)→ active（带新证据重试）
   任意态 → blocked（结构化阻塞，记 reason）
   passed → regressed（依赖变更导致失效，回 active）
```

`passed` 缺 evidence 或独立 `pass` review 都不算完成。看板把「任务声明已通过」和「门禁缺口」分开显示，不代替独立评审。

## 历史

- v2：9 态机、amendment、重型 validate 脚本。
- v3：5 态机 + JSONL 证据/评审；主会话只回收一行契约。
- v3.1：评审方法论内联，不再硬依赖 gstack。
- 本次整理：`main` 回到宿主无关核心；Claude / Codex / TRAE / WorkBuddy / DSH 各用一条分支。

## License

见 [LICENSE](LICENSE)。评审方法论改编自 [gstack](https://github.com/garrytan/gstack)（MIT © 2026 Garry Tan），见 `references/review/NOTICE`。
