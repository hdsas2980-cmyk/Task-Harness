# Task Harness v3.1

长时运行任务的最小骨架。一轮一任务、状态落盘、证据加独立评审判定完成，
主会话上下文不随任务数增长。适用于需跨多次会话增量推进的大型工程。

> **v3.1（评审自包含）**：评审方法论从外部 gstack 技能抽出、内联进本仓库
> （`references/review/`），task-harness 装到任意 IDE 都能完整运行，不再依赖用户
> 环境里是否装了 gstack；gstack 降级为可选兜底。详见下文「v3.1 的变化」与
> 「新机安装 / 从旧版更新的注意事项」。

## 哲学

最小的骨架换最大的问责：

- **一轮一任务**（参考 ralph）——每个任务在 fresh context 里推进，只加载单任务，
  执行结尾输出 `EXIT_SIGNAL` 状态块供外部循环判定。
- **存在性先于实现**（参考 ponytail）——7 级懒惰阶梯已内联进 `SKILL.md`，
  从源头砍掉伪任务；绝不为精简砍掉验证、安全、错误处理。
- **证据加独立评审判定完成**（评审方法论源自 gstack）——`passed` 必须同时持有一条 evidence
  记录加一条 pass 评审记录；评审在独立上下文完成，实现者不等于评审者。

三处"外包"（ralph 范式、ponytail 阶梯、gstack 评审方法论）都以文字协议内联，
核心（`SKILL.md` 加模板加内联评审方法论）完全自包含，无外部 skill/代码依赖，
装到任意 IDE 都能完整运行；gstack 仅作可选兜底。

## v3 相对 v2 的变化

v2 引入了 9 状态机、amendment 修订流程、`.harness/*.json` 三模板与 590 行
`validate_harness.py`。v3 判断这些是过度工程且会增加上下文负担，改为：

- 5 状态机：`pending → active → evidence_ready → passed`，外加 `blocked` / `regressed`
- 追加式 JSONL 日志（`evidence.jsonl` / `reviews.jsonl`）取代目录树式 JSON 模板
- 评审在独立上下文按内联方法论进行，主会话只回收一行 `HARNESS_REVIEW:` 契约结论
- 移除 `validate_harness.py` 与 v1 遗留的 `feature_list.json` / `task.json`

## v3.1 的变化（评审自包含）

v3 把评审委托给外部 gstack 技能，导致 task-harness 换到没装 gstack 的 IDE 时评审环缺失。
v3.1 把评审方法论抽出来内联进本仓库，实现真正的自包含：

- 新增 `references/review/`：`spec-review.md`（相 1 规格评审）+ `completion-review.md`
  （相 3 完成评审），方法论改编自 gstack（MIT © 2026 Garry Tan，见 `NOTICE`），
  **已剥离 gstack 运行时**（telemetry / gbrain / checkpoint / skill-routing 等），
  改写为 task-harness 语境（评审对象取自 `tasks.json` 触及文件 + `evidence.jsonl`，
  非 git 工作区 `rev=N/A` 时直接读文件，零 git/PR/gh 硬依赖）。
- SKILL.md 新增**破坏性命令自查护栏**节：自包含的文字纲领，不依赖项目级 CLAUDE.md
  （CLAUDE.md 并非每个 IDE 都具备）。
- 三处"外包"（ralph 范式、ponytail 阶梯、评审方法论）**全部内联**，无外部 skill 依赖。
- **gstack 降级为可选兜底**：内联方法论不足以判定（需 specialists 深度/复杂 diff）
  且本机装有 gstack 时，可回退调 `gstack/review` / `gstack/plan-eng-review`；
  没装则内联方法论承担全部评审，确实无法判定时如实标 `blocked`。
- 破坏性命令拦截：内联护栏是文字纲领，装有 gstack 时其 `careful` hook 作为可真正拦截的运行时兜底。

## 一次性安装

克隆后一条命令部署到 Claude Code；若检测到 CC Switch 主库会一并同步
（CC Switch 是 auto 同步权威源，不同步会被回滚）。

```sh
git clone https://github.com/hdsas2980-cmyk/Task-Harness.git
cd Task-Harness

# Linux / macOS / Windows-bash
bash scripts/install.sh

# 或 Windows PowerShell
powershell -ExecutionPolicy Bypass -File scripts\install.ps1
```

脚本幂等，可重复运行；每次把 `~/.claude/skills/task-harness/`
（及 CC Switch 主库）覆盖为仓库当前版本。重装系统后即可一次性还原环境。

重装系统或 Claude 被重置后的完整重建步骤（含前置检查、网络/鉴权注意、核验与冒烟测试），
见 [SETUP.md](SETUP.md)——可整段贴给 Claude Code 让它逐步执行。

## 新机安装 / 从旧版更新的注意事项

### 新机（全新安装）
- **前置**：`git`、`bash`（Windows 用 Git Bash）、任一 Python 3（`python`/`python3`/`py`，
  `init.sh` 需要它算 eligible 任务）。缺 Python 时 `init.sh` 会明确报错退出。
- **一条命令搞定**：`bash scripts/install.sh`（或 PowerShell 版）。脚本会把 `SKILL.md` +
  `references/`（含 `references/review/` 内联评审）装到 `~/.claude/skills/task-harness/`，
  三个斜杠命令装到 `~/.claude/commands/`。
- **不需要 gstack**：v3.1 起评审已内联，装到任意 IDE 都能完整运行。gstack 是可选增强，
  没有它 harness 照常评审、判定、推进。
- **网络/鉴权**：直连 `github.com:443` 可能被重置，走本地代理；私有仓库用 HTTPS + 凭据管理器。
  详见 [SETUP.md](SETUP.md) 阶段 1。
- **装完自检**：`~/.claude/skills/task-harness/references/review/` 下应有
  `spec-review.md` / `completion-review.md` / `NOTICE` 三件；SKILL.md 应含「破坏性命令自查护栏」节。

### 从旧版（v3.0 及更早）更新
- **install.sh 幂等、每次整份覆盖**：直接 `git pull` 后重跑 `bash scripts/install.sh` 即可，
  它会 `rm -rf` 旧 skill 目录再整份拷贝，**不会残留旧版文件**。
- **CC Switch 用户务必两处一致**：若装了 CC Switch（`skillSyncMethod=auto`，以主库为权威源），
  install.sh 会同时覆盖 `~/.cc-switch/skills/task-harness`。只更新 `~/.claude/skills` 而漏了主库，
  **下次 auto 同步会用旧版把你的更新回滚**。更新后可 `diff -rq ~/.claude/skills/task-harness
  ~/.cc-switch/skills/task-harness` 确认一致。
- **不影响进行中的项目**：升级只换 skill 本体，各项目 `.harness/` 下的 `tasks.json` /
  `evidence.jsonl` / `reviews.jsonl` 结构不变，无需迁移。评审调用点从「调 gstack」变为
  「按内联方法论评审」，契约行 `HARNESS_REVIEW:` 格式完全不变，旧证据/评审记录继续有效。
- **原先靠 gstack 的评审习惯**：现在默认走内联方法论；仍想用 gstack 深度评审的，
  内联文件已写明"内联不足时回退 gstack"的兜底路径，装着 gstack 即可继续用。
- **更新后自检**：同新机自检；另可跑 SETUP.md 阶段 5 的冒烟测试确认全链路与上下文恒定。

## 结构

```
SKILL.md                     技能主入口：哲学 / 5 态机 / 三相流程 / ponytail 阶梯 / 破坏性命令护栏 / 评审调用点
references/methodology.md    方法论背景与设计问答
references/review/           内联评审方法论（自包含，无 gstack 运行时依赖）
  spec-review.md             规格评审（相 1）
  completion-review.md       完成评审（相 3）
  NOTICE                     gstack MIT attribution
references/templates/        项目初始化模板
  tasks.json                 任务清单，唯一真相源
  evidence.jsonl             追加日志：verify 证据
  reviews.jsonl             追加日志：评审结论
  progress.txt               叙事日志，只读最后一条
  init.sh                    紧凑状态加单任务加载（自动探测 python，utf-8 输出）
  next-step.md               推进提示词模板（A 单步 / B team 并行 / C loop）
commands/                    斜杠命令（安装后可 /task-harness-next-a|b|c 调用）
scripts/install.sh           一次性安装（bash）
scripts/install.ps1          一次性安装（PowerShell）
```

## 使用

### 相 1 · 设计（一次性）

在目标项目里把 `references/templates/` 下模板复制到 `.harness/`，过 ponytail
阶梯砍掉伪任务，起草 `tasks.json`（稳定 id、priority、一句话 desc、`depends_on`、
可执行 `verify`），再按内联的 `references/review/spec-review.md` 做规格独立评审，结论追加 `progress.txt`。

`tasks.json` 结构：

```json
{
  "project": "示例",
  "rev": 1,
  "tasks": [
    { "id": "t-01", "priority": 1, "desc": "一句话说清范围",
      "depends_on": [], "verify": "go test ./...", "status": "pending" }
  ]
}
```

### 相 2/3 · 推进（每轮一任务）

每轮 `bash .harness/init.sh` 取下一个 eligible 任务，执行、记 `evidence.jsonl`、
按内联的 `references/review/completion-review.md` 在独立上下文评审、按 `HARNESS_REVIEW:`
一行契约更新 `status` 并记 `reviews.jsonl`，直至 `EXIT_SIGNAL: true`。

### 斜杠命令

安装脚本会把三个推进命令装到 `~/.claude/commands/`，直接在 Claude Code 里调用：

| 命令 | 模式 | 行为 |
| --- | --- | --- |
| `/task-harness-next-a` | 单步（默认） | 只推进一个任务，拿到状态块即停，不自转 |
| `/task-harness-next-b` | team 并行（可选） | 仅对依赖互不相关、改动文件不重叠的任务分派子 Agent，各自独立评审 |
| `/task-harness-next-c` | loop 连推（可选） | 每轮 fresh context，遇 `EXIT_SIGNAL:true`/BLOCKED/同任务连续两轮 fail 即停 |

三命令自包含（内联完整流程，不依赖外部文件），末尾支持追加临时指令（如指定任务 id）。
默认单步单任务；team 并行与 loop 都必须显式调用对应命令才生效——这是为守住
「上下文不随任务数增长」的核心宗旨。等价的可复制提示词见
`references/templates/next-step.md`。详见 `SKILL.md`。

### 状态机

```
pending → active → evidence_ready → passed
                        │              │
                        └─(评审 fail)→ active（带新证据重试）
   任意态 → blocked（结构化阻塞，记 reason）
   passed → regressed（依赖变更导致失效，回 active）
```

`passed` 必须同时持有一条 evidence 记录加一条 pass 评审记录，缺一不可；实现者不评审自己。

## 参考

- [Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)

## License

见 [LICENSE](LICENSE)。内联评审方法论改编自 gstack（MIT © 2026 Garry Tan），
见 [references/review/NOTICE](references/review/NOTICE)。
