# Task Harness v3.1 — Codex 下一步提示词模板

复用方式：把“单步推进”段交给当前 Codex 任务；需要独立评审时，把“评审”段交给新的 Codex 上下文。

## A. 单步推进（默认）

你在一个 Codex 工作轮次中，只推进一个 Harness 任务。先做：

1. 按 SKILL.md“项目看板”以项目绝对路径运行技能初始化脚本，保持项目工作目录；
2. 只选择一个依赖已满足、优先级最高的 `pending` 或 `regressed` 任务；
3. 读取该任务、必要依赖结论、任务声明路径和必要代码，不读取全量旧日志；
4. 将该任务置为 `active`，按 ponytail 阶梯选择最小实现；
5. 运行任务的 `verify`，把可重放命令、退出码、测试摘要、revision、时间和 artifact 路径追加到 `evidence.jsonl`；
6. 把任务置为 `evidence_ready`，不要在本轮直接置 `passed`；
7. 追加 `progress.txt`，最后输出恰好一个状态块：

```text
HARNESS_STATUS: <task-id> <IN_PROGRESS|COMPLETE|BLOCKED>
PROGRESS: <passed>/<total>
EXIT_SIGNAL: <false|true>
```

## B. 独立评审

启动一个新的 Codex 评审上下文，只给它：项目绝对路径、当前任务对象、对应 evidence、变更范围/diff、`references/review/completion-review.md`。

评审者必须：

- 只读必要材料；
- 检查 CRITICAL、安全、范围、测试、状态完整性和可恢复性；
- 不执行未授权的破坏性动作；
- 不把实现者未落盘的解释当证据；
- 最后只输出恰好一行：

```text
HARNESS_REVIEW: pass|fail | <task-id> | <一句理由>
```

主任务收到 `pass` 后，追加 `reviews.jsonl` 并将状态改为 `passed`；收到 `fail` 后，追加失败 review，将状态改回 `active` 并带新证据重试。独立上下文不可用时，记录 `blocked`，不要伪造 review。

## C. loop（可选，默认关闭）

只有用户明确要求连续推进时才进入 loop。每轮仍是一个任务、一个新上下文；出现 `EXIT_SIGNAL=true`、`BLOCKED` 或同一任务连续两次评审失败就停止并报告。
