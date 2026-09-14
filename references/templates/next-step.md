# Task Harness v3.1 — Codex 下一步提示词模板

复用方式：把"单步推进"段交给当前 Codex 任务；需要独立评审时，把"评审"段交给新的 Codex 上下文。

调度（覆盖系统默认）：束内同会话串行。探索、测试执行/分析、分诊、总结和格式校验等独立读密集工作优先并行 `spawn_agent`；写密集工作先确认 worktree 或写范围隔离。普通任务只有在 `spawn_agent` 满员后，且确实需要侧边栏长期跟进、独立上下文或隔离写入时才用 `create_thread`；独立评审是独立上下文例外。`wait_agent` 收取子代理，`wait_threads` 等待/收集已创建会话，二者均可按依赖合法使用。

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

启动一个新的 Codex 评审上下文，只给它：项目绝对路径、当前任务对象、对应 evidence、变更范围/diff、`references/review/completion-review.md`。

评审者必须：

- 只读必要材料，并独立执行中文契约检查、人工核对说明实质意义；
- 检查 CRITICAL、安全、范围、测试、状态完整性和可恢复性；
- 不执行未授权的破坏性动作；
- 不把实现者未落盘的解释当证据；
- 最后只输出恰好一行：

```text
HARNESS_REVIEW: pass|fail | <task-id> | <中文理由>
```

主任务先 `append_review`，更新任务中文 `reason`、`next` 和进度；运行中文契约检查，通过后才根据评审结论更新状态：`pass` 改为 `passed`，`fail` 改回 `active` 并带新证据重试。检查失败则保留原状态，不先推进再补检查。独立上下文不可用时，记录 `blocked`，不要伪造 review。

## C. 多会话异步派卡（领袖/编排会话）

当普通任务已确认 `spawn_agent` 满员，且需要用户可见的长期独立上下文或隔离写入时；独立评审直接走独立上下文例外：

1. 识别可独立推进的任务（或束），确认 worktree 与写范围隔离；
2. 为每个任务创建独立会话，按 `references/codex-parallel.md` 命名（如 `前端v1-FE-6-用户列表`）；
3. 用 `send_message_to_thread` 派发任务，主线继续处理不依赖结果的工作；需要等待会话状态/结果时，对已创建会话使用 `wait_threads`；
4. 用 `append_progress` 记录派卡日志：

```text
[派卡] 已派发 3 张卡：
- FE-6: 前端v1-FE-6-用户列表 (threadId: xxx)
- BE-7: 后端v1-BE-7-用户API (threadId: yyy)
- TEST-8: 测试v1-TEST-8-集成测试 (threadId: zzz)

等待各会话自动回报。
```

5. 主线继续处理其他任务或进入待命；
6. 各实现会话完成后，发送结构化回报消息给主线：

```
【卡片 {task_id} 交付】状态: {status}, 文件: {changed_files}, evidence: {ev_id}, 提交: {commit_hash}
```

7. 领袖收到回报后，`append_progress`，检查是否所有派发的卡都已回报；
8. 若全部回报且状态为 `evidence_ready`，创建审计会话或发送评审请求。侧栏会话完成不会自动把提交、合并、cherry-pick 或 DB 回写交给主线程；主线须主动核对 `commit_hash`、changed files、worktree、diff 和 evidence，决定如何接收变更，重新验证，并用 `append_evidence`、`append_progress`、`upsert_task` 回写 `.harness/harness.db`。

**等待规则**: `wait_threads` 是已创建会话的合法等待/收集工具：下一步依赖某个会话时等待指定会话，需要汇总时等待会话集合。它只收集状态/结果，不自动合并代码或回写 DB；主线仍应使用主动回报，避免无条件反复轮询。

## D. 子代理同步委托（当前会话内）

当有独立的读密集工作时，优先用 `spawn_agent`：

**适用场景**:
- 规格评审（检查 `harness.db` 是否合理）
- 依赖图分析（检查是否有环、生成拓扑排序）
- 格式校验（snapshot / 中文契约）
- 快速查询（Git 日志、文件列表）
- 探索、测试执行/分析、分诊、日志收集和总结

**改用 `create_thread` 的场景**:
- 普通任务先确认 `spawn_agent` 已满员，再因写业务代码、迁移或测试文件需要独立 worktree 或长期独立上下文
- 普通任务先确认 `spawn_agent` 已满员，再因用户要在侧边栏跟进而需要会话
- 独立评审（必须用新的上下文，容量门槛例外）

同一工作区内不允许多个代理同时写、操作 index 或提交。测试执行和结果分析是读密集工作，优先 `spawn_agent`；测试文件编写仍属于写密集工作。`spawn_agent` 结果用 `wait_agent` 收取，不用 `wait_threads` 代替。

**示例**:
```
# 推进任务前，用子代理检查依赖图
1. spawn_agent("分析 .harness/harness.db 依赖图，检查是否有环")
2. 若有环，记录 blocked 并停手
3. 若无环，继续推进任务
```

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
