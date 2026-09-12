# Task Harness v3.1 — Codex 下一步提示词模板

复用方式：把"单步推进"段交给当前 Codex 任务；需要独立评审时，把"评审"段交给新的 Codex 上下文。

## A. 单步推进（默认）

你在一个 Codex 工作轮次中，只推进一个 Harness 任务。先做：

1. 读取项目 `.harness/tasks.json`（或根目录 `tasks.json`）与 `progress.txt` 末段，保持项目工作目录；不要为了看板去跑技能脚本；
2. 只选择一个依赖已满足、优先级最高的 `pending` 或 `regressed` 任务（或束）；
3. 读取该任务（或束内任务）、必要依赖结论、任务声明路径和必要代码，不读取全量旧日志；
4. 将该任务置为 `active`，按 ponytail 阶梯选择最小实现；
5. 若是束，按 `bundle` 数组顺序串行推进每个任务；若是单任务，直接推进；
6. 运行任务的 `verify`（束的 `verify` 是整束验证），把可重放命令、退出码、测试摘要、revision、时间和 artifact 路径追加到 `evidence.jsonl`；
7. 把任务置为 `evidence_ready`，不要在本轮直接置 `passed`；
8. 追加 `progress.txt`，最后输出恰好一个状态块：

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

## C. 多会话异步派卡（领袖/编排会话）

当需要并行推进多个写范围互斥的任务时：

1. 识别可并行任务（或束），确认写范围互斥；
2. 为每个任务创建独立会话，按 `references/codex-parallel.md` 命名（如 `前端v1-FE-6-用户列表`）；
3. 用 `send_message_to_thread` 派发任务，**不阻塞等待**；
4. 记录派卡日志到 `progress.txt`：

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

7. 领袖收到回报后，记录到 `progress.txt`，检查是否所有派发的卡都已回报；
8. 若全部回报且状态为 `evidence_ready`，创建审计会话或发送评审请求。

**关键**: 不要用 `wait_threads` 阻塞主线；让子会话完成后通过消息主动通知。

## D. 子代理同步委托（当前会话内）

当需要立即获得结果的 sidecar 任务时，用 `spawn_agent`：

**适用场景**:
- 规格评审（检查 `tasks.json` 是否合理）
- 依赖图分析（检查是否有环、生成拓扑排序）
- 格式校验（JSONL 是否合法）
- 快速查询（Git 日志、文件列表）

**不适用场景**:
- 写代码（应该用 `create_thread` 异步并行）
- 运行测试（可能耗时长，应该用 `create_thread`）
- 独立评审（必须用 `create_thread` 隔离上下文）

**示例**:
```
# 推进任务前，用子代理检查依赖图
1. spawn_agent("分析 .harness/tasks.json 依赖图，检查是否有环")
2. 若有环，记录 blocked 并停手
3. 若无环，继续推进任务
```

## E. 束（Bundle）推进

当任务是束时（有 `bundle` 字段）：

1. 按 `bundle` 数组顺序串行推进每个子任务；
2. 单个 Codex 会话推进整个束，不拆分到多会话；
3. 每个子任务完成后，记录中间证据到 `progress.txt`；
4. 所有子任务完成后，运行束的 `verify`（整束验证）；
5. 追加 `evidence.jsonl`，将束状态置为 `evidence_ready`；
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
