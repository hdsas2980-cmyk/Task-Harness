# task-harness v3.2 (TRAE edition) · TRAE 环境安装与冒烟

> 纯 TRAE 环境的安装、重建与冒烟自检。Windows 优先 PowerShell；Claude Code 的旧理发（legacy）流程请见 `SETUP.md`。

## 1. 从零安装（TRAE）

前置：本机有 `git`、`python`（或 `py` 启动器）、TRAE 已安装。

```bash
git clone https://github.com/hdsas2980-cmyk/Task-Harness.git
cd Task-Harness
# Windows（推荐）：
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\install.ps1
# 或任意平台 bash：
bash scripts/install.sh
```

默认目标（安装器会覆盖为仓库当前版本，幂等可重跑）：

| 资产 | 全局目录 | 说明 |
|------|----------|------|
| 技能 | `~/.trae-cn/skills/task-harness/` | SKILL.md + references |
| 斜杠命令 | `~/.trae-cn/commands/` | `/task-harness-next-a\|b\|c` |
| 评审子智能体 | `~/.trae-cn/agents/harness-reviewer.md` | 独立上下文评审 |

可选：加 `--claude`（bash）/ `-Claude`（powershell）时，额外把 legacy 版本装到
`~/.claude` 与 `~/.cc-switch`，实现双生态共存（决策项 A）。

> 只在你自己的机器上拷贝，而不是整库：把 `references/templates/*` 里 6 个模板
> （tasks.json / evidence.jsonl / reviews.jsonl / progress.txt / init.py / init.sh /
> init.ps1 / next-step.md）拷进项目根或 `.harness/`。

## 2. 安装后生效

TRAE 采用动态按需加载：要让新装的技能/命令/子智能体被识别，通常需要重载或重启 TRAE
（或按产品提示刷新技能面板）。装完务必执行下面冒烟，确认可被唤起。

## 3. 冒烟自检（每装完必做）

在临时目录建一个玩具 harness，验证依赖门控、状态读取与双入口：

```bash
mkdir /tmp/harness-smoke && cd /tmp/harness-smoke
# 复制模板
cp <repo>/references/templates/{init.py,init.sh,init.ps1,tasks.json} .
# 用现成的 2 任务模板（t-01 无依赖、t-02 依赖 t-01）

# ① PowerShell 入口
powershell -NoProfile -ExecutionPolicy Bypass -File .\init.ps1
# 期望：PROGRESS: 0/2，推荐 t-01（无依赖、P1）

# ② bash 入口
bash init.sh
# 期望同上

# ③ 依赖门控：把 t-01 置 passed，再跑
# 期望：推荐 t-02（依赖已满足），且不推荐任何被依赖未满足的任务
```

通过标准：三处输出一致、无堆栈、推荐的任务永远满足 `depends_on` 已满足。

## 4. 对项目使用 harness（三步）

1. **相 1 · 设计**：复制 `references/templates/tasks.json`，起草任务清单（稳定 id / priority / desc / depends_on / 可执行的 verify），按 `spec-review.md` 独立评审。
2. **相 2 · 执行**：在 TRAE 输入 `/task-harness-next-a`（单步）推进。每轮只推进一个任务，跑完追加 `evidence.jsonl` 并置 `evidence_ready`。
3. **相 3 · 评审**：TRAE 会调 `harness-reviewer` 子智能体（只读、独立上下文）按 `completion-review.md` 评审，回一行 `HARNESS_REVIEW:` 契约。

team 并行用 `/task-harness-next-b`，loop 连推用 `/task-harness-next-c`（均为显式开启的可选模式）。

## 5. 项目规则（双写建议）

把下面这段写进项目（建议同时写两处，会话才会自动带上）：

- TRAE：`.trae/rules/harness.md`（或全局规则）
- 兼容层：项目根 `AGENTS.md` 追加

```md
## task-harness 使用规则
- 长工程若建了 `.harness/`，推进一律走 `/task-harness-next-a`（单步）或显式 b/c，禁止自由发挥多任务。
- 实现者不评审自己：`evidence_ready` 的任务必须由 `harness-reviewer` 独立评审后置 `passed`。
- 每轮只读 progress.txt 最后一条，回读全量清单/旧证据等于违规。
- `passed` 必须 evidence + pass 评审双记录；缺一不可，不得伪造完成。
```

## 6. 常见问题

- `init.ps1` 报编码错误：确认用 PowerShell 直读，不要用别的方式转码；本版 init.ps1 为纯 ASCII，无中文。
- `init.py` 报 `tasks.json 不存在`：先进入相 1 创建 tasks.json；模板在 `references/templates/`。
- 命令唤不起：确认 `commands/task-harness-next-*.md` 已在 `~/.trae-cn/commands/`，且 `name` frontmatter 存在；TRAE 不从技能目录读命令。
- gstack 相关术语：TRAE 版已去掉 gstack 运行时兜底，评审完全由内联方法论 + `harness-reviewer` 子智能体承担。