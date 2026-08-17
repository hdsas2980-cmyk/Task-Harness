---
name: task-harness
description: 长时运行任务的最小骨架。一轮一任务、状态落盘、证据加独立评审判定完成，主会话上下文不随任务数增长。适用于需跨多次会话增量推进的大型工程。
---

# task-harness v3.2 (TRAE edition)

## 哲学
最小的骨架换最大的问责。一轮一任务（ralph 范式）、存在性先于实现（ponytail 阶梯）、完成由不可变证据加独立评审判定（评审方法论内联，源自 gstack）。三处外包全部内联为文字协议，自包含、零外部 skill 依赖，装到任意 IDE 都能完整运行。
状态全部落盘，评审在独立上下文进行，主会话上下文恒定——与任务总数无关。
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
3. 按内联的 `references/review/spec-review.md` 做规格独立评审（依赖环、路径归属、命令可执行性、工程原则），结论追加 progress.txt。内联不足时交由独立评审子智能体 `harness-reviewer` 深评。

### 相 2 · 执行（每任务 fresh context）
1. 运行 `init.ps1`（PowerShell 默认）或 `init.sh`（bash）→ 输出紧凑状态（进度计数加下一个 eligible 任务），不打印全量清单。
2. 选唯一一个依赖已满足的最高优先级 `pending` → 置 `active`。
3. 只读该任务加它触及的代码（ponytail：先读懂再动手），实现其范围。
4. 跑 `verify` → 追加一条 `evidence.jsonl` → 置 `evidence_ready`。
5. 结尾输出执行状态块（见下），供循环判定是否继续。

### 相 3 · 评审（委托独立上下文）
1. 对 `evidence_ready` 任务，在独立上下文按内联的 `references/review/completion-review.md` 评审，传证据 id 加变更范围。TRAE 下评审交由只读子智能体 `harness-reviewer`（或内置 `general_purpose_task`）完成，实现者不评审自己。
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

## 破坏性命令自查护栏（自包含，不依赖任何外部文件）
执行任何可能不可逆或有广泛影响的命令前，先自查并向用户确认，不得在验证/评审中擅自运行：
- 递归删除（`rm -rf`、批量删目录）、`git clean -f`、覆盖写入未备份文件。
- 数据破坏（`DROP TABLE`、`TRUNCATE`、无 WHERE 的 UPDATE/DELETE、删数据卷）。
- 历史/远端改写（`git reset --hard`、`git push --force`、`--amend` 已推提交）。
- 生产/共享系统变更（部署、重启服务、改 DNS/网关/权限、`kubectl delete`）。
- 未限定路径的递归 `grep`/`find`（须带目录白名单 + timeout，目录不存在必须失败、不得回退到根）。
命中即先停下说明"要做什么、可能出什么错、是否可逆"，取得确认再执行。本护栏为纯文字纲领（TRAE 版不再依赖外部运行时钩子）。

## 评审调用点与评审契约
评审方法论已自包含内联进本 skill，装到任意 IDE 都能完整运行，不依赖任何外部运行时（**TRAE 版无 gstack 兜底**）：
- 规格评审：`references/review/spec-review.md`（相 1）。
- 完成评审：`references/review/completion-review.md`（相 3）。
- 独立评审落地：TRAE 下调用只读子智能体 `agents/harness-reviewer.md`（或内置 `general_purpose_task` 手写 prompt）在独立上下文完成，实现者不评审自己。
- 兜底：内联清单不足以判定时，如实标 `blocked`，绝不伪造 pass。
- 破坏性命令自查护栏（自包含，见上文「破坏性命令自查护栏」节）。
- 评审结论契约（评审结尾必须输出恰好一行）：
  ```
  HARNESS_REVIEW: pass|fail | <task-id> | <一句理由>
  ```
  harness 只解析这一行，按 pass/fail 更新状态并追加 reviews.jsonl。
- 子 Agent 派发防空转：首行即命令、硬输出契约收尾、数据外置、显式 agentType、未回契约行即判空转重试一次。详见 `references/templates/next-step.md` 的「D. 子 Agent 派发契约」。

## 执行状态块（相 2 结尾输出，供循环判定）
```
HARNESS_STATUS: <task-id> <IN_PROGRESS|COMPLETE|BLOCKED>
PROGRESS: <passed>/<total>
EXIT_SIGNAL: <false|true>
```
所有任务 `passed` 时 EXIT_SIGNAL=true，循环结束。

## 文件（放 `.harness/` 或项目根）
运营产物（在 `.harness/`）：
- `tasks.json` — 任务清单，唯一真相源。
- `evidence.jsonl` — 追加日志：`{id,task,cmd,exit,tests,rev,ts}`。
- `reviews.jsonl` — 追加日志：`{id,task,ev,skill,verdict,ts}`。
- `progress.txt` — 叙事日志，只读最后一条。
模板（安装时进 `.harness/`，改项目不必动）：
- `init.py` — 紧凑状态加单任务加载（纯 Python 逻辑，幂等）。
- `init.sh` — bash 入口；`init.ps1` — PowerShell 入口（TRAE 默认）；两者都只调 `init.py`。
- `next-step.md` — 推进提示词模板（A 单步默认 / B team 并行可选 / C loop 可选）。
子智能体（安装到 TRAE agents 目录）：
- `agents/harness-reviewer.md` — 只读独立评审子智能体，输出 `HARNESS_REVIEW:` 契约行。

## 修订（不走重型 amendment 流程）
改任务定义 = 直接编辑 tasks.json 加顶层 `rev+1` 加 progress.txt 记一句；受影响的 `passed` 任务标 `regressed` 回 active。
