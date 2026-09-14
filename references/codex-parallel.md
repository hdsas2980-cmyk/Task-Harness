# Codex 多会话与多子代理并行

并行不等于一轮多任务。一轮仍只推进一张卡或完整束；sidecar 只持明确辅助范围。原生参数、授权、Fork/Worktree 与 UI 操作的唯一细则见 references/codex-native.md，状态机以 SKILL.md 为准。

## 0. 遵守宿主授权

启用技能后独立读密集工作优先 `spawn_agent`；写密集工作先检查隔离。先规划主线下一步，再委托非阻塞小任务，避免派出关键路径后空等。左侧新聊天必须同时满足：用户明确要求创建新聊天、`spawn_agent` 已达到宿主容量上限、且有侧栏并行/长期上下文/隔离写入的实际需要。未满员不得 create_thread。独立评审要求新上下文，且同样不能豁免上述门槛；原生 `/review` 仅在等价契约成立时替代最终独立评审。

`wait_agent` 收取 `spawn_agent` 结果；`wait_threads` 等待或收集已经创建的会话。按依赖有界等待，不无条件轮询；结束用 close_agent 释放名额。

## 1. 会话标题

以下标题规则用于已授权的 Harness 编排任务；用户明确指定的标题优先。创建、换卡、作废时更新映射，不凭标题判断状态。

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

- sidecar 做测试执行、测试结果分析、日志收集、代码定位等独立辅助工作；不得擅自领下一张业务卡。
- 左侧新聊天必须同时满足：用户明确要求、`spawn_agent` 已达到宿主容量上限、且有侧栏并行/长期上下文/隔离写入的实际需要；不满足任一条件不得创建。
- 实现者到 evidence_ready 停手；原生 `/review` 只有满足原生审查等价契约时才能替代 Harness 最终独立评审，否则必须新的非 Fork 独立上下文，不用实现 sidecar 自签。
- 审计只读材料与必要源码，输出 HARNESS_REVIEW；唯一获授权的控制库写入者核对来源、追加 review、运行语言门禁后更新状态。避免审计与领袖重复写库。

## 3. 创建与派卡

普通任务调用 `create_thread` 前先核对用户明确的新聊天请求、`spawn_agent` 容量已满及实际并行需求；独立审计只有原生 /review 不满足等价契约时才创建同样受此门槛约束的新会话。按原生路由 list_projects → Git/worktree 或非 Git/local → 最小初始 prompt → 核验 ID。用户指定直接使用保存项目时遵从。

初始 prompt 已派卡，不立刻重复 send_message_to_thread。clientThreadId 仅表示工作区准备中；正式 threadId 就绪后才使用消息/等待工具。不指定 model/thinking，除非用户明确要求。失败或超时先查询是否已经创建，不能盲目重复。

## 4. 写范围与提交

多写入者需独立 worktree 或已证明互斥的写集；不能共享 index/提交动作。任务回报携带 source revision、dirty diff 或提交摘要、changed files、worktree、验证记录。提交与合并遵循用户授权，不把“回报完成”当自动 cherry-pick。独立 worktree 不自动拥有命名 branch，Fork 也不自动创建 Git branch。

## 5. 子代理还是会话

| 需求 | 选择 | 边界 |
|---|---|---|
| 当前卡的独立读密集辅助工作 | spawn_agent | 主线继续非重叠工作，结果核验后关闭 |
| 当前卡的写密集辅助工作 | 隔离后子代理或主线串行 | 无互斥写集就不并行 |
| 用户明确要求且 spawn_agent 已满 | create_thread | 还必须存在侧栏并行、长期上下文或隔离写入的实际需要 |
| 用户要求从当前历史分支 | fork_thread | 不能用于最终独立审计 |
| 最终完成评审 | 等价原生 /review，或显式授权后新的非 Fork 审计任务 | 原生回执不等价时不得替换；缺授权/上下文则记录阻塞 |

## 6. 异步回报契约（create_thread 模式）

派卡提示词包含 task_id、项目/canonical DB、工作区、输入基线、写范围、验证命令、停止条件及回报要求。回报最少：

```text
【卡片 {task_id} 交付】状态: {status}, 文件: {changed_files}, evidence: {ev_id}, 提交: {commit_hash_or_uncommitted}
工作区: {absolute_workspace}; 基线: {source_revision}; 限制: {limitations}
HARNESS_STATUS: {task_id} IN_PROGRESS
EXIT_SIGNAL: false
```

会话不会自动把提交动作、合并、cherry-pick 或 DB 回写交给主线。主线从 wait_threads/read_thread 获取实际结果，核对后才 append_evidence/append_progress/upsert_task；不要依赖子任务一定会主动跨会话发消息。集成后重新验证，原 worktree 的 pass 不等于集成通过。

## 7. 完成、看板、失败重建

实现交卷到 evidence_ready 不是 COMPLETE；独立审计按 completion-review.md 输出契约。主线核验材料一致、追加 append_review，通过门禁后才能 passed。看板和宿主 UI 不能替代 DB。

会话出错时先确认在途状态/工作区是否仍被占用，保存 checkpoint。需要重建时重新检查新聊天授权；结果不明不盲目重派。用户要求归档才调用 set_thread_archived，重命名加“归档_”不是实际归档或停止执行回执。

## 8. 子代理同步委托（spawn_agent 模式）

每项写清输入、只读/写入范围、验证命令和返回摘要。仅下一步依赖结果时 wait_agent；完成后核对实际产物，close_agent。测试可能写缓存/制品或占端口，也要隔离；测试文件编写属于写密集工作。子代理结果不能替代新的非 Fork 最终独立 review。

## 9. 红线

不能因满员或评审需求自动创建用户侧栏聊天；未满员也不得创建左侧新聊天。不能将 Fork、实现 sidecar 或同轮自检作为最终审计；原生 /review 仅在等价契约成立时例外替代。不能把 clientThreadId 当正式 ID；不能让一张未完成卡同时交给两条活实现线；不能把未知回执写成 passed、停止成功或释放写锁。主会话没有左侧并行新会话时不得星标。

## 中文交付门禁

派卡、进度、交付理由使用中文原字段；机器字段（ID、命令、路径、SHA、退出码、工具回执）可保留原文，但其相邻的结论/原因/下一步必须有非空中文说明，ID、命令、路径、技术输出保持原文。主线交付与独立审计分别运行中文契约检查（不传 --templates）；失败不推进，不由看板补翻译。记录精确 task_id 与来源，不篡改历史 evidence/review。
