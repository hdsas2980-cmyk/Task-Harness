# task-harness v3 · 推进提示词模板

复用方式：把下面「单步推进」段整段贴给 Claude 即可推进一轮。
team 并行与 loop 均为**可选增强**，默认走单步、单任务、不自转。

---

## A. 单步推进（默认 · 不进 loop）

本轮只推进一个任务，禁止回读全量清单与旧证据，保持主会话上下文恒定。

1. 读 `.harness/progress.txt` 的最后一条，了解上一轮结论（只读最后一条，不回溯全文）。
2. `bash .harness/init.sh` → 看紧凑状态：进度计数 + 下一个 eligible 任务。
3. 选唯一一个「依赖已满足、优先级最高」的 pending 任务，置为 active。
   （若无 eligible：全部 passed 则报告完成；否则报告 blocked 原因，停。）
4. 只读该任务及它触及的代码，按 ponytail 阶梯先砍伪需求再动手，实现其范围。
   绝不为"精简"砍掉验证、安全、错误处理。
5. 跑该任务的 verify → 向 `.harness/evidence.jsonl` 追加一条
   `{id,task,cmd,exit,tests,rev,ts}` → 置 evidence_ready。
6. 调 `gstack/review`（传证据 id + 变更范围）独立评审；实现者不评审自己。
   评审结尾按契约输出恰好一行：`HARNESS_REVIEW: pass|fail | <task-id> | <理由>`
   - pass → status 置 passed，向 `.harness/reviews.jsonl` 追加一条。
   - fail → 回 active，记录原因，本轮结束（下轮带新证据重试）。
7. 向 `.harness/progress.txt` 追加一句本轮验证结论。
8. 结尾输出执行状态块后停止，**不自动开始下一轮**：
   ```
   HARNESS_STATUS: <task-id> <IN_PROGRESS|COMPLETE|BLOCKED>
   PROGRESS: <passed>/<total>
   EXIT_SIGNAL: <false|true>
   ```

---

## B. team 并行（可选 · 显式开启才生效）

仅当本轮存在多个「依赖互不相关」的 eligible pending 任务，且你显式要求并行时启用。

- 只对 `depends_on` 无交叉、触及文件不重叠的任务分派子 Agent。
- 每个子 Agent 仍严格「只领一个任务」，独立跑 verify、独立走 gstack/review。
- 有依赖关系或改同一批文件的任务，禁止并行，退回单步串行。
- 并行不得共享上下文以求"效率"——否则破坏"上下文不随任务数增长"的核心宗旨。
- 汇总：各子 Agent 各自追加 evidence/reviews/progress，主会话只收状态块，不回读细节。

---

## D. 子 Agent 派发契约（防空转 · A 相 6 与 B 通用）

子 Agent 收到的 prompt 就是它的任务本身。长叙事 + 大段内联数据 + 动作埋在末尾，会让它把整段当阅读材料、用寒暄开场（"你好，我是…"）而不执行。派发时严格遵守：

1. **首行即命令（动词开头）**：第一行就是祈使动作（读取 X → 核查 Y → 只输出 Z），上下文放其后；绝不用背景铺垫开头。
2. **硬输出契约收尾**：明确"只输出恰好一行 `HARNESS_REVIEW: pass|fail | <task-id> | <理由>`（评审）或状态块（实现），不要输出任何别的内容"。留了对话空间就会被寒暄填满。
3. **数据外置**：不内联大段 artifacts；让子 Agent 用 read_file 自读 `.harness/artifacts/*` 与 `evidence.jsonl`。prompt 越短，指令越不被稀释。
4. **显式角色**：传 `subagent_type`（如 general-purpose 或专门 reviewer），或首行声明身份"你是评审 Agent"。Agent 无独立 system 参数，角色靠 agentType 或首行注入。
5. **兜底重试**：子 Agent 未回出契约行（`HARNESS_REVIEW:` / 状态块）即判为空转 → 用更短、更祈使的 prompt 重试一次；仍失败则主会话记录并回退串行，不伪造评审结论。
6. **Workflow 场景最硬**：能用结构化输出 schema 时优先用，逼子 Agent 调 StructuredOutput，直接消除自由寒暄空间。

评审派发骨架（照抄替换尖括号即可）：

    你是评审 Agent。用 read_file 读 <artifact 路径>，独立核查以下 N 条：<核查清单>。
    只输出恰好一行：HARNESS_REVIEW: pass|fail | <task-id> | <一句理由>。不要输出任何别的内容。

---

## C. loop 轮询（可选 · 默认关闭）

默认到状态块即停。需要自动连推时，显式说明「进入 loop」再启用：

- 每完成一轮（拿到状态块）后，若 `EXIT_SIGNAL=false` 则自动开始下一轮 A。
- 每轮之间仍是 fresh context：不携带上一轮的代码/证据细节，只凭落盘状态。
- 终止条件（满足其一即停，报告后退出 loop）：
  - `EXIT_SIGNAL=true`（全部 passed）；
  - 出现 BLOCKED；
  - 同一任务连续两轮评审 fail（防打转）。
- 轮询节奏由外部触发或人工把关，提示词内不做定时器/sleep。
```

未显式说「进入 loop」或「并行」时，一律按 A 单步执行一轮后停下。
