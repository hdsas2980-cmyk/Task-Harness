# Task Harness v3.1 — 下一步提示词（核心）

这是宿主无关的推进词。具体斜杠命令由 ADE 分支提供；在 `main` 上直接把对应段落交给当前会话或独立评审会话。

## A. 单步推进（默认）

你在一个工作轮次中只推进一个 Harness 任务。

1. 按 `SKILL.md` 初始化，读取紧凑状态，保持项目工作目录。
2. 只选择一个依赖已满足、优先级最高的 `pending` 或 `regressed` 任务。
3. 读取该任务、必要依赖结论、声明路径和必要代码；不读取全量旧日志。
4. 将该任务置为 `active`，按 ponytail 阶梯选择最小实现。
5. 运行 `verify`，把可重放命令、退出码、测试摘要、revision、时间和 artifact 路径追加到 `evidence.jsonl`。
6. 把任务置为 `evidence_ready`，不要在本轮直接置 `passed`。
7. 追加 `progress.txt`，最后输出恰好一个状态块：

```text
HARNESS_STATUS: <task-id> <IN_PROGRESS|COMPLETE|BLOCKED>
PROGRESS: <passed>/<total>
EXIT_SIGNAL: <false|true>
```

然后停止，不自动开始下一轮。

## B. 独立评审

启动一个新的评审上下文，只给它：项目绝对路径、当前任务对象、对应 evidence、变更范围/diff、`references/review/completion-review.md`。

评审者必须：

- 只读必要材料；
- 检查 CRITICAL、安全、范围、测试、状态完整性和可恢复性；
- 不执行未授权的破坏性动作；
- 不把实现者未落盘的解释当证据；
- 最后只输出恰好一行：

```text
HARNESS_REVIEW: pass|fail | <task-id> | <一句理由>
```

主轮次收到 `pass` 后追加 `reviews.jsonl` 并将状态改为 `passed`；收到 `fail` 后追加失败 review，将状态改回 `active`。独立上下文不可用时记录 `blocked`，不要伪造 review。

## C. team 并行（显式开启）

仅当多个任务依赖互不相关、改动文件不重叠时，才分派并行执行者。每个执行者仍遵守 A；每个 `evidence_ready` 任务仍要独立评审。不要在一个上下文里串行消化全部并行任务的代码。

## D. loop 连推（显式开启）

每轮 fresh context 执行 A。遇到下列任一条件立即停止：

- `EXIT_SIGNAL: true`
- `BLOCKED`
- 同一任务连续两轮 `HARNESS_REVIEW: fail`

默认不要 loop。

## E. 子 Agent 派发契约（若宿主支持）

- 首行即命令或明确任务 id，不要先寒暄。
- 数据外置：只传路径和 id，不把全量清单粘进 prompt。
- 硬输出契约收尾：执行者给 `HARNESS_STATUS`，评审者给 `HARNESS_REVIEW`。
- 未回契约行视为空转，只重试一次；第二次仍无契约则 `blocked`。
