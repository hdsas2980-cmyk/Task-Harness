# Task Harness v3

长时运行任务的最小骨架。一轮一任务、状态落盘、证据加独立评审判定完成，
主会话上下文不随任务数增长。适用于需跨多次会话增量推进的大型工程。

## 哲学

最小的骨架换最大的问责：

- **一轮一任务**（参考 ralph）——每个任务在 fresh context 里推进，只加载单任务，
  执行结尾输出 `EXIT_SIGNAL` 状态块供外部循环判定。
- **存在性先于实现**（参考 ponytail）——7 级懒惰阶梯已内联进 `SKILL.md`，
  从源头砍掉伪任务；绝不为精简砍掉验证、安全、错误处理。
- **证据加独立评审判定完成**（参考 gstack）——`passed` 必须同时持有一条 evidence
  记录加一条 pass 评审记录；评审经 skill 调用在独立上下文完成，实现者不等于评审者。

三处"外包"（ralph 范式、ponytail 阶梯、gstack 评审契约）都以文字协议内联，
核心（`SKILL.md` 加 5 个模板）完全自包含，无外部代码依赖。

## v3 相对 v2 的变化

v2 引入了 9 状态机、amendment 修订流程、`.harness/*.json` 三模板与 590 行
`validate_harness.py`。v3 判断这些是过度工程且会增加上下文负担，改为：

- 5 状态机：`pending → active → evidence_ready → passed`，外加 `blocked` / `regressed`
- 追加式 JSONL 日志（`evidence.jsonl` / `reviews.jsonl`）取代目录树式 JSON 模板
- 评审委托给 skill，主会话只回收一行 `HARNESS_REVIEW:` 契约结论
- 移除 `validate_harness.py` 与 v1 遗留的 `feature_list.json` / `task.json`

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

## 结构

```
SKILL.md                     技能主入口：哲学 / 5 态机 / 三相流程 / ponytail 阶梯 / gstack 调用点
references/methodology.md    方法论背景与设计问答
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
可执行 `verify`），再调 `gstack/plan-eng-review` 做规格独立评审，结论追加 `progress.txt`。

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
调 `gstack/review` 评审、按 `HARNESS_REVIEW:` 一行契约更新 `status` 并记
`reviews.jsonl`，直至 `EXIT_SIGNAL: true`。

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

见 [LICENSE](LICENSE)。
