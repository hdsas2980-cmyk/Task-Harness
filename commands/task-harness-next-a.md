---
description: task-harness v3 推进 · A 单步（默认，不进 loop）
---

按 task-harness v3 单步推进一轮。只推进一个任务，禁止回读全量清单与旧证据，保持主会话上下文恒定。

1. 读 `.harness/progress.txt` 最后一条（只读最后一条，不回溯全文）。
2. `bash .harness/init.sh` → 看紧凑状态：进度计数 + 下一个 eligible 任务。
3. 选唯一一个「依赖已满足、优先级最高」的 pending 任务，置为 active。
   若无 eligible：全部 passed 则报告完成；否则报告 blocked 原因，停。
4. 只读该任务及它触及的代码，按 ponytail 阶梯先砍伪需求再动手，实现其范围。绝不为"精简"砍验证/安全/错误处理。
5. 跑该任务 verify → 向 `.harness/evidence.jsonl` 追加 `{id,task,cmd,exit,tests,rev,ts}` → 置 evidence_ready。
6. 在独立上下文按 `references/review/completion-review.md` 评审（传证据 id + 变更范围）；实现者不评审自己。内联不足且本机装有 gstack 时可回退调 `gstack/review`。
   评审结尾输出恰好一行：`HARNESS_REVIEW: pass|fail | <task-id> | <理由>`
   - pass → status 置 passed，向 `.harness/reviews.jsonl` 追加一条。
   - fail → 回 active，记录原因，本轮结束。
7. 向 `.harness/progress.txt` 追加一句本轮验证结论。
8. 输出执行状态块后**停止，不自动开始下一轮**：
   ```
   HARNESS_STATUS: <task-id> <IN_PROGRESS|COMPLETE|BLOCKED>
   PROGRESS: <passed>/<total>
   EXIT_SIGNAL: <false|true>
   ```

$ARGUMENTS
