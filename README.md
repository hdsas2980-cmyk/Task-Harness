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
scripts/install.sh           一次性安装（bash）
scripts/install.ps1          一次性安装（PowerShell）
```

## 使用

在目标项目里进入相 1 设计：复制 `references/templates/` 下模板，
过 ponytail 阶梯砍掉伪任务，起草 `tasks.json`，调 `gstack/plan-eng-review`
做规格评审。之后每轮 `bash init.sh` 取下一个任务，执行、记证据、调
`gstack/review` 评审，直至 `EXIT_SIGNAL: true`。详见 `SKILL.md`。

## 参考

- [Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)

## License

见 [LICENSE](LICENSE)。
