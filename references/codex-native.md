# Codex 原生命令融合层

## 0. 先判意图，再判能力

本文件是 task-harness 的原生操作路由，不安装斜杠命令、不模拟宿主 API。仅讨论/规划这些能力，不代表授权实际创建聊天、设置目标、修改记忆或初始化当前项目。

执行顺序：识别用户意图 → 核对当前宿主工具定义/命令菜单与权限 → 执行原生动作 → 核验回执 → 仅在影响项目执行时记录 Harness 进度。技能不能覆盖系统/开发者指令。工具未暴露时说明限制，提供用户可执行的原生入口，不把文字回复当执行成功。

来源分层：官方命令文档是 documented；本轮工具 schema 是 static_observed；成功调用及读回才是 observed/verified；业务 passed 仍需 evidence + 独立 review。不同版本、平台与账号的入口可能不同。

## 1. 能力路由总表

| ID / 用户意图 | 原生入口 | Harness 配合 | 回执与边界 |
|---|---|---|---|
| N01 初始化 | /init 生成 AGENTS.md | Harness DB 初始化是另一动作，见 §2 | AGENTS.md 存在不代表 DB 已初始化 |
| N02 代码审查 | /review；open_in_codex 的 review 仅打开差异视图 | 若原生审查满足 §3 的等价契约，可直接作为 Harness 最终独立评审；否则仍需 Harness 评审 | 打开面板不等于执行审查；等价前不得替换，也不自动 passed |
| N03 聊天分支 | /fork；fork_thread；CLI codex fork | 先 checkpoint，核对源聊天与目标工作区 | Fork 继承历史，不是独立审计；不是 Git branch |
| N04 新聊天 | New chat；/task 无项目聊天；create_thread | 左侧新会话只能在 `spawn_agent` 已达到宿主容量上限、且确需并行/侧栏可见/隔离写入时创建；用户明确请求仍是必要条件 | 获取正式 threadId 后才派后续消息；clientThreadId 不可用 |
| N05 压缩上下文 | /compact | 先落 checkpoint，恢复时读 DB 与工作区 | 没有压缩工具时只准备恢复材料，请用户执行 /compact |
| N06 星标 | Pin/Unpin；set_thread_pinned | 主会话只有在左侧已有新会话并行时才可星标；仅影响导航，不改卡优先级和状态 | 定位唯一 threadId，成功后读回 pinnedThreads；无并行新会话不得 pin 主会话 |
| N07 状态 | /status；list_threads/read_thread/wait_threads；get_goal | 区分会话资源、宿主运行态、目标与 DB 业务状态 | 只读查询，不用 resume/new 代替状态查询 |
| N08 目标 | /goal；get_goal/create_goal/update_goal | 显式设置的持久目标可以跨多个执行轮，不替代任务图 | 仅用户/高优先级指令明确要求才创建，见 §5 |
| N09 计划模式 | /plan 或宿主模式选择器 | update_plan 仅维护步骤；不是切换计划模式 | 实际模式以宿主指令为准，见 §5 |
| N10 记忆 | /memories 配置；宿主提供的记忆读写入口 | 记忆做定位线索，项目事实回到 DB/Git 核验 | 记忆开关不等于新增条目；写入须明确授权 |
| N11 重命名 | Rename chat；set_thread_title | 编排任务用角色/版本/卡号；用户指定标题优先 | 以 ID 定位，读回真实标题，不改 task ID |

表中斜杠命令由用户在宿主输入框调用，不是终端 shell 命令。不要虚构 /pin、/rename、/memory 或桌面 /new；以当前菜单为准。Windows 的命令菜单可用于寻找新聊天、星标和重命名，不依赖硬编码快捷键。

## 2. 初始化：分开 AGENTS.md 与 Harness DB

1. 用户要原生 /init：检查项目内外适用的 AGENTS.md，保留既有规则，生成或合并项目导航、测试入口及本技能指针。不要覆盖用户内容、复制整个 SKILL.md 或写入凭据。没有可调用 init 工具时，可以在明确授权下直接编辑 AGENTS.md，但报告“文件编辑”，不是“执行了 /init”。
2. 用户要初始化 Harness：先解析项目绝对路径、检查既有 canonical DB/工作区绑定与任务定义。已有 DB 用 HarnessDB.open(project, create=False) 只读检查，停止重复初始化；多工作区不能各自建立第二个权威库。
3. 全新项目才用 HarnessDB 建库，写中文 project/description、rev、任务、progress；任务最少有 id、name、desc、reason、next、status=pending、depends_on、verify。没有验收定义先补定义，不造 evidence/review。已有 DB 的 create=True 入口可能初始化 schema，未知版本先停止，不拿它当通用迁移器。
4. 运行安装副本 scripts/check_task_harness_language.py <项目绝对路径>，退出码 0 后读回 snapshot；这是结构/语言验证，不是业务通过，也不自动授权启动第一张卡。
5. 旧 JSON 项目只经 scripts/convert_harness_json.py 一次性导入，保留备份，导入后不双写。备份活 SQLite 要考虑 WAL，不能仅拷贝一个可能未 checkpoint 的 DB 文件。

## 3. 代码审查：原生审查不自动签署 Harness

一般 /review 可审未提交变更或对比 base branch；记录范围、基线 SHA、diff/未跟踪文件摘要，区分“未发现问题”和“未覆盖验证”。可选 code-review skill 不是本技能的安装依赖。open_in_codex(review) 只显示差异，不能代替审查执行。

能力对照（documented，不是运行验收）：官方 `/review` 启动代码审查模式，检查未提交变更或对比 base branch。Harness 最终独立评审还要求：非实现者、非 Fork 新鲜上下文、核对 evidence/verify、中文契约、输出 HARNESS_REVIEW pass|fail 并门禁 `passed`。二者逻辑能力不一样，因此不能用原生审查整体替换 Harness 完成评审。

**原生审查等价替换条件**：只有当原生 `/review` 的实际回执同时包含审查基线与范围、变更/未跟踪文件摘要、验证命令及退出结果、独立审查者身份/新鲜上下文、逐项结论与中文理由，并明确 `pass|fail` 时，才可将该回执转换为一条 Harness review，替换本卡的最终独立评审，不再另开审计会话。仅显示 diff、给出建议、同一主会话自检、Fork 或缺少独立性/验证回执，均不等价；主线仍需核对来源、追加回执并运行中文契约检查。

最终完成评审在不等价时保留本分支的严格协议：实现者交付 evidence；新的非 Fork 独立 Codex 评审任务只读任务对象、对应 evidence、封存 diff、必要源文件及 references/review/completion-review.md。来源记录包含实际 threadId、基线与证据 ID；create_thread 没有 fork_context 参数，不向它传入子代理参数。Fork 或实现侧 sidecar 的意见仅作辅助，不作为最终 review。

创建审计任务同样受 §4 约束：仅用户明确要求创建新聊天，且 `spawn_agent` 已达到宿主容量上限。没有授权或独立上下文时保留 evidence_ready，记录真实阻塞，不自动创建、不伪造 review。审查者输出 HARNESS_REVIEW: pass|fail | <task-id> | <中文理由>；主线核对来源和材料未漂移，追加 append_review、进度并通过中文契约后，才能更新任务。只有独立 `pass` review 与 evidence 同时存在且仍匹配当前材料，才允许 passed；fail 返回 active。并行修改导致基线漂移必须重新验证/送审。

## 4. 新聊天、Fork、Worktree 与线程整理

- 仅用户明确要求创建新聊天，且 `spawn_agent` 已达到宿主容量上限，并确需侧栏并行/长期上下文/隔离写入时，才可用 create_thread。满员不是单独授权；未满员先 close_agent 已完成对象，或串行/等待。skill 启用、独立评审需求或“规划新聊天支持”都不替代这三项条件。
- 创建项目前先 list_projects，使用返回的 projectId 和 isGitRepository：Git 默认 worktree，非 Git 默认 local；用户明确要求直接使用保存项目则遵从。没有匹配项目先消歧，不伪造 projectId。仅无仓库工作用 projectless；仅明确请求云任务才选云。
- 默认省略 model、thinking 和 startingState。只有用户要求指定 Git 状态才传 startingState；仅用户指定的新分支名才能使用 onMissing=create-branch。Worktree 可能是 detached HEAD；独立 worktree 不等于已有命名分支。
- create_thread 的初始 prompt 已经派卡，不再立即发送相同任务。返回 clientThreadId 时是排队设置中，不能作为 threadId 使用。成功创建后按宿主要求输出 created-thread 指令；ID 解析为正式 threadId 后才使用 wait_threads/send_message_to_thread。
- fork_thread 仅在用户要求从现有聊天分叉时使用；同目录默认共享文件，不代表写隔离。只有完成的历史会复制，源任务进行中的 turn 不会复制。Fork 完成后如需继续执行，再 send_message_to_thread，交接未进入历史但已经落盘的 checkpoint。
- 等待区分 wait_agent 和 wait_threads；一次紧凑快照或带 cursor 的有界等待优于重复读历史。回执不自动合并代码、不自动 cherry-pick、不自动回写 DB。
- 主会话星标前先确认左侧至少有一个并行新会话；再 list_threads，使用返回的原始标题及 threadId 消歧；已有 pinnedThreads 含全部星标项。当前任务 ID 未知时也不能凭空构造。读取后 set_thread_pinned/set_thread_title，再读回结果。
- 编排标题正则见 references/codex-parallel.md；用户明确指定名称优先，不强行套卡号。Pin 不替代归档，重命名不改变 Harness 任务 ID；纯导航操作无需初始化/写入 DB。仅影响派卡时追加映射记录。
- 用户要求归档用 set_thread_archived；归档不等于终止执行进程或释放写锁，不能用改名“归档_”声称已归档。

## 5. 状态、目标与计划模式

/status 显示聊天 ID、上下文用量及限额，不显示 Harness 完成度。工具 get_goal 查询目标；list_threads/read_thread/wait_threads 查询宿主运行状态；HarnessDB 的只读 snapshot 查询项目状态。缺失用量/上限就报告不可用，不估造 token。业务状态仅使用 SKILL.md 的 pending/active/evidence_ready/passed/blocked/regressed；unknown 是回执未知描述，不新增任务状态。

目标：先 get_goal，避免重复创建；仅显式要求才 create_goal，token_budget 也只在用户明确指定时填写。update_goal 仅按当前 schema 标记真正完成或真实阻塞：同一阻塞至少连续三个 goal turns 且无法进展才可 blocked，恢复后重新计数。预算将尽、单轮结束、待评审都不自动等于目标完成。预算目标完成后报告工具返回的最终 token 使用量；暂停/恢复/修改预算由宿主 UI 控制，不能虚构工具参数。目标要求整体项目完成时仍以 Harness 验收门禁为准。

Plan：回答“怎么做”。/plan 切换宿主计划模式；update_plan 只管理 pending/in_progress/completed 步骤，至多一个 in_progress。写了规划文档或调用 update_plan 都不能声称切入 Plan mode。request_user_input 仅宿主明确处于 Plan mode 且工具可用时调用；Default 模式必要时用简短自然语言澄清。真正 Plan mode 遵守只规划不实施的宿主限制；“规划并提升”也不覆盖该限制。

## 6. Compact 与记忆：恢复而非复制真相源

压缩前在 DB progress 追加 checkpoint：项目与 canonical DB 绝对路径、任务 ID/rev、当前阶段、Git SHA/dirty diff、写范围、已执行命令与退出码、evidence/review ID、制品路径、未决阻塞、下一步、在途线程/代理 ID。敏感信息只留定位方式，不保存 secret 值。大日志到 artifacts；不创建 tasks.json 或 memory.md 作为第二份活状态。纯聊天没有 Harness DB 时可提供交接摘要，不强行初始化项目。

当前工具集没有 compact 操作时，报告“checkpoint 已准备，原生压缩尚未执行”，请用户使用 /compact；普通摘要不等于压缩。压缩完成后的恢复顺序：读 canonical DB/current task → 当前卡的依赖与相关 evidence/review/progress → Git 状态与写范围 → 确认下一步。以 DB、文件和可重放命令为准；若相互冲突，停止受影响操作并保留双方证据，不直接覆盖 DB。没有待办时不因压缩自动找新活。

记忆：/memories 管理宿主记忆权限，不是条目写入命令。按当前宿主提供的 memory 路径/引用规则做窄搜索；无记忆能力则如实说明。读取记忆不替代当前版本、DB、Git 核验；引用历史但未核实时标明可能过时。只有用户明确要求记住/更新/删除才走宿主允许的写入通道；若宿主要求 extensions/ad_hoc/notes/<timestamp>-<slug>.md，只新增一份小更新说明，不直接改 MEMORY.md、摘要或旧 rollout。项目 checkpoint 不写入长期记忆，密钥与临时运行噪声也不保存。

## 7. 最小验证场景

N01–N11 每项检查“用户意图、可用入口、权限、预期回执、失败路径、DB 是否应该改变”。静态文本/安装测试只能验证路由契约，不证明宿主执行。运行探针必须另有范围授权；不要为验证该 skill 自动新建聊天、Fork、设置目标、压缩当前上下文或写全局记忆。

重点负例：把 /init 当 DB 初始化；把 update_plan 当 Plan mode；满员自动新建聊天；Fork 自签 review；clientThreadId 派消息；无回执声称已压缩；Pin 提升任务优先级；status 初始化数据库；只读记忆变写入；目标缺评审直接 complete。

## 8. 来源与版本（2026-09-14 核对）

官方资料不保证当前本机菜单完全一致。具体工具参数和授权以调用当轮 schema 为准，本轮未对所有原生操作做真实调用。

- 斜杠命令、/init、/review、/status、/goal、/plan、/memories、/compact、/fork：`https://learn.chatgpt.com/docs/reference/slash-commands.md`
- 桌面新聊天/星标/重命名操作：`https://developers.openai.com/codex/app/commands.md`
- CLI fork/resume：`https://developers.openai.com/codex/cli/slash-commands.md`
- Git Worktree 与 detached HEAD：`https://developers.openai.com/codex/app/worktrees/`
- 子代理委托约束：`https://developers.openai.com/codex/concepts/multi-agents/`
- Desktop 工具、goal、plan、memory 的精确限制：当轮宿主提供的工具 schema/指令（static_observed，不作为跨版本公开 API 保证）。
