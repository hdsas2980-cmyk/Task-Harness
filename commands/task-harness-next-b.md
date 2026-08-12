---
description: task-harness v3 推进 · B team 并行（可选，仅独立任务）
---

按 task-harness v3 以 team 并行推进本轮。仅当存在多个「依赖互不相关」的 eligible pending 任务时启用，否则退回单步串行（见 /task-harness-next-a）。

前置：
- `bash .harness/init.sh` 看清哪些 pending 任务 `depends_on` 无交叉、触及文件不重叠。
- 只对满足上述条件的任务并行；有依赖关系或改同一批文件的任务禁止并行。

分派规则：
- 每个子 Agent 严格「只领一个任务」：置 active → 只读该任务及触及代码 → 实现 → 跑 verify → 追加 `.harness/evidence.jsonl` → 置 evidence_ready → 在独立上下文按 `references/review/completion-review.md` 评审（内联不足且装有 gstack 时可回退 `gstack/review`）→ 按 `HARNESS_REVIEW:` 一行结论更新 status 并追加 `.harness/reviews.jsonl` → 追加一句 `.harness/progress.txt`。
- 子 Agent 之间**不共享上下文**以求"效率"；否则破坏"上下文不随任务数增长"的核心宗旨。
- 实现者不评审自己。绝不为"精简"砍验证/安全/错误处理。

汇总：主会话只收各子 Agent 的执行状态块，不回读细节。最后输出总进度：
```
PROGRESS: <passed>/<total>
EXIT_SIGNAL: <false|true>
```
不自动开始下一轮。

$ARGUMENTS
