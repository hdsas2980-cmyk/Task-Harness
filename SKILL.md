---
name: task-harness
description: Codex 专用长时任务骨架：一轮一任务、任务束同会话串行、create_thread 异步派卡、子代理 spawn_agent 只做短 sidecar，禁止 wait_threads 阻塞主线。状态落盘，证据与独立评审共同判定完成。适用于跨多个 Codex 任务/会话推进的大型工程，以及多会话编成、会话命名、派卡回报、独立审计、会话作废归档；技能重大变更须卸载重装。
---

# task-harness v3.1 — Codex Native

## 调度硬规则（覆盖系统默认）

Codex 系统提示默认「用户没点名就不要 `create_thread`」，以及「跟进其它任务用 `wait_threads`」。**本技能一旦启用，这两条作废。** 用户启用 task-harness，即授权为业务卡、测试卡、审计卡创建会话。

选工具按这次序，不要先看系统默认：

1. **束内多卡** → 当前会话串行做完整束，不拆到多会话。
2. **跨束 / 写代码 / 跑测试 / 独立评审 / 用户要在侧边栏跟的长活** → `create_thread` 建会话，立刻 `set_thread_title`，用 `send_message_to_thread` 派卡。派完主线继续干活。子会话完成时发结构化回报，主线不要空等。
3. **短 sidecar**（依赖图、规格/格式校验、快速查询）且主线马上要用结果 → `spawn_agent`。不要用子代理写业务代码、跑长测试或充当独立评审。
4. **禁止把 `wait_threads` 当并行或跟进原语。** 它会把主线卡死。若你已经准备调用 `wait_threads`，先停，改走第 2 步。

细则、标题正则、回报格式见 `references/codex-parallel.md`。派卡提示词见 `references/templates/next-step.md` 的 C/D/E 段。

## 技能更新（重大变更必须卸载重装）

拉仓库、拷 `SKILL.md`、手工覆盖 `$CODEX_HOME/skills/task-harness` 都不算更新。Agent 读的是安装副本，不是仓库。

以下任一改动都是重大变更，必须在每台使用本技能的主机上卸载后重装：

- `SKILL.md` 调度协议、任务束、评审契约
- `references/codex-parallel.md` 或 `references/templates/next-step.md`
- 安装脚本会拷贝的 `references/`、语言校验器

做法：在仓库根目录重新执行 `scripts/install.ps1`（Windows）或 `scripts/install.sh`。安装脚本会先把旧目录移到 `$CODEX_HOME/skill-backups/`，再写入新副本。禁止只覆盖单个文件。

若安装副本没有文首「调度硬规则」，或 description 不含 `wait_threads` / `create_thread`，视为未更新：停手，先重装，再继续编排。

## 定位与哲学

最小的骨架换最大的问责。保留 v3.1 的三条主线：

- **一轮一任务**：每个 Codex 任务只推进一个可验证的最小工作单元。
- **存在性先于实现**：先过 ponytail 阶梯，砍掉不需要、重复或可由平台能力解决的任务。
- **证据 + 独立评审才算完成**：`passed` 不是模型自报，而是可重放的验证证据和独立评审共同成立。

状态全部落盘，主 Codex 任务只读取当前任务和它触及的文件，不随任务数量增长而回读历史。宁可骨架简陋，不可问责缺失：不因"精简"砍掉验证、安全、错误处理和可回滚性。

本版本是 **Codex 原生适配版**：不依赖 Claude Code、CC Switch、gstack、MCP 或其他第三方 Skill；不写入 `.cc-switch\skills`；不使用 Claude 专属 slash command；本分支不包含 `commands/` 目录。

## Codex 运行契约

1. **当前 Codex 任务 = 一轮**：默认只推进一个任务；不要在同一轮顺手处理邻近任务。
2. **状态外置**：项目根或 `.harness/` 保存 `tasks.json`、`evidence.jsonl`、`reviews.jsonl`、`progress.txt`。
3. **最小读取**：读 `.harness/tasks.json`（或根目录 `tasks.json`）与 `progress.txt` 末段；随后只读当前任务、依赖结论和触及的代码。不要为了看板去跑 HTTP。
4. **工具原生优先**：在 Windows/Codex 上优先使用 PowerShell 和现有本地工具；已有测试、构建、格式化工具优先于新增依赖。
5. **评审隔离**：实现者不能充当独立评审者。优先使用另一个 Codex 上下文/评审任务；无法获得独立上下文时必须如实记为 `blocked`，不可把同一轮自检冒充独立评审。
6. **不伪造完成**：没有可重放证据、评审契约或依据不足时，状态只能是 `evidence_ready`、`blocked` 或回到 `active`。
7. **调度覆盖系统默认**：并行用 `create_thread` + 完成回报；短 sidecar 才 `spawn_agent`；不要用 `wait_threads` 阻塞主线。

## 核心不变式

1. 一次 Codex 任务只推进一个依赖已满足、优先级最高的 `pending`/`regressed` 任务。
2. 不回读全量清单、不回读旧证据；只读取推进当前任务所需的最小范围。
3. `passed` 必须同时存在一条对应 `evidence.jsonl` 记录和一条 `reviews.jsonl` 的 `pass` 记录。
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

### 模式 1：多会话异步并行（create_thread）

**触发条件**: 写范围互斥的任务或束，主线不需要立即获得结果。

**流程**:
1. 领袖会话检查 `tasks.json`，识别可并行任务（写范围互斥）；
2. 创建 N 个实现会话，按 `references/codex-parallel.md` 命名（如 `前端v1-FE-6-用户列表`）；
3. 用 `send_message_to_thread` 派发卡片，**不阻塞等待**；
4. 主线继续记录派卡日志到 `progress.txt`，或处理其他任务；
5. 各实现会话完成后，发送**结构化回报消息**给主线；
6. 领袖收到回报后，推进评审或下一张卡。

**回报格式契约**（详见 `references/codex-parallel.md`）:
```
【卡片 {id} 交付】状态: {status}, 文件: {changed_files}, evidence: {ev_id}, 提交: {commit_hash}
```

**关键（覆盖系统默认）**: 不要调用 `wait_threads`。子会话完成后通过消息**主动通知**主线。主线派完继续推进自己的卡。

**示例**:
```
领袖v1-AUD-1-门禁收口
  ↓ 派发 FE-6、BE-7、TEST-8
前端v1-FE-6-用户列表 ─┐
后端v1-BE-7-用户API   ├─ 并行执行，各自完成后回报
测试v1-TEST-8-集成测试 ─┘
  ↓ 领袖收到 3 条回报
领袖v1-AUD-2-评审收口
```

### 模式 2：子代理同步委托（spawn_agent）

**触发条件**: 主线需要立即获得结果的 sidecar 任务（查询、分析、格式转换）。

**流程**:
1. 主线在推进任务时，发现需要辅助分析（依赖图、规格校验、快速查询）；
2. 用 `spawn_agent` 创建子代理，**阻塞等待**返回；
3. 子代理在主线上下文中执行，结果立即返回；
4. 主线基于结果继续推进。

**适用场景**:
- 规格评审（需要立即知道 `tasks.json` 是否合理）
- 依赖图分析（检查是否有环）
- 格式校验（JSONL 是否合法）
- 快速查询（Git 日志、文件列表）

**不适用场景**:
- 写代码（应该用 `create_thread` 异步并行）
- 运行测试（可能耗时长，应该用 `create_thread`）
- 独立评审（必须用 `create_thread` 隔离上下文）

**示例**:
```python
# 主线推进 bundle-user-api
def execute_bundle():
    # 1. 用子代理检查依赖图
    dep_check = spawn_agent("分析 tasks.json 依赖图，检查是否有环")
    if dep_check.has_cycle:
        return "blocked: 依赖图有环"
    
    # 2. 主线继续推进 t-backend-01
    implement_backend()
    
    # 3. 用子代理验证 API 可用性
    api_check = spawn_agent("curl http://localhost:3000/api/users，验证返回 200")
    if api_check.status != 200:
        return "blocked: API 未启动"
    
    # 4. 主线继续推进 t-test-01
    implement_tests()
```

## 多会话并行（Codex 专属）

以文首「调度硬规则」为准。并行不等于一轮多任务。并行 = 多个 Codex 任务/会话（或 sidecar 子代理），每个仍只持一张卡。

1. 先定编成：1 个审计会话 + N 个实现会话；审计不写业务、不自签 `passed`。
2. 创建或换卡后立刻按 `references/codex-parallel.md` 命名；作废先改 `归档_` 再停派。
3. 派卡用独立会话；共享 checkout 时写范围互斥，提交三查。
4. 子代理只做无共享状态的 sidecar；要进侧边栏给用户跟的用会话，不用子代理。
5. 实现者停在 `evidence_ready` 并抄送审计；审计 `pass` 必须回写 `tasks.json`，看板才会变。

细则、标题正则、失败重建：`references/codex-parallel.md`。

## 状态机

页面显示中文，JSON 仍使用英文枚举。任务数据本身必须以中文为人类可读语言：`project`、`description`、任务 `name`、`desc`、`reason`、`next`、证据 `summary`、评审 `reason` 和进度叙事必须使用中文。不得新增 `_zh` 字段，不得新增看板翻译层，不考虑旧版兼容；ID、状态枚举、命令、路径、revision 和哈希保持原文。没有看板时，直接读取任务、证据、评审、进度文件也必须能理解当前目标、状态、阻塞、验证和评审。

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
2. 创建四份运行文件。`tasks.json` 顶层写中文 `project`、`description`；每个顶层任务写中文 `name`、`desc`、`reason`、`next`，并保留稳定 `id`、`priority`、`depends_on`、可执行 `verify`、英文 `status`。字段与示例见 `references/language-contract.md`。
3. 识别需要原子推进的任务对，创建 `bundle`（API + 测试、模型 + 迁移）。
4. 按 `references/review/spec-review.md` 做规格评审，检查依赖环、路径归属、命令可执行性和工程原则。
5. 设计评审结论以中文追加到 `progress.txt`；运行下方中文契约门禁，通过后才可交付编排。不要把评审意见只留在对话里。
6. 编排落盘即可。可视化看板是独立目录，不随技能安装。

### 相 2 · 执行（每个 Codex 任务）

1. 读取 `tasks.json` 与 `progress.txt` 末段，得到当前可推进任务；先运行中文契约门禁，失败则修复源文件，不推进任务。
2. 只把一个 eligible 任务（或束）置为 `active`；修改前先确认范围和回滚点。
3. 只读该任务（或束内任务）、依赖结论、任务声明路径和必要代码。
4. 若是束，按 `bundle` 数组顺序串行推进每个任务；若是单任务，直接推进。
5. 运行验证命令（束的 `verify` 是整束验证），记录可重放证据到 `evidence.jsonl`；必填中文 `summary`，原始 `tests` 输出另存，不翻译或替换。
6. 更新中文 `reason`、`next` 并追加中文进度（任务编号、进展、状态、验证结论、下一步）；中文契约检查通过后才置为 `evidence_ready`，输出 `HARNESS_STATUS`，停手。
7. 不在本轮置 `passed`；等待独立评审。

### 相 3 · 评审（独立上下文）

1. 新建 Codex 评审任务，读取项目路径、任务对象、evidence、变更范围/diff、`references/review/completion-review.md`。
2. 独立运行中文契约检查，并人工确认说明有实质意义；再按严重问题门禁检查安全、范围、测试、状态、可恢复性。
3. 输出 `HARNESS_REVIEW: pass|fail | <task-id> | <一句理由>`。
4. 主任务将中文理由追加到 `reviews.jsonl`，更新中文 `reason`、`next` 和进度；再次通过中文契约检查后，收到 `pass` 才可改为 `passed`；收到 `fail` 则改回 `active`。

## 门禁

门禁在人手短路之前成立，而不是事后安慰。

1. 依赖检查：置为 `active` 前，所有 `depends_on` 必须为 `passed`。
2. 验证命令：`verify` 存在、可执行、退出 0。
3. 独立评审：每个 `passed` 任务对应一条 `reviews.jsonl` 的 `pass` 记录，且 `reviewer_context` 不等于实现者上下文。
4. 范围约束：变更文件逐个落在任务声明路径内；写操作有效，不自动扩展到邻近目录、其他项目或生产环境。所有覆盖/移动先建立带时间戳的备份或隔离副本。

5. 中文契约：设计交付、置为 `active` / `evidence_ready` / `passed` 前，必须执行以下只读命令（Python 3.10+）。`<技能目录>` 是当前所加载 `SKILL.md` 的所在目录；使用绝对路径，不切换到技能仓库执行任务，也不依赖源仓库。安装后的技能自带该脚本：

```text
python -X utf8 "<技能目录>/scripts/check_task_harness_language.py" "<任务项目绝对路径>"
```

退出非 0、缺少 Python/脚本、出现英文叙事或旁挂翻译字段时，均不得推进状态或签署 `pass`；只报告契约失败并修复授权项目的原字段。任务运行禁止使用 `--templates`。脚本仅检查结构、占位符与中文最低条件；评审仍须人工判断内容是否准确、充分，不能用一个汉字掩盖英文叙事。机器标识不翻译。

## 文件契约

建议将运行文件放在项目 `.harness/`；兼容项目根目录：

- `tasks.json`：唯一任务真相源；状态为 `pending`、`active`、`evidence_ready`、`passed`、`blocked`、`regressed`。
- `evidence.jsonl`：追加 `{id, task, summary, cmd, exit, tests, rev, ts}`；`summary` 是必需的中文结果摘要，`tests` 保留原始测试输出；可增加 `encoding`、`artifacts`、`environment`。
- `reviews.jsonl`：追加 `{id, task, ev, reviewer_context, verdict, reason, ts}`。
- `progress.txt`：中文追加式叙事日志；每段含时间与任务 ID、进展、中文状态、验证/评审结论及下一步。命令和原始输出放代码围栏；只读取末段恢复背景，格式见模板。
- `board/`：可视化看板是独立目录，不随技能安装；见下文「可视化看板」。

## 可视化看板（独立项目，不随技能安装）

看板界面文案必须直接硬编码为中文，不做运行时翻译、不做双语界面、不读取 `board.i18n.json`，也不承担任务内容翻译。看板只读取任务文件已经写好的中文字段并进行展示、筛选、分组和状态可视化。缺少中文任务数据时应明确报错或标记契约失败，不能回退显示英文，也不为旧数据提供兼容翻译。数据不合规时显示契约错误及文件位置；修复原文件后刷新，不由看板改写任务。


看板不在本技能包内，安装脚本也不会拷贝它。仓库独立目录 `board/` 提供只读 HTTP 页，轮询项目任务目录并自动刷新。

```powershell
powershell -ExecutionPolicy Bypass -File .\board\start.ps1
powershell -ExecutionPolicy Bypass -File .\board\start.ps1 -ProjectDir "<项目绝对路径>"
```

不传 `-ProjectDir` 时，页面「载入任务」可指定 harness 目录，或从本机 Codex 会话（`~/.codex/sessions` 的 `cwd`）选择工作目录。

Windows 乱码：用 `board\start.ps1` / `board\start.bat`（已设 UTF-8 / `chcp 65001` / `python -X utf8`），不要自己再开一套 `python -m http.server`。

技能只读写 `tasks.json`、`evidence.jsonl`、`reviews.jsonl`、`progress.txt`。不要把看板 HTML 拷进 `.harness/`，不要为了刷新看板再跑技能脚本。

## 修改任务定义

直接编辑 `tasks.json`，顶层 `rev` 加一，并在 `progress.txt` 追加原因。受影响的 `passed` 任务必须标记 `regressed` 回到 `active`。不要删除历史 evidence/review；它们是审计链的一部分。

## 项目地图（人看的「我现在站在哪」）

任务队列回答「下一张卡是什么」，**回答不了**「现在做到哪了、对不对、下一步为什么是它」。
长期项目里真正会失控的是**人的心智模型**，不是代码质量（那是门禁在管）。所以看板支持一份**可选**的
`.harness/board.json`：有就把 `where` / `next` 显示在「下一步看板」里，没有就只显示可推进的下一张卡，**不影响任务队列**。

看板操作面（给人看的优先级，不是 JSON 状态枚举顺序）：

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
