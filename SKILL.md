---
name: task-harness
description: 长时运行任务的最小骨架。一轮一任务、状态落盘、证据加独立评审判定完成，主会话上下文不随任务数增长。适用于需跨多次会话增量推进的大型工程。
---

# task-harness v3

## 哲学
最小的骨架换最大的问责。一轮一任务（ralph）、存在性先于实现（ponytail）、完成由不可变证据加独立评审判定（gstack）。
状态全部落盘，评审外包给独立上下文，主会话上下文恒定——与任务总数无关。
宁可骨架简陋，不可问责缺失：绝不为"精简"砍掉验证、安全、错误处理。

## 核心不变式
1. 一次会话只推进一个任务（选依赖已满足、优先级最高的 pending）。
2. 只加载当前任务加它触及的代码；不回读全量任务清单，不回读旧证据。
3. `passed` 必须同时持有一条 evidence 记录加一条 pass 评审记录，缺一不可。
4. 实现者不等于评审者（评审经 skill 调用在独立上下文完成）。
5. 依据不足时如实标 `blocked`，绝不伪造完成。

## 5 态机
```
pending → active → evidence_ready → passed
                        │              │
                        └─(评审 fail)→ active（带新证据重试）
   任意态 → blocked（结构化阻塞，记 reason）
   passed → regressed（依赖变更导致失效，回 active）
```

## 三相流程

### 相 1 · 设计（一次性）
1. 对每个候选任务先过 ponytail 阶梯（见下），从源头砍掉伪任务。
2. 起草 `tasks.json`：稳定 id、priority、一句话 desc、`depends_on`、可执行 `verify` 命令。
3. 调 `gstack/plan-eng-review` 做规格独立评审（依赖环、路径归属、命令可执行性），结论追加 progress.txt。

### 相 2 · 执行（每任务 fresh context）
1. `bash init.sh` → 输出紧凑状态（进度计数加下一个 eligible 任务），不打印全量清单。
2. 选唯一一个依赖已满足的最高优先级 `pending` → 置 `active`。
3. 只读该任务加它触及的代码（ponytail：先读懂再动手），实现其范围。
4. 跑 `verify` → 追加一条 `evidence.jsonl` → 置 `evidence_ready`。
5. 结尾输出执行状态块（见下），供循环判定是否继续。

### 相 3 · 评审（委托独立上下文）
1. 对 `evidence_ready` 任务调 `gstack/review`，传证据 id 加变更范围。
2. review 结尾按契约吐一行 `HARNESS_REVIEW:` → 追加 `reviews.jsonl`。
3. `pass` → `passed`；`fail` → 回 `active` 带新一轮证据。

## ponytail 阶梯（任务设计与实现时逐级自问）
1. 这个任务/代码需要存在吗？（YAGNI）
2. 代码库里已有可复用的吗？
3. 标准库/语言原生能解决吗？
4. 平台/框架原生能力能解决吗？
5. 已装的依赖能解决吗？
6. 一行能解决吗？
7. 能跑通的最小实现是什么？
（绝不对"理解代码"偷懒；绝不砍验证/安全/错误处理/无障碍。）

## gstack 调用点与评审契约
- 规格评审：`gstack/plan-eng-review`（相 1）。
- 完成评审：`gstack/review`（相 3）。
- 执行护栏（可选）：挂 `gstack/careful` hook 拦截误删/强推。
- 评审结论契约（评审 skill 结尾必须输出恰好一行）：
  ```
  HARNESS_REVIEW: pass|fail | <task-id> | <一句理由>
  ```
  harness 只解析这一行，按 pass/fail 更新状态并追加 reviews.jsonl。

## 执行状态块（相 2 结尾输出，供循环判定）
```
HARNESS_STATUS: <task-id> <IN_PROGRESS|COMPLETE|BLOCKED>
PROGRESS: <passed>/<total>
EXIT_SIGNAL: <false|true>
```
所有任务 `passed` 时 EXIT_SIGNAL=true，循环结束。

## 文件（放 `.harness/` 或项目根）
- `tasks.json` — 任务清单，唯一真相源。
- `evidence.jsonl` — 追加日志：`{id,task,cmd,exit,tests,rev,ts}`。
- `reviews.jsonl` — 追加日志：`{id,task,ev,skill,verdict,ts}`。
- `progress.txt` — 叙事日志，只读最后一条。
- `init.sh` — 紧凑状态加单任务加载。

## 修订（不走重型 amendment 流程）
改任务定义 = 直接编辑 tasks.json 加顶层 `rev+1` 加 progress.txt 记一句；受影响的 `passed` 任务标 `regressed` 回 active。
