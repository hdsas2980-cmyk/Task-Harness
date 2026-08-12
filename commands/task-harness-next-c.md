---
description: task-harness v3.1 推进 · C loop 连推（可选，显式确认）
---

按 task-harness v3 进入 loop 连续推进。这是**可选**模式，本命令即视为显式开启。

每轮执行一次 A 单步流程（读 progress 最后一条 → init.sh → 选唯一 eligible pending → 实现 → verify → 追加 evidence → 按 completion-review.md 独立评审 → 更新 status/reviews → 追加 progress → 输出状态块）。

循环控制：
- 每轮之间 fresh context：不携带上一轮代码/证据细节，只凭落盘状态。
- 拿到状态块后，若 `EXIT_SIGNAL=false` 则自动开始下一轮。
- 终止条件（满足其一即停，报告后退出 loop）：
  1. `EXIT_SIGNAL=true`（全部 passed）；
  2. 出现 BLOCKED；
  3. 同一任务连续两轮评审 fail（防打转）。
- 不做定时器/sleep；连推由本命令驱动，节奏与终止以上述条件为准。

绝不为"精简"砍验证/安全/错误处理；实现者不评审自己。

$ARGUMENTS
