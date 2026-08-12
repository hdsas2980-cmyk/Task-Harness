# Task Harness 方法论

## 为什么需要 Harness？

Agent 的核心限制是**无状态**——每次会话都从零开始，没有之前会话的记忆。没有结构的 Agent 会以可预测的方式失败：

| 失败模式 | 表现 |
|---------|------|
| 贪多嚼不烂 | 试图一次做太多，代码只实现了一半 |
| 过早宣称完成 | 声称工作完成了，实际还有遗漏 |
| 破坏环境 | 留下编译错误、测试失败、依赖冲突 |
| 重复探索 | 每次会话花大量时间重新发现项目结构 |

Harness 就是解决这些问题的**外部记忆系统**。

## 为什么用 JSON 做任务清单？

这是方法论中最关键的洞察：

模型倾向于自由改写 Markdown 文件——改写措辞、重组结构、删减内容。这种"过度编辑"倾向会导致任务清单逐渐失真：步骤被简化、验证条件被弱化、优先级被悄悄调整。

JSON 文件被模型更谨慎对待。模型更可能只修改特定字段（如 `status`），而保留其余结构不变。这种差异对维护任务完整性至关重要。

> v3 说明：任务清单文件为 `tasks.json`，任务状态由 `status` 字段表达（pending/active/evidence_ready/passed/blocked/regressed），不再用布尔 `passes`。完成的判定不只看 `status`，还必须有配套的 `evidence.jsonl` 与 `reviews.jsonl` 记录支撑，详见 [SKILL.md](../SKILL.md) 的核心不变式。

## 核心设计原则

### 1. 单一真相来源（Single Source of Truth）

`tasks.json` 是唯一的任务清单文件。所有判断都基于它：
- 什么还没做？→ `status: pending`（且依赖已满足）的任务
- 做了什么？→ `status: passed` 的任务（须持有 evidence + 通过评审）
- 总进度？→ `passed / total`

不要在其他文件中维护重复的任务列表。

### 2. 叙事性日志（Narrative Log）

`progress.txt` 用自然语言记录"做了什么"和"为什么"。JSON 精确但不解释原因。当 Agent 需要理解某个设计决策的背景时，叙事日志比 JSON 中的步骤列表更有用。

### 3. 快速上下文恢复（Fast Context Restore）

`init.sh` 只输出推进下一步所需的最小信息：进度计数、待评审/阻塞项、以及下一个 eligible 任务。v3 刻意不打印全量清单与 git 历史，以保证主会话上下文不随任务数增长。

### 4. 增量推进（Incremental Progress）

每个会话只推进 1 个任务（v3 不变式）。这看起来慢，但实际更快：
- 更少的回滚风险
- 更可靠的验证
- 更清晰的 git 历史
- 更容易恢复中断的工作

## 常见问题

### Q: 任务拆得太细，会不会效率低？

**不会。** Agent 在大任务上的失败率远高于小任务。一个 10 步任务被中断后，很难判断哪一步完成了、哪一步是半成品。拆成 10 个独立功能后，每个都能被独立验证和提交。

### Q: 要不要每个任务 commit？

**推荐但不强制。** v3 中"完成"由 evidence + 独立评审判定，不再把 commit/push 当作完成条件。若项目是 Git 仓库，仍建议每任务一 commit——便于 `git revert` 独立回滚、`git log` 追踪、以及在 evidence 里记录代码 `rev`（短哈希）。非 Git 工作区时 evidence 的 `rev` 记 `N/A`，是否推远端由项目策略决定。防进度丢失的根基在 v3 是落盘的 tasks.json / evidence.jsonl / reviews.jsonl，而非必须 push。

### Q: tasks.json 太大了怎么办？

如果任务超过 50 个，考虑分阶段创建：
- 先创建当前阶段的 20-30 个任务
- 当前阶段完成后，再创建下一阶段的任务

这样保持文件大小可控，Agent 读取更快。注意 v3 中主会话恒定的上下文成本来自"单任务加载"，与清单总长度关系不大；分阶段主要是让设计与依赖管理更清晰。

### Q: Agent 不遵守规则怎么办？

在 `AGENTS.md` 中以明确的规则形式写好约束。AGENTS.md 会在每次会话开始时被加载到 Agent 的上下文中，比普通文件更有约束力。

关键规则要放在 `AGENTS.md` 的 `Rules` 部分，而不是 `## Notes` 或 `## Tips` 中。

### Q: 任务的 desc 应该多详细？

**一句话说清范围即可，细节留给执行时读代码。** v3 精简掉了 v1 的 `steps` 数组——预设的分步骤容易在实现时失真，且增加清单体积。`desc` 划定"做什么与边界"，`verify` 给出"如何确认完成"，实现路径由 Agent 在读懂当前代码后决定（ponytail：先读懂再动手）。这样既防止 Agent 过度发挥，又不把过时的步骤固化进清单。

## 最佳实践

### 1. 功能 ID 命名

使用有意义的 ID，一眼就能看出属于哪个版本/阶段：

```
v1-01, v1-02, ...    # 第一版功能
v2-01, v2-02, ...    # 第二版功能
fix-01, fix-02       # 修复类
infra-01             # 基础设施类
```

### 2. 依赖（depends_on）

v3 用 `depends_on` 表达任务间关系，取代 v1 的 `category` 标签。`init.sh` 据此只挑"依赖已 passed"的任务作为下一个 eligible，自动形成正确执行顺序；相 1 的规格评审（`references/review/spec-review.md`）负责校验依赖图无环。写清依赖比按代码层级贴标签更能约束执行顺序。

```
"depends_on": []            # 无前置，可立即执行
"depends_on": ["t-01"]      # 需 t-01 先 passed
```

### 3. 验证条件（verification）

每个功能必须有可执行的验证条件：

```
// 差：主观描述
"看起来更好"

// 好：可执行的检查
"bun run build 成功无错误"
"登录页桌面端显示左右分屏，移动端只有表单区"
"表头 font-weight: 600，font-size: 12px"
```

### 4. progress.txt 格式

只读最后一条即可掌握进度，每轮追加一段、不改写历史：

```
----------------------------------------
YYYY-MM-DD · <task-id> <执行/评审>
----------------------------------------
- 做了什么 / 触及文件
- evidence: <evidence.jsonl 行 id>
- review: HARNESS_REVIEW: pass|fail | <task-id> | <理由>
- 状态: <passed / 回 active 重试 / blocked>
- PROGRESS: <passed>/<total>
```

### 5. 处理阻塞

当 Agent 遇到无法解决的问题时：

```
⚠️ 阻塞: 描述遇到的问题
原因: 为什么无法继续
尝试: 已经尝试过的解决方案
建议: 可能的解决方向
```

不要让 Agent 绕过阻塞继续做其他功能——这可能导致后续功能也失败。

## 参考

- [Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) — Anthropic 官方方法论文章
- [task-harness SKILL.md](../SKILL.md) — 技能主入口
- [templates/](templates/) — Harness 文件模板
