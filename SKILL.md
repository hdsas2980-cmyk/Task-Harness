---
name: task-harness
description: Codex 专用长时任务骨架：一轮一任务、状态落盘、证据与独立评审共同判定完成，严格控制上下文增长。适用于跨多个 Codex 任务/会话推进的大型工程，以及多会话编成、会话命名、多子代理并行、独立审计、派卡或会话作废归档。
---

# task-harness v3.1 — Codex Native

## 定位与哲学

最小的骨架换最大的问责。保留 v3.1 的三条主线：

- **一轮一任务**：每个 Codex 任务只推进一个可验证的最小工作单元。
- **存在性先于实现**：先过 ponytail 阶梯，砍掉不需要、重复或可由平台能力解决的任务。
- **证据 + 独立评审才算完成**：`passed` 不是模型自报，而是可重放的验证证据和独立评审共同成立。

状态全部落盘，主 Codex 任务只读取当前任务和它触及的文件，不随任务数量增长而回读历史。宁可骨架简陋，不可问责缺失：不因“精简”砍掉验证、安全、错误处理和可回滚性。

本版本是 **Codex 原生适配版**：不依赖 Claude Code、CC Switch、gstack、MCP 或其他第三方 Skill；不写入 `.cc-switch\skills`；不使用 Claude 专属 slash command；本分支不包含 `commands/` 目录。

## Codex 运行契约

1. **当前 Codex 任务 = 一轮**：默认只推进一个任务；不要在同一轮顺手处理邻近任务。
2. **状态外置**：项目根或 `.harness/` 保存 `tasks.json`、`evidence.jsonl`、`reviews.jsonl`、`progress.txt`。
3. **最小读取**：按下方“项目看板”运行初始化，读取紧凑摘要；随后只读当前任务、依赖结论和触及的代码。
4. **工具原生优先**：在 Windows/Codex 上优先使用 PowerShell 和现有本地工具；已有测试、构建、格式化工具优先于新增依赖。
5. **评审隔离**：实现者不能充当独立评审者。优先使用另一个 Codex 上下文/评审任务；无法获得独立上下文时必须如实记为 `blocked`，不可把同一轮自检冒充独立评审。
6. **不伪造完成**：没有可重放证据、评审契约或依据不足时，状态只能是 `evidence_ready`、`blocked` 或回到 `active`。

## 核心不变式

1. 一次 Codex 任务只推进一个依赖已满足、优先级最高的 `pending`/`regressed` 任务。
2. 不回读全量清单、不回读旧证据；只读取推进当前任务所需的最小范围。
3. `passed` 必须同时存在一条对应 `evidence.jsonl` 记录和一条 `reviews.jsonl` 的 `pass` 记录。
4. 评审必须在独立上下文完成，并记录评审上下文/来源。
5. 任何阻塞必须写入结构化 reason；不得用“看起来没问题”替代验证。
6. 已通过任务受依赖、接口或环境变化影响时，标记 `regressed` 并回到 `active`。


## 多会话并行（Codex 专属）

并行不等于一轮多任务。并行 = 多个 Codex 任务/会话（或 sidecar 子代理），每个仍只持一张卡。

1. 先定编成：1 个审计会话 + N 个实现会话；审计不写业务、不自签 `passed`。
2. 创建或换卡后立刻按 `references/codex-parallel.md` 命名；作废先改 `归档_` 再停派。
3. 派卡用独立会话；共享 checkout 时写范围互斥，提交三查。
4. 子代理只做无共享状态的 sidecar；要进侧边栏给用户跟的用会话，不用子代理。
5. 实现者停在 `evidence_ready` 并抄送审计；审计 `pass` 必须回写 `tasks.json`，看板才会变。

细则、标题正则、失败重建：`references/codex-parallel.md`。

## 状态机

页面显示中文，JSON 仍使用英文枚举。

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
2. 创建 `tasks.json`：稳定 `id`、`priority`、一句话 `desc`、`depends_on`、可执行 `verify`、`status`。
3. 按 `references/review/spec-review.md` 做规格评审，检查依赖环、路径归属、命令可执行性和工程原则。
4. 设计评审结论追加到 `progress.txt`；不要把评审意见只留在对话里。
5. 编排落盘后必须再次运行初始化：复制独立看板页面，并在 `http://127.0.0.1` 打开。

### 相 2 · 执行（每个 Codex 任务）

1. 运行初始化脚本，读取紧凑状态。
2. 只把一个 eligible 任务置为 `active`；修改前先确认范围和回滚点。
3. 只读该任务及其触及的代码，采用最小改动完成实现。
4. 执行任务的 `verify`；将命令、退出码、测试摘要、代码 revision 和时间追加到 `evidence.jsonl`。
5. 将任务置为 `evidence_ready`，重新初始化以确保看板服务在读当前文件（`-NoOpen` / `--no-open`），输出 `HARNESS_STATUS` 状态块，然后停止本轮。

### 相 3 · 评审（独立 Codex 上下文）

1. 独立评审上下文只读取任务定义、变更范围、对应 evidence 和必要代码；禁止借用实现上下文的未落盘结论。
2. 按 `references/review/completion-review.md` 核查功能、回归、安全、可维护性、验证质量和范围控制。
3. 评审结尾必须输出恰好一行：

   ```text
   HARNESS_REVIEW: pass|fail | <task-id> | <一句理由>
   ```

4. 将评审结果追加到 `reviews.jsonl`，`pass` 才能把 `evidence_ready` 改为 `passed`；`fail` 回到 `active` 并带新证据重试。看板只读 `tasks.json`，`pass` 必须当场回写，不能只在对话里宣布。

## ponytail 阶梯

1. 这个任务/代码需要存在吗？（YAGNI）
2. 项目中已有可复用实现吗？
3. 标准库/语言原生能解决吗？
4. 平台或框架原生能力能解决吗？
5. 已安装依赖能解决吗？
6. 一行或一个配置能解决吗？
7. 能跑通的最小实现是什么？

绝不对“理解代码”偷懒；绝不砍验证、安全、错误处理和无障碍要求。

## Codex 上下文预算规则

- 启动时只读初始化脚本的摘要，不把 100+ 任务全文塞进上下文。
- 任务选择只依赖 `tasks.json` 的必要字段；旧 evidence/review 只按当前 `task` 过滤读取。
- 大型日志、构建产物、截图、抓包和报告放 `.harness/artifacts/`，在任务里记录路径，不内联全文。
- 需要跨轮传递的信息写入 `progress.txt` 最后一段；不要依赖聊天历史。
- 每轮结束前清楚写出“已做 / 证据 / 下一步 / 阻塞”，让下一轮可从磁盘恢复。

## 破坏性命令护栏

执行下列动作前，必须先说明影响、目标绝对路径、可逆性，并取得本轮用户明确授权；验证或评审不得擅自执行：

- 递归删除、批量移动、`git clean`、覆盖未备份文件；
- `DROP TABLE`、`TRUNCATE`、无条件数据删除/更新；
- `git reset --hard`、强制推送、改写已发布历史；
- 部署、服务重启、权限/DNS/网关变更；
- 未限制目录范围的递归搜索。

授权只对当前明确动作有效，不自动扩展到邻近目录、其他项目或生产环境。所有覆盖/移动先建立带时间戳的备份或隔离副本。

## 文件契约

建议将运行文件放在项目 `.harness/`；兼容项目根目录：

- `tasks.json`：唯一任务真相源；状态为 `pending`、`active`、`evidence_ready`、`passed`、`blocked`、`regressed`。
- `evidence.jsonl`：追加 `{id, task, cmd, exit, tests, rev, ts}`，可增加 `artifacts`、`environment`。
- `reviews.jsonl`：追加 `{id, task, ev, reviewer_context, verdict, ts}`。
- `progress.txt`：追加式叙事日志，只读取最后一段恢复背景。
- `references/templates/init.ps1`：Windows/Codex 原生初始化脚本。
- `references/templates/init.sh`：Git Bash/Linux/macOS 兼容初始化脚本。
- `references/templates/task-harness.html` + `app.js`：技能携带的静态 Web 看板。
- `references/templates/serve_dashboard.py`：可选地把 SPA 挂到 `127.0.0.1`，不改任务真相源。

## 项目看板

依赖 Python 3（仅标准库）。使用技能绝对路径调用，不把工作目录切到 skill 目录。

- Windows：`& "<skill>/references/templates/init.ps1" -ProjectDir "<项目绝对路径>"`；兼容旧参数 `-HarnessDir`。
- Git Bash/Linux/macOS：`bash "<skill>/references/templates/init.sh" "<项目绝对路径>"`。
- 输入为项目根或 `.harness`；旧版根目录 `tasks.json` 保持原位读取，不迁移。初始无任务也复制空白看板并启动服务，不创建示例任务，不自动打开浏览器。
- 技能只携带一份静态 SPA。初始化把它复制到项目 `.harness/task-harness.html`（覆盖页面以便技能更新生效），然后在 `127.0.0.1:8765-8799` 启动只读 HTTP；输出 `DASHBOARD: http://127.0.0.1:<port>/task-harness.html`。
- 端口独占本项目 source：候选端口若已被其他项目的看板占用则自动换端口，绝不复用他人地址；复用已有服务前也会校验该端口返回的 `tasks.json` 与本项目一致。
- 编排完成首次自动用该 URL 打开；后续初始化复用已有端口。`-Open` / `--open` 重新打开；自动化测试用 `-NoOpen` / `--no-open`（仍启动/复用服务并打印 URL）。Codex 内用浏览器面板打开 `DASHBOARD` 的 http 地址，不要打开 `file://`。无界面环境只记录 URL。
- 更新任务、证据、评审、日志后重新初始化或在页面点「刷新任务」。服务只暴露看板和 `tasks.json` / `evidence.jsonl` / `reviews.jsonl` / `progress.txt`，绝不写任务真相源。
- 「载入任务」在浏览器中选择项目任务目录（`.harness` 或项目根）；「刷新任务」重读该目录。脚本初始化会先载入当前 HTTP 项目。没有独立桌面壳。
- 页面状态中文，JSON 枚举仍保持英文；已通过只表示任务声明，缺少关联证据及评审必须显示门禁缺口，不代替独立评审。

## 修改任务定义

直接编辑 `tasks.json`，顶层 `rev` 加一，并在 `progress.txt` 追加原因。受影响的 `passed` 任务必须标记 `regressed` 回到 `active`。不要删除历史 evidence/review；它们是审计链的一部分。

## 项目地图（人看的「我现在站在哪」）

任务队列回答「下一张卡是什么」，**回答不了**「现在做到哪了、对不对、下一步为什么是它」。
长期项目里真正会失控的是**人的心智模型**，不是代码质量（那是门禁在管）。所以看板支持一份**可选**的
`.harness/board.json`：有就把 `where` / `next` 显示在默认打开的「下一步看板」里，没有就只显示可推进的下一张卡，**不影响任务队列**。

看板操作面（给人看的优先级，不是 JSON 状态枚举顺序）：

1. 默认打开 **下一步看板**，其余为任务列表 / 进度时间线 / 进度日志。
2. 左侧筛选从上到下是人要先处理的顺序：**已阻塞 → 待评审 → 进行中 → 可推进 → 全部任务**。每项带一句人话，避免把「卡住了」理解成「马上开工」。
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

- 所有任务为 `passed`；
- 每个 `passed` 任务均有对应 evidence 和独立 `pass` review；
- 最新验证可重放，退出码为 0；
- 没有未记录的阻塞、越界修改或未备份破坏性动作；
- 输出最后一条 `HARNESS_STATUS`，其中 `EXIT_SIGNAL: true`。
