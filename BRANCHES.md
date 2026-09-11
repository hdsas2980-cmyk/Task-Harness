# 分支拓扑

本仓库按「一份核心协议 + 多个 ADE 宿主适配」拆分。不要再往 `main` 里堆某个 IDE 的安装路径、斜杠命令或专属子智能体。

## 当前分支

| 分支 | 宿主 | 装到哪里 | 说明 |
|------|------|----------|------|
| `main` | 无宿主 | 不安装到 IDE | 核心协议、评审方法论、共享模板与可选看板。阅读入口。 |
| `claude` | Claude Code | `~/.claude/skills/task-harness`，若有 CC Switch 则同步主库；斜杠命令进 `~/.claude/commands/` | 原 `main` 的 Claude 发行版。可选 gstack 兜底。 |
| `codex` | OpenAI Codex | `$CODEX_HOME/skills/task-harness`（默认 `~/.codex/skills/task-harness`） | 原 `codex-native-v3.1`。PowerShell 优先，独立 Codex 评审上下文，本地看板。 |
| `traework` | TRAE / Trae Work | `~/.trae-cn/skills/task-harness`；命令进 `~/.trae-cn/commands/`；评审子智能体进 `~/.trae-cn/agents/` | TRAE 专用。默认不写 Claude。 |
| `workbuddy` | WorkBuddy | `~/.workbuddy/skills/task-harness` | WorkBuddy 用户技能目录。独立会话评审。 |
| `dsh` | DeepSeek Harness（DSH，口头常说 dhs） | `~/.dsh/skills/task-harness`；项目级也可放 `<repo>/.dsh/skills/task-harness` | DSH 文件系统 skill 提供方扫描这两个根。 |

## 旧分支对照

| 旧名字 | 处理 |
|--------|------|
| `main`（整理前，Claude Code + 斜杠命令 + CC Switch） | 内容迁到 `claude` |
| `feature/v3.1-inline-review` | 与旧 `main` 相同，已删除 |
| `codex-native-v3.1` | 重命名为 `codex` |
| `traework` | 保留，去掉「顺手装 Claude」作为主路径 |

## 选择哪条分支

- 只想读协议、抄模板、给新 ADE 做适配：`main`
- 日常在 Claude Code 里跑：`claude`
- 日常在 Codex 里跑：`codex`
- 日常在 TRAE 里跑：`traework`
- 日常在 WorkBuddy 里跑：`workbuddy`
- 日常在 DeepSeek Harness / DSH 里跑：`dsh`

同一台机器可以同时安装多个宿主分支，但每个宿主只装自己那条，不要把 `claude` 的 `commands/` 拷进 Codex，也不要把 Codex 的安装脚本指向 `~/.claude`。

## 共享与分叉

**必须保持一致（协议层）**

- 5 态机与 `blocked` / `regressed`
- `tasks.json` 唯一真相源
- `evidence.jsonl` + 独立 `reviews.jsonl` 才能 `passed`
- ponytail 阶梯、破坏性命令护栏、`HARNESS_STATUS` / `HARNESS_REVIEW` 契约
- `references/review/` 的评审内核（宿主分支可以改调用方式，不能改判定铁律）

**允许分叉（宿主层）**

- 安装目标目录
- 斜杠命令、子智能体、宿主 frontmatter
- 初始化入口（紧凑 `init.py` vs 本地看板）
- 评审落地方式（新会话 / 子智能体 / 斜杠命令）
- 可选运行时兜底（仅 `claude` 可提 gstack）

新宿主怎么加，见 [docs/ADAPTER.md](docs/ADAPTER.md)。
