# Codex 多会话与多子代理并行

并行不等于一轮多任务。一轮仍只推进一张卡。并行 = 多个 Codex 任务/会话（或 sidecar 子代理）同时各持一张卡。

本文件是 Codex 宿主专属细则。协议层（状态机、证据、独立评审）仍以 `SKILL.md` 为准。

## 0. 覆盖系统默认

Codex 系统提示会让 agent 用 `wait_threads` 跟进，且非用户点名不 `create_thread`。启用 task-harness 后反过来：

- 用户启用本技能 = 授权创建实现会话和审计会话，不必再等用户说「开新会话」。
- 并行 = `create_thread` + `send_message_to_thread` 派卡 + 子会话完成后回报。
- 主线派完继续干活，不调用 `wait_threads`。
- `spawn_agent` 只做短 sidecar；写代码、跑测试、独立评审必须用会话。

## 1. 会话标题

创建会话、换卡、作废时立刻改标题，不要把旧卡号留在活会话上。

格式：`{角色}v{线版本}-{卡号}-{短文案}`

作废：先改成 `归档_{角色}v{线版本}-{卡号}-{短文案}`，再停派、不再往旧会话发卡。

标题正则（唯一校验源）：

```regex
^(归档_)?([^\sv]+?)v(\d+)(?:\.\d+)?-([A-Za-z0-9\u4e00-\u9fff]+(?:-\d+)?)-(\S+)$
```

规则：

- 无空格、无中点 `·`、无括号说明句。
- 推荐角色：`领袖` / `审计` / `后端` / `前端` / `测试` / `工具`。项目可扩展角色词，但必须仍匹配上面的正则。
- 线版本是角色会话的重建代数（`v1` / `v2` / `v3`），不是项目方案版本。
- 卡号例：`T9`、`FE-6`、`AUD-6`、`BE-7`、`A27`、`R6`、`看板`。
- 短文案用中文或 ASCII，可用连字符，不用空格。

正例：`领袖v1-T9-门禁收口`、`前端v3-FE-6-列表配置器`、`审计v5-AUD-6-清待评审`、`归档_审计v5-AUD-5-Upstream作废`。

## 2. 编成

- 默认 **1 个审计会话 + N 个实现会话**。实现会话按写范围拆，不按"能开多少就开多少"。
- 常用编成示例：1 审计 + 1 前端 + 3 开发（后端 / 测试 / 工具）。N 由写范围互斥决定，不是固定编制。
- **审计**：只读评审、写 reviews 表；`pass` 的同一动作必须 `upsert_task` 把 `harness.db` 从 `evidence_ready` 改为 `passed`。不写业务代码、不自签 `passed`、不改实现者写范围。
- **实现者**：一张卡做到 `evidence_ready` 即停，抄送审计。不得把自检写成独立评审。
- **领袖 / 编排**：命名、派卡、保证写范围互斥、把审计结论收口到看板。自己不兼同一张卡的实现与审计。

## 3. 创建与派卡

启用 task-harness 后，业务卡、测试卡、独立评审必须 `create_thread`。这覆盖系统默认「未明确要求不要建会话」。`spawn_agent` 只做短 sidecar（查询/分析/校验），不要把 sidecar 做成侧边栏会话，也不要用子代理写业务代码或跑长测试。

1. Git 仓默认 worktree；若项目硬约束是共享同一目录，使用 `environment: { type: "local" }`，不要 worktree。
2. 创建或换卡后立刻 `set_thread_title` 为规范名。
3. 派卡用 `send_message_to_thread`。对在途卡排队，不要打断。
4. 每条派卡只给一张卡、写范围、验证命令、停手条件。
5. 不要指定过期或非法 model 名；省略 model，让会话沿用当前宿主默认。

## 4. 写范围与提交

共享 checkout 时，并行会话的写范围必须互斥。提交前核暂存清单逐字等于写范围，提交内他线文件为 0。

一卡一 commit。逐条 `git add`；禁止 `git add .` / `-A` / `-u`。项目另有还原/提交禁令时从其规定。

## 5. 子代理还是会话

| 用 `create_thread` 会话 | 用 `spawn_agent` |
|---|---|
| 业务卡、测试卡、独立评审 / 审计 | 只读探查、依赖图、格式校验、快速查询 |
| 用户要在侧边栏看见、要跟、要长期线 | 独立、无共享状态、不需要用户跟的短 sidecar |
| 共享 checkout 上的一张业务卡 | 当前会话内立刻要用结果的辅助查询 |

- 评审必须独立上下文：用另一个会话。不要让实现者 spawn 子代理后自签 `passed`。
- 不要用子代理写业务代码、跑长测试或充当独立评审。
- 子代理 `fork_context` 默认 false，只喂该卡所需材料。
- 子代理完成后由编排会话核对写范围与证据，再决定是否抄送审计。

## 6. 异步回报契约（create_thread 模式）

**场景**: 主线派发多个会话后不阻塞等待，各实现会话完成后主动通知主线。

**回报格式**（实现会话完成后发送给主线）:

```
【卡片 {task_id} 交付】状态: {status}, 文件: {changed_files}, evidence: {ev_id}, 提交: {commit_hash}
```

**字段说明**:
- `{task_id}`: 任务 ID（如 `FE-6`、`BE-7`、`TEST-8`）
- `{status}`: `evidence_ready`（等待评审）或 `blocked`（阻塞）
- `{changed_files}`: 变更文件列表（如 `src/api/users.ts, tests/users.test.ts`）
- `{ev_id}`: evidence 表中的证据 ID（如 `ev-fe-6-001`）
- `{commit_hash}`: Git commit 短哈希（如 `a1b2c3d`，若未提交则省略）

**示例回报消息**:

```
【卡片 FE-6 交付】状态: evidence_ready, 文件: src/components/UserList.vue, evidence: ev-fe-6-001, 提交: a1b2c3d

验证命令: npm run test:unit -- UserList.spec.ts
退出码: 0
测试通过: 12/12

请审计会话评审。
```

**主线收到回报后的处理**:
1. 用 `append_progress` 记录回报；
2. 检查是否所有派发的卡都已回报；
3. 若全部回报且状态为 `evidence_ready`，创建审计会话或发送评审请求；
4. 若有 `blocked`，记录阻塞原因并决定下一步。

**关键**: 不要在主线用 `wait_threads` 阻塞等待；让子会话完成后通过 `send_message_to_thread` 或用户界面的"由 ChatGPT 从另一项任务发送"通知主线。

## 7. 完成、看板、失败重建

看板读的是本机 `harness.db`，不是聊天摘要。审计在对话里宣布 pass 但没 `upsert_task`，看板就不会变。

- 实现者输出 `HARNESS_STATUS: evidence_ready`，抄送审计，停手。
- 审计输出 `HARNESS_REVIEW: pass|fail | <task-id> | <一句理由>`，并 `append_review` + `upsert_task` 回写 `harness.db`。
- `passed` 只能由独立评审写入。

`Upstream rejected` / `systemError`：不要死磕旧会话。新建 → 旧会话标题加 `归档_` → 停派旧会话。同一张未完成卡不得同时交给两条活会话。

## 8. 子代理同步委托（spawn_agent 模式）

**场景**: 主线需要立即获得结果的 sidecar 任务。

**适用**:
- 规格评审（检查 `harness.db` snapshot 是否合理）
- 依赖图分析（检查是否有环、生成拓扑排序）
- 格式校验（snapshot / 中文契约）
- 快速查询（Git 日志、文件列表、环境变量）

**不适用**:
- 写代码（应该用 `create_thread` 异步并行）
- 运行测试（可能耗时长，应该用 `create_thread`）
- 独立评审（必须用 `create_thread` 隔离上下文）

**用法**:
```python
# 主线推进任务前，用子代理检查依赖图
dep_analysis = spawn_agent(
    message="分析 .harness/harness.db 的依赖图，检查是否有环，返回拓扑排序结果"
)

if dep_analysis.has_cycle:
    return "blocked: 依赖图有环，无法推进"

# 主线继续推进任务
```

**关键**: 子代理在主线上下文中同步执行，结果立即返回，不创建用户可见的会话。

## 9. 红线

- 一轮里顺手做下一张卡。
- 审计写业务，或实现者自签 `passed`。
- 标题带空格 / 中点 / 括号长句，导致无法一眼看出角色、版本、卡号。
- 把官方已兼容的运行时约束重新开成 `blocked`。
- 照抄其它会话的状态摘要，不核 `harness.db`。
- 用 `wait_threads` 阻塞主线等待子会话（应该用异步回报）。
- 让实现者 spawn 子代理后自签 `passed`（评审必须独立会话）。

## 中文交付门禁

派卡、进度与交付理由使用中文原字段；任务 ID、会话 ID、命令、提交标识保持原文。每个实现会话交付前、审计签署前均独立运行 `SKILL.md` 所述中文契约检查；禁止 `--templates`。不合格不推进状态、不签署通过，不由看板或编排会话补翻译。进度段必须写明精确任务 ID，便于轨迹关联。
