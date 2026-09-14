---
name: task-harness

disable-model-invocation: true
description: Codex 长时任务骨架：一轮一任务与任务束、harness.db 单一状态、证据和独立评审门禁。支持初始化、代码审查、新聊天和分支、压缩上下文、星标、状态、目标、计划模式、记忆与重命名；多会话/子代理按宿主授权，spawn_agent 配 wait_agent，新聊天 create_thread 配 wait_threads，含会话命名、派卡与归档。重大变更须完整备份重装。
---

# task-harness v3.1 — Codex Native

## 调度硬规则（遵守宿主授权）

本技能要求：独立读密集工作优先并行 `spawn_agent`，写密集工作先确认隔离与互斥范围；先决定主线立即要做的工作，再委托不阻塞该步骤的小任务。技能不覆盖系统/开发者指令，也不改变工具的授权边界。多会话并行时，左侧新聊天与主会话星标都有额外门槛。

1. 束内多卡在当前会话串行；普通任务先使用 `spawn_agent` 处理明确的 sidecar，主线继续非重叠工作。
2. 左侧新会话使用 `create_thread` 必须同时满足：用户明确要求创建新聊天、`spawn_agent` 已达到宿主容量上限、且确需侧栏并行/长期上下文/隔离写入。缺一不可。满员不是单独授权；未满员不得创建左侧新聊天，应关闭已完成代理、等待或串行。
3. 官方 `/review` 是代码差异审查，与 Harness 最终独立评审不等价，不能直接替换。仅当原生审查回执满足等价契约时，才将其写入最终 review，不再另开审计会话；否则必须新的非 Fork 独立审计上下文。缺少授权或独立上下文时保留待评审证据并记录阻塞，不自行创建。
4. 主会话通道仅在左侧已有新会话并行时可以星标；星标只影响导航，不改任务优先级或状态。
5. `wait_agent` 对应 `spawn_agent`，`wait_threads` 对应已经创建的会话，二者不是禁用项。按下一步依赖有界等待；结束及时 `close_agent` 释放名额。
6. 线程工具不会自动把提交、合并、cherry-pick 或 DB 回写交给主线。主线核对 diff、来源与证据，决定是否合并并重新验证。

工具参数与 11 项原生命令路由见 [Codex 原生能力路由](references/codex-native.md)；编排标题/派卡/回报见 [多会话细则](references/codex-parallel.md)，执行提示词见 [下一步模板](references/templates/next-step.md)。

## 技能更新（重大变更必须卸载重装）

拉仓库、拷 `SKILL.md`、手工覆盖 `$CODEX_HOME/skills/task-harness` 都不算更新。Agent 读的是安装副本，不是仓库。

以下任一改动都是重大变更，必须在每台使用本技能的主机上卸载后重装：

- `SKILL.md` 调度协议、任务束、评审契约
- `references/codex-parallel.md` 或 `references/templates/next-step.md`
- `references/`、语言校验器、`harness_db.py` 与转换脚本

做法：在仓库根目录重新执行 `scripts/install.ps1`（Windows）或 `scripts/install.sh`。安装脚本会先把旧目录移到 `$CODEX_HOME/skill-backups/`，再写入新副本。禁止只覆盖单个文件。

若安装副本缺少 `references/codex-native.md`，或文首仍写旧式越权调度规则，视为旧版：停止按旧规则编排，先完成评审并用安装器重装。校验已安装 SKILL.md、references 与运行时的内容摘要，不仅检查版本标题。

## 定位与哲学

最小的骨架换最大的问责。保留 v3.1 的三条主线：

- **一轮一任务**：每个 Codex 任务只推进一个可验证的最小工作单元。
- **存在性先于实现**：先过 ponytail 阶梯，砍掉不需要、重复或可由平台能力解决的任务。
- **证据 + 独立评审才算完成**：`passed` 不是模型自报，而是可重放的验证证据和独立评审共同成立。

状态全部落盘，主 Codex 任务只读取当前任务和它触及的文件，不随任务数量增长而回读历史。宁可骨架简陋，不可问责缺失：不因"精简"砍掉验证、安全、错误处理和可回滚性。

本版本是 **Codex 原生适配版**：不依赖 Claude Code、CC Switch、gstack、MCP 或其他第三方 Skill；不写入 `.cc-switch\skills`；不使用 Claude 专属 slash command；本分支不包含 `commands/` 目录。

## Codex 原生能力路由

用户要求初始化、状态、目标、计划模式、记忆、压缩上下文、星标、重命名、代码审查、新聊天或聊天分支时，先读取 [Codex 原生能力路由](references/codex-native.md)。原生线程管理只管理聊天，不替代 `.harness/harness.db`、evidence 或独立 review；分支/Fork 不等于独立审计。

## Codex 运行契约

1. **当前 Codex 任务 = 一轮**：默认只推进一个任务；不要在同一轮顺手处理邻近任务。
2. **状态外置**：唯一真相源是 `.harness/harness.db`。禁止把 `tasks.json`、`evidence.jsonl`、`reviews.jsonl`、`progress.txt` 当活数据读写；没有 DB 就是未初始化，不是回退 JSON。旧项目先跑一次 `scripts/convert_harness_json.py` 整目录导入，旧文件只作只读备份。
3. **最小读取**：用 `HarnessDB.open(project, create=False).read_snapshot()` / `get_task()` 读 `.harness/harness.db`；只取当前任务、依赖结论、progress 末段和触及的代码。不要手写 SQL，不要为了看板去跑 HTTP，不要读旧 JSON。
4. **工具原生优先**：在 Windows/Codex 上优先使用 PowerShell 和现有本地工具；已有测试、构建、格式化工具优先于新增依赖。
5. **评审隔离**：实现者不能充当独立评审者。优先使用另一个 Codex 上下文/评审任务；无法获得独立上下文时必须如实记为 `blocked`，不可把同一轮自检冒充独立评审。
6. **不伪造完成**：没有可重放证据、评审契约或依据不足时，状态只能是 `evidence_ready`、`blocked` 或回到 `active`。
7. **调度与授权**：遵守文首硬规则及 `references/codex-native.md`；读密集子代理优先，左侧新聊天还要子代理已满，最终评审仅在原生审查等价时替换，否则用非 Fork 独立审计。

## 核心不变式

1. 一次 Codex 任务只推进一个依赖已满足、优先级最高的 `pending`/`regressed` 任务。
2. 不回读全量清单、不回读旧证据；只读取推进当前任务所需的最小范围。
3. `passed` 必须同时存在一条对应 evidence 记录和一条 reviews 的 `pass` 记录（都在 `harness.db` 表里，不是 JSONL 文件）。
4. 评审必须在独立上下文完成，并记录评审上下文/来源。
5. 任何阻塞必须写入结构化 reason；不得用"看起来没问题"替代验证。
6. 已通过任务受依赖、接口或环境变化影响时，标记 `regressed` 并回到 `active`。

## 任务束（Bundle）

**定义**: 多个任务组成的原子工作单元，束内任务必须在同一个 Codex 会话中串行完成，全部通过才算束完成。

**适用场景**:
- API 实现 + 对应测试（`t-backend-01` + `t-test-01`）
- 数据模型变更 + 迁移脚本（`t-schema-02` + `t-migrate-02`）
- 组件重构 + 依赖它的集成测试（`t-refactor-03` + `t-integration-03`）

**契约**:
```json
{
  "id": "bundle-user-api",
  "priority": 1,
  "desc": "用户 API 实现与测试",
  "name": "用户接口实现与测试",
  "reason": "暂无阻塞",
  "next": "实现接口后运行整束验证",
  "bundle": [
    {"id": "t-backend-01", "desc": "实现用户查询接口", "verify": "curl http://localhost:3000/api/users"},
    {"id": "t-test-01", "desc": "补充用户查询集成测试", "verify": "npm test -- user-api.test.ts"}
  ],
  "depends_on": [],
  "verify": "npm test -- user-api.test.ts",
  "status": "pending"
}
```

**推进规则**:
1. `bundle` 只接受任务对象数组，不接受 ID 字符串数组；束内任务按数组顺序串行推进；
2. 单个 Codex 会话推进整个束，不拆分到多会话；
3. 束内任务不在 `tasks` 顶层数组出现，只在 `bundle` 字段内；
4. 束的 `status` 由最后一个任务决定；所有任务 `passed` 才算束 `passed`；
5. 束的 `verify` 是整束验证命令，不是单个任务的验证。

**与多会话并行的关系**:
- 束 = 单会话内的串行原子单元；
- 多会话并行 = 多个束（或单任务）在不同会话中异步并行；
- 例：会话 A 推进 `bundle-user-api`（backend + test），会话 B 推进 `bundle-order-api`（backend + test），两束并行。

## 两种并行模式

### 模式 1：子代理辅助（spawn_agent）

先核对当前卡与写范围；将不阻塞主线下一步的独立读密集小任务委托给子代理。写密集任务必须有明确互斥写集或独立 worktree。主线继续非重叠工作，结果为硬门槛时才等待。`spawn_agent` 的结果用 `wait_agent`；核对摘要、实际变更与可重放验证后关闭代理。摘要不是独立最终 review。

### 模式 2：用户要求的新聊天（create_thread）

先按原生路由检查明确授权与 `list_projects`，再选 worktree/local。创建的初始 prompt 包含当前卡、工作区、写范围、验证命令、停止条件与回报格式；不要重复发送同一派卡。已创建的 `create_thread` 会话用 `wait_threads`，创建尚在排队时不能把 clientThreadId 当 threadId。

## 多会话并行（Codex 专属）

一轮仍只推进一张卡或完整束；辅助工作不扩张主线授权范围。每个写入者范围互斥、每张未完成卡只交给一条活实现线。返回结果先核对文件/提交/证据再串行集成。新建、Fork、星标、重命名等按原生路由处理，线程元数据不代替 Harness 状态；最终审计不写业务、不能由实现者自签。

## 状态机

页面显示中文，DB payload 仍使用英文枚举。任务数据本身必须以中文为人类可读语言：`project`、`description`、任务 `name`、`desc`、`reason`、`next`、证据 `summary`、评审 `reason` 和进度叙事必须使用中文。不得新增 `_zh` 字段，不得新增看板翻译层，不考虑旧版兼容；ID、状态枚举、命令、路径、revision 和哈希保持原文。没有看板时，直接读 `harness.db` snapshot 也必须能理解当前目标、状态、阻塞、验证和评审。

```text
pending（待处理） → active（进行中） → evidence_ready（待独立评审） → passed（已通过）
                        │              │
                        └─(评审未通过)→ active（进行中，带新证据重试）
   任意态 → blocked（已阻塞，记录 reason）
   passed → regressed（需回归，依赖变更导致失效，回 active）
```

## 三相流程

### 相 1 · 设计（一次性）

1. 对候选任务逐级过 ponytail 阶梯，移除伪需求、重复实现和不必要依赖。
2. 初始化 `.harness/harness.db`，不要把四份 JSON 当活数据。新项目可把 `references/templates/` 种子拷到 `.harness/` 后跑一次 `scripts/convert_harness_json.py`；或直接 `HarnessDB.open(project, create=True)`，`set_meta` 写中文 `project`/`description`，`upsert_task` 写中文 `name`/`desc`/`reason`/`next`，并保留稳定 `id`、`priority`、`depends_on`、可执行 `verify`、英文 `status`。字段与示例见 `references/language-contract.md`。
3. 识别需要原子推进的任务对，创建 `bundle`（API + 测试、模型 + 迁移）。
4. 按 `references/review/spec-review.md` 做规格评审，检查依赖环、路径归属、命令可执行性和工程原则。
5. 设计评审结论以中文 `append_progress`；运行下方中文契约门禁，通过后才可交付编排。不要把评审意见只留在对话里。
6. 编排落盘即可。可视化看板是独立目录，不随技能安装。

### 相 2 · 执行（每个 Codex 任务）

1. 读取 `harness.db` snapshot 与 progress 末段，得到当前可推进任务；先运行中文契约门禁，失败则修复 harness.db payload，不推进任务。
2. 只把一个 eligible 任务（或束）置为 `active`；修改前先确认范围和回滚点。
3. 只读该任务（或束内任务）、依赖结论、任务声明路径和必要代码。
4. 若是束，按 `bundle` 数组顺序串行推进每个任务；若是单任务，直接推进。
5. 运行验证命令（束的 `verify` 是整束验证），用 `append_evidence` 记录可重放证据；必填中文 `summary`，原始 `tests` 输出另存，不翻译或替换。
6. 更新中文 `reason`、`next` 并追加中文进度（任务编号、进展、状态、验证结论、下一步）；中文契约检查通过后才置为 `evidence_ready`，输出 `HARNESS_STATUS`，停手。
7. 不在本轮置 `passed`；等待独立评审。

### 相 3 · 评审（独立上下文）

1. 获得明确新聊天授权后新建非 Fork Codex 评审任务；没有授权/独立上下文则记录阻塞，不自签。评审任务读取项目路径、任务对象、evidence、变更范围/diff、`references/review/completion-review.md`。
2. 独立运行中文契约检查，并人工确认说明有实质意义；再按严重问题门禁检查安全、范围、测试、状态、可恢复性。
3. 输出 `HARNESS_REVIEW: pass|fail | <task-id> | <一句理由>`。
4. 主任务用 `append_review` 追加中文理由，更新中文 `reason`、`next` 和进度；再次通过中文契约检查后，收到 `pass` 才可改为 `passed`；收到 `fail` 则改回 `active`。

## 门禁

门禁在人手短路之前成立，而不是事后安慰。

1. 依赖检查：置为 `active` 前，所有 `depends_on` 必须为 `passed`。
2. 验证命令：`verify` 存在、可执行、退出 0。
3. 独立评审：每个 `passed` 任务对应一条 reviews 表的 `pass` 记录，且 `reviewer_context` 不等于实现者上下文。
4. 范围约束：变更文件逐个落在任务声明路径内；写操作有效，不自动扩展到邻近目录、其他项目或生产环境。所有覆盖/移动先建立带时间戳的备份或隔离副本。

5. 中文契约：设计交付、置为 `active` / `evidence_ready` / `passed` 前，必须执行以下只读命令（Python 3.10+）。`<技能目录>` 是当前所加载 `SKILL.md` 的所在目录；使用绝对路径，不切换到技能仓库执行任务，也不依赖源仓库。安装后的技能自带该脚本：

```text
python -X utf8 "<技能目录>/scripts/check_task_harness_language.py" "<任务项目绝对路径>"
```

退出非 0、缺少 Python/脚本、出现英文叙事或旁挂翻译字段时，均不得推进状态或签署 `pass`；只报告契约失败并修复授权项目的原字段。任务运行禁止使用 `--templates`。脚本仅检查结构、占位符与中文最低条件；评审仍须人工判断内容是否准确、充分，不能用一个汉字掩盖英文叙事。机器标识不翻译。

## 文件契约

唯一真相源：项目 `.harness/harness.db`。**不兼容** 把 JSON/JSONL/TXT 当活数据。没有 DB = 未初始化，不是回退 JSON。

- 任务表：`upsert_task` 写入完整 payload；状态为 `pending`、`active`、`evidence_ready`、`passed`、`blocked`、`regressed`。
- 证据表：`append_evidence({id, task, summary, cmd, exit, tests, rev, ts})`；`summary` 是必需中文摘要，`tests` 保留原始测试输出。
- 评审表：`append_review({id, task, ev, reviewer_context, verdict, reason, ts})`。
- 进度表：`append_progress` 追加中文叙事；每段含时间与任务 ID、进展、中文状态、验证/评审结论及下一步。
- 可选地图：`set_meta('board', {...})`，不影响任务队列。
- 旧项目：`python -X utf8 "<技能目录>/scripts/convert_harness_json.py" "<项目绝对路径>"` 一次性整目录导入；旧文件保留作只读备份，运行时不读。禁止让 agent 一条条 INSERT。
- `board/`：可视化看板是独立目录，不随技能安装；见下文「可视化看板」。

## 可视化看板（独立项目，不随技能安装）

看板界面文案必须直接硬编码为中文，不做运行时翻译、不做双语界面、不读取 `board.i18n.json`，也不承担任务内容翻译。看板只读取 `harness.db` snapshot 里已写好的中文字段并进行展示、筛选、分组和状态可视化。缺少中文任务数据时应明确报错或标记契约失败，不能回退显示英文，也不为旧数据提供兼容翻译。数据不合规时显示契约错误；修复 DB 后刷新，不由看板改写任务。


看板不在本技能包内，安装脚本也不会拷贝它。仓库独立目录 `board/` 提供只读 HTTP 页，轮询项目任务目录并自动刷新。

```powershell
powershell -ExecutionPolicy Bypass -File .\board\start.ps1
powershell -ExecutionPolicy Bypass -File .\board\start.ps1 -ProjectDir "<项目绝对路径>"
```

不传 `-ProjectDir` 时，页面「载入任务」可指定 harness 目录，或从本机 Codex 会话（`~/.codex/sessions` 的 `cwd`）选择工作目录。

Windows 乱码：用 `board\start.ps1` / `board\start.bat`（已设 UTF-8 / `chcp 65001` / `python -X utf8`），不要自己再开一套 `python -m http.server`。

技能只读写 `.harness/harness.db`。Agent 用 `HarnessDB` 的 `upsert_task` / `append_evidence` / `append_review` / `append_progress` / `set_meta`，不要手写 SQL，不要逐条从旧 JSON 搬。不要把看板 HTML 拷进 `.harness/`，不要为了刷新看板再跑技能脚本。

## 修改任务定义

用 `upsert_task` 更新任务，`set_meta('rev', n+1)`，并 `append_progress` 原因。受影响的 `passed` 任务必须标记 `regressed` 回到 `active`。不要删除历史 evidence/review；它们是审计链的一部分。

## 项目地图（人看的「我现在站在哪」）

任务队列回答「下一张卡是什么」，**回答不了**「现在做到哪了、对不对、下一步为什么是它」。
长期项目里真正会失控的是**人的心智模型**，不是代码质量（那是门禁在管）。所以看板支持一份**可选**的
`meta.board`（可选地图，不是任务真相源）：有就把 `where` / `next` 显示在「下一步看板」里，没有就只显示可推进的下一张卡，**不影响任务队列**。

看板操作面（给人看的优先级，不是状态枚举顺序）：

1. 默认打开 **任务列表**，其次为下一步看板 / 进度时间线 / 进度日志。
2. 左侧筛选从上到下：**全部任务 → 已阻塞 → 待评审 → 进行中 → 可推进**。卡片和侧栏颜色跟状态机一致。
3. **当前行**钉在左侧状态机下方；**最近证据与评审**用抽屉，不占主视线。

**它不是又一份文档** —— 它是**看板上的一个视图**，随看板一起刷新，人一眼看到"我现在在哪"。

契约（全部字段可选，缺的区块不显示）：

```json
{
  "updated": "2026-09-11",
  "where": "一句话：现在站在哪（含最容易误解的地方）",
  "capabilities": [
    { "name": "登录", "state": "usable|partial|shell|missing", "note": "判断依据" }
  ],
  "tests": {
    "total": 949, "unit": "项后端测试", "skipped": 30, "note": "怎么跑的",
    "areas":  [ { "name": "backend/tests/api", "count": "67 个文件", "what": "测的是什么" } ],
    "limits": [ "30 条 skip 全是真机不可达 ⇒ 现在没有任何一条真实数据库断言" ]
  },
  "why":  [ { "what": "路由注册表", "problem": "它解决的问题", "evidence": "依据（门禁第 N 条 / commit）" } ],
  "next": [ { "task": "B3", "why": "为什么是它而不是别的", "see": "做完你会看到什么" } ]
}
```

**写它的纪律**（与项目里的证据纪律一致）：

- `state` 必须**有依据**（e2e 覆盖 / 端点实测 / 文件行号），不许凭印象写「能用」；
- `tests.limits` **必须写**：测试通过 ≠ 测对了，把「哪些没测到」明写出来；
- `why[].problem` 是给**不懂技术的人**看的：说清"没有它会发生什么"，不写技术名词；
- `next` 若为空，说明**没有可推进任务** —— 那就该由人决策，而不是让 agent 自己找活干。

**状态词典钉在左侧按钮上**：每项一行人话。其中
`evidence_ready`（待评审）最容易误读 —— 它是**"做完了但还没被独立评审确认"**，既不是完成、也不是没开始；独立评审通过才是 `passed`。

## 完成标准

只有同时满足以下条件才报告完成：

- 所有任务（含束内任务）为 `passed`；
- 每个 `passed` 任务均有对应 evidence 和独立 `pass` review；
- 最新验证可重放，退出码为 0；
- 没有未记录的阻塞、越界修改或未备份破坏性动作；
- 输出最后一条 `HARNESS_STATUS`，其中 `EXIT_SIGNAL: true`。
