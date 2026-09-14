# Codex 原生能力与 Task-Harness 融合规划

日期：2026-09-14。范围：codex 分支的原生操作路由和既有编排规范。状态：源码候选已实现，验证记录见文末；未经独立最终评审，未重装用户全局 skill。本文件不推进同目录既有工厂 P0–P5 任务，也不迁移当前项目 DB。

## 1. 目标与设计决定

保留一轮一任务/束、SQLite 单一真相源、证据 + 独立评审门禁；复用宿主命令，不增加 commands/、私有数据库控制器、后台服务或第二套状态机。

D01：SKILL.md 只保留常驻硬规则与按需入口，11 项原生操作归 references/codex-native.md；调用工具前核对当轮 schema。
D02：/init 仅项目 AGENTS.md，Harness DB 单独初始化；/status 只读，不能用 resume 或新聊天代替。
D03：/plan 切模式，update_plan 仅步骤；/goal 是显式开启的持久目标，不随计划自动创建；/memories 是权限配置而非写条目。
D04：新聊天/Fork 与 Git branch/Worktree 分开；左侧 create_thread 必须同时满足用户明确要求、spawn_agent 已满和实际并行需要。满员不是单独授权。
D05：官方 /review 与最终独立评审逻辑能力不等价，不能直接替换；仅等价回执可写入最终 review。否则仍用新的非 Fork 独立 Codex 任务；缺授权/上下文保留证据并记录阻塞。
D06：Compact、Fork、新聊天前后衔接 checkpoint；主会话仅在左侧已有新会话并行时星标。星标/重命名仅导航，不强行初始化或写 DB，不改变任务优先级。
D07：不把官方文档或工具存在写成运行通过；文本和安装测试不等于宿主真机验收。

## 2. 分层设计

| 层 | 权威内容 | 不能替代的事项 |
|---|---|---|
| 宿主命令/工具 | 模式、目标、聊天资源与导航操作的实际回执 | Harness 业务验收 |
| Skill 路由 | 意图、前置条件、动作、结果核验与失败处理 | 宿主权限与工具 schema |
| canonical harness.db | 任务定义、证据、评审、进度与状态 | Git 实际文件和宿主运行态 |
| Git/制品/测试 | 代码身份与可重放结果 | 独立 review |
| 记忆/聊天摘要 | 历史线索与恢复提示 | 当前事实与验证证据 |

以上权威各司其职。发生冲突应保留双方证据、暂停受影响写入并对账，不以“文件更新”自动覆盖 DB 或作废审计。

## 3. 能力落点与验收门禁

| ID | 能力 | 正向验收 | 关键负例 |
|---|---|---|---|
| N01 | 初始化 | AGENTS.md 与 DB 分开，重复执行保留已有内容 | /init 自动建库或迁移未知 schema |
| N02 | 代码审查 | 固定 diff/未跟踪文件范围；原生 /review 不等价则不得替换最终独立 review | 打开 review 面板就 passed |
| N03 | 聊天分支 | /fork/fork_thread 记录来源和实际工作区 | Fork 当 Git branch 或最终审计 |
| N04 | 新聊天 | 明确请求且 spawn_agent 已满、list_projects、合法项目/环境、核验 threadId | 未满员或满员自动新建，clientThreadId 当 threadId |
| N05 | 压缩上下文 | checkpoint → 原生压缩回执 → 读库/Git 恢复 | 文本摘要声称 /compact 已执行 |
| N06 | 星标 | 主会话仅在左侧已有并行新会话时 pin；唯一 ID、读回 | 无并行新会话 pin 主会话，或提升任务 priority |
| N07 | 状态 | 分会话用量/运行态/goal/DB 报告，未知如实标注 | 查询触发初始化或恢复执行 |
| N08 | 目标 | 显式创建、避免重复、预算与阻塞阈值遵守 schema | 自动创建目标、预算耗尽即 complete |
| N09 | 计划模式 | /plan 与 update_plan 分开，遵守真实模式 | Default 使用 Plan-only 输入工具 |
| N10 | 记忆 | /memories 与读写分开，按宿主规则窄搜索与引用 | 未授权写 MEMORY.md 或存凭据 |
| N11 | 重命名 | 定位 ID、用户标题优先、读回 | 强改用户指定标题或 task ID |

## 4. 实施顺序与变更面

1. 核验官方 slash commands 与当前工具定义，冻结原生能力边界。
2. 编写按需 reference；同步 SKILL.md、README.md、SETUP.md 和派卡/并行文档，消除旧“覆盖系统默认、满员新建”的冲突。
3. 补契约回归与安装副本测试，检查 N01–N11、错误参数/授权负例、Markdown 编码与链接。
4. 在临时 CODEX_HOME 运行 Windows/POSIX 安装器，确认整个 reference 和运行时被带入；不替换全局安装副本。
5. 独立评审与授权的真实宿主探针后，再完整备份重装。当前不创建用于测试的新聊天、不 Fork、不压缩当前会话、不设 goal、不写全局记忆。

Board 在存在 harness.db 时改为校验数据库 snapshot，忽略 leftover JSON/TXT；无库时仍可读 JSON 以便未转换目录。写入 API 增加中文契约门禁。这是为消除其他主机反复出现的 progress.txt 契约误报，不是工厂产品验收。

## 5. 非目标与降级策略

- 不实现工厂控制面、任务调度服务或 DB schema migration；不修改已有工厂计划/卡状态。
- 不安装自定义 slash commands；缺原生工具则提供经核实的用户入口，不发送伪命令。
- 新聊天创建回执未知先查询消歧，不盲目重派；Fork/归档不代表停止进程或释放写锁。
- 无独立审计授权/环境时保留 evidence_ready 与阻塞原因；这不是缺失证据下的通过。
- 重大技能变更必须用安装器完整备份重装，当前会话已加载内容不保证热更新。

## 6. 来源与验证边界

官方来源及 2026-09-14 核对范围集中在 [原生路由 §8](../../references/codex-native.md)。web 搜索/打开未返回正文，随后 fetch 读取官方 Markdown 正文；本轮工具 schema 属于静态宿主观察。公开文档可能重定向到 ChatGPT Learn，不据此推断本机产品版本。

自动化测试验证文档契约、安装载荷与已有代码回归；N01–N11 的真实宿主动作均未执行，未签署 Harness pass。

## 7. 交付文件

- [原生命令融合层](../../references/codex-native.md)
- [主规则](../../SKILL.md)
- [并行/派卡契约](../../references/codex-parallel.md)
- [下一步模板](../../references/templates/next-step.md)
- [验证记录](2026-09-14-codex-native-validation.md)
