# Task Harness v3.1 — Codex 下一步提示词模板

先读取 SKILL.md；原生命令见 references/codex-native.md，编排见 references/codex-parallel.md。读密集工作优先 spawn_agent；写密集工作先隔离。左侧新聊天必须同时满足用户明确要求、spawn_agent 已达到宿主容量上限、以及侧栏并行/长期上下文/隔离写入需要。独立审计同样受该门槛约束，除非原生 /review 已满足等价契约。

## A. 单步推进（默认）

你在一个 Codex 工作轮次中，只推进一个 Harness 任务。先做：

遵守 `references/language-contract.md`：原字段中文、机器标识不变、无旁挂翻译。用当前技能绝对路径运行 `scripts/check_task_harness_language.py <项目绝对路径>`，禁止 `--templates`；开始推进前、证据与进度追加后、评审回写后均须通过。失败只修复源文件，不推进状态。

1. 读取项目 `.harness/harness.db` snapshot 与 progress 末段，保持项目工作目录；不要读旧 JSON，不要为了看板去跑技能脚本；
2. 只选择一个依赖已满足、优先级最高的 `pending` 或 `regressed` 任务（或束）；
3. 读取该任务（或束内任务）、必要依赖结论、任务声明路径和必要代码，不读取全量旧日志；
4. 将该任务置为 `active`，按 ponytail 阶梯选择最小实现；
5. 若是束，按 `bundle` 数组顺序串行推进每个任务；若是单任务，直接推进；
6. 运行任务的 `verify`（束的 `verify` 是整束验证），把可重放命令、退出码、中文结果摘要 `summary`、原始测试输出 `tests`、revision、时间和 artifact 路径用 `append_evidence` 写入；
7. 更新任务中文 `reason`、`next`，用 `append_progress` 追加中文进度；运行中文契约检查，通过后才置为 `evidence_ready`，失败不推进；不要在本轮直接置 `passed`；
8. 最后输出恰好一个状态块：

```text
HARNESS_STATUS: <task-id> <IN_PROGRESS|COMPLETE|BLOCKED>
PROGRESS: <passed>/<total>
EXIT_SIGNAL: <false|true>
```

## B. 独立评审

先核对用户明确的新聊天授权、spawn_agent 是否已满，以及原生 /review 是否已满足等价契约。没有授权、未满员或独立上下文时记录待评审阻塞，不自动创建。不等价时，新的非 Fork 审计任务只给：项目/canonical DB 绝对路径、当前任务、对应 evidence、封存 diff/基线、必要源码和 references/review/completion-review.md。

审计者只读，独立运行中文契约和验证，检查严重问题、安全、范围、回归与可恢复性。结果输出唯一 HARNESS_REVIEW: pass|fail | <task-id> | <中文理由>。主线核对来源与材料未漂移，append_review、更新中文 reason/next/progress，通过语言门禁后按 pass→passed、fail→active 回写。没有真实审计不能伪造 review。

## C. 用户授权的新聊天派卡

仅当用户明确要求创建新聊天、spawn_agent 已达到宿主容量上限、且确需侧栏并行时，按原生路由 list_projects 并选环境。初始 prompt：

```text
在 {project_absolute_path} 处理 {task_id}，canonical DB 为 {db_absolute_path}。
先核对 {source_revision} 与当前任务定义；仅写 {write_scope}，不得兼任最终审计。
执行 {verify_command}，将证据制品保存在 {artifact_path}，按授权决定是否写库。
交付范围止于 evidence_ready；返回 changed_files、工作区、提交或 dirty diff、证据、限制与下一步。
```

create_thread 的初始 prompt 已派卡，不重复发送。正式 threadId 就绪后用 wait_threads 收集结果（保留 cursor，避免频繁轮询）；后续新指令才 send_message_to_thread。结果只供核对，主线串行集成后重新验证并回写 DB。

## D. 子代理委托

主线先决定立即要做的工作；把当前卡非阻塞的独立辅助项委托 spawn_agent，明确输入、互斥写范围与返回格式。主线继续非重叠工作，硬依赖时 wait_agent，结束 close_agent。满员且用户明确要求并确需侧栏并行时才 create_thread；否则关闭已完成代理、等待或串行，不能自动改用 create_thread。

## E. 束（Bundle）推进

当任务是束时（有 `bundle` 字段）：

1. 按 `bundle` 数组顺序串行推进每个子任务；
2. 单个 Codex 会话推进整个束，不拆分到多会话；
3. 每个子任务完成后，`append_progress` 记录中间证据；
4. 所有子任务完成后，运行束的 `verify`（整束验证）；
5. `append_evidence` 后，将束状态 `upsert_task` 为 `evidence_ready`；
6. 输出 `HARNESS_STATUS`，停手等待评审。

**示例**:
```
束 bundle-user-api = [t-backend-03, t-test-03]

1. 推进 t-backend-03：实现 GET /api/users
2. 验证 t-backend-03：curl http://localhost:3000/api/users
3. 推进 t-test-03：补充集成测试
4. 验证整束：npm test -- user-api.test.ts && curl http://localhost:3000/api/users
5. 置为 evidence_ready，停手
```

## F. loop（可选，默认关闭）

只有用户明确要求连续推进时才进入 loop。每轮仍是一个任务、一个新上下文；出现 `EXIT_SIGNAL=true`、`BLOCKED` 或同一任务连续两次评审失败就停止并报告。
