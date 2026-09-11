---
name: task-harness
description: 长时运行任务的最小骨架。一轮一任务、状态落盘、证据加独立评审判定完成，主会话上下文不随任务数增长。这是宿主无关的核心协议；安装到具体 ADE 请用对应分支。
---

# task-harness v3.1 — Core

## 定位

最小的骨架换最大的问责。本文件是**宿主无关的核心协议**，不写入任何 IDE 目录，不含斜杠命令或子智能体定义。

- **一轮一任务**：每个工作轮次只推进一个可验证的最小单元。
- **存在性先于实现**：先过 ponytail 阶梯，砍掉伪任务、重复实现和不必要依赖。
- **证据 + 独立评审才算完成**：`passed` 不是模型自报，必须同时有可重放证据和独立 `pass` 评审。

状态全部落盘。主会话只读取当前任务和它触及的文件，不随任务数量回读历史。宁可骨架简陋，不可问责缺失：不因「精简」砍掉验证、安全、错误处理和可回滚性。

要装进 Claude Code / Codex / TRAE / WorkBuddy / DSH，请检出对应宿主分支。分支表见仓库根 `BRANCHES.md`。

## 核心不变式

1. 一次工作轮次只推进一个依赖已满足、优先级最高的 `pending` / `regressed` 任务。
2. 只加载当前任务加它触及的代码；不回读全量任务清单，不回读旧证据。
3. `passed` 必须同时持有一条 `evidence.jsonl` 记录和一条 `reviews.jsonl` 的 `pass` 记录。
4. 实现者不等于评审者。评审在独立上下文完成；没有独立上下文就标 `blocked`，不得把本轮自检写成独立评审。
5. 依据不足时如实标 `blocked`，绝不伪造完成。
6. 已通过任务受依赖、接口或环境变化影响时，标 `regressed` 并回到 `active`。

## 状态机

页面或叙述可用中文，JSON 枚举保持英文。

```text
pending（待处理） → active（进行中） → evidence_ready（待独立评审） → passed（已通过）
                        │              │
                        └─(评审 fail)→ active（带新证据重试）
   任意态 → blocked（已阻塞，记录 reason）
   passed → regressed（需回归，依赖变更导致失效，回 active）
```

## 三相流程

### 相 1 · 设计（一次性）

1. 对每个候选任务过 ponytail 阶梯，从源头砍掉伪任务。
2. 起草 `tasks.json`：稳定 `id`、`priority`、一句话 `desc`、`depends_on`、可执行 `verify`、`status`。
3. 按 `references/review/spec-review.md` 做规格独立评审（依赖环、路径归属、命令可执行性、工程原则）。
4. 结论追加 `progress.txt`，不要把评审意见只留在对话里。
5. 若使用看板：编排落盘后再跑一次初始化，确认页面读的是当前项目文件。

### 相 2 · 执行（每轮一个任务）

1. 运行初始化，只读紧凑状态（进度、待评审、阻塞、下一个 eligible）。
2. 把唯一一个 eligible 任务置为 `active`。修改前确认范围和回滚点。
3. 只读该任务及其触及的代码，按最小改动实现。
4. 跑 `verify`，追加一条 `evidence.jsonl`，置 `evidence_ready`。
5. 输出执行状态块后停止本轮，不要顺手做下一个任务。

### 相 3 · 评审（独立上下文）

1. 独立上下文只读取任务定义、对应 evidence、变更范围和必要源文件；禁止借用实现对话里未落盘的结论。
2. 按 `references/review/completion-review.md` 评审。
3. 评审结尾必须输出恰好一行：

   ```text
   HARNESS_REVIEW: pass|fail | <task-id> | <一句理由>
   ```

4. `pass` → 追加 `reviews.jsonl` 并将状态改为 `passed`；`fail` → 回 `active` 并带新证据重试。

宿主如何打开独立上下文（新会话、子智能体、斜杠命令）由 ADE 分支定义，本文件不绑定。

## ponytail 阶梯

1. 这个任务/代码需要存在吗？（YAGNI）
2. 项目中已有可复用实现吗？
3. 标准库/语言原生能解决吗？
4. 平台或框架原生能力能解决吗？
5. 已安装依赖能解决吗？
6. 一行或一个配置能解决吗？
7. 能跑通的最小实现是什么？

绝不对「理解代码」偷懒；绝不砍验证、安全、错误处理和无障碍要求。

## 上下文预算

- 启动时只读初始化摘要，不把全量任务正文塞进上下文。
- 任务选择只依赖 `tasks.json` 的必要字段；旧 evidence/review 只按当前 `task` 过滤读取。
- 大型日志、构建产物、截图、抓包和报告放 `.harness/artifacts/`，任务里记录路径，不内联全文。
- 需要跨轮传递的信息写入 `progress.txt` 最后一段；不要依赖聊天历史。
- 每轮结束前写清「已做 / 证据 / 下一步 / 阻塞」，让下一轮可从磁盘恢复。

## 破坏性命令护栏

执行下列动作前，必须先说明影响、目标绝对路径、可逆性，并取得本轮用户明确授权；验证或评审不得擅自执行：

- 递归删除、批量移动、`git clean`、覆盖未备份文件；
- `DROP TABLE`、`TRUNCATE`、无条件数据删除/更新；
- `git reset --hard`、强制推送、改写已发布历史；
- 部署、服务重启、权限/DNS/网关变更；
- 未限制目录范围的递归搜索。

授权只对当前明确动作有效。所有覆盖/移动先建立带时间戳的备份或隔离副本。

## 文件契约

建议放在项目 `.harness/`；兼容项目根目录的旧布局：

- `tasks.json`：唯一任务真相源。状态为 `pending`、`active`、`evidence_ready`、`passed`、`blocked`、`regressed`。
- `evidence.jsonl`：追加 `{id, task, cmd, exit, tests, rev, ts}`，可增加 `artifacts`、`environment`。
- `reviews.jsonl`：追加 `{id, task, ev, reviewer_context, verdict, ts}`。
- `progress.txt`：追加式叙事日志，只读取最后一段恢复背景。
- `init.py`：紧凑状态，不改任务文件。
- `init.ps1` / `init.sh`：默认启动 `127.0.0.1` 只读看板；`--status-only` 只打印紧凑状态。
- `serve_dashboard.py` + `task-harness.html`：看板 SPA。服务只读，不写任务真相源。

## 初始化

依赖 Python 3（仅标准库）。在项目目录调用，不要把工作目录切到本仓库。

```powershell
python <repo>/references/templates/init.py --project <项目绝对路径>
# 看板（复制 SPA 到项目 .harness/，绑定 127.0.0.1:8765-8799）：
powershell -NoProfile -File <repo>/references/templates/init.ps1 -ProjectDir <项目绝对路径>
```

```bash
python3 <repo>/references/templates/init.py --project "<项目绝对路径>"
bash <repo>/references/templates/init.sh --status-only "<项目绝对路径>"
bash <repo>/references/templates/init.sh "<项目绝对路径>"
```

输入为项目根或 `.harness`。根目录已有 `tasks.json` 时原位读取，不迁移。无任务时仍可复制空白看板并启动服务，不创建示例任务。默认不自动打开浏览器；`-Open` / `--open` 才打开。自动化用 `-NoOpen` / `--no-open`。

看板只暴露 `task-harness.html` 与 `tasks.json` / `evidence.jsonl` / `reviews.jsonl` / `progress.txt`。端口按项目 source 独占，不复用其他项目的地址。必须通过 `http://127.0.0.1` 打开；`file://` 读不到实时任务。

页面状态中文，JSON 枚举英文。已通过只表示任务声明；缺少关联证据及独立评审必须显示门禁缺口。

## 执行状态块

相 2 结尾输出：

```text
HARNESS_STATUS: <task-id> <IN_PROGRESS|COMPLETE|BLOCKED>
PROGRESS: <passed>/<total>
EXIT_SIGNAL: <false|true>
```

全部任务 `passed` 且门禁成立时 `EXIT_SIGNAL: true`。看板打印的 `EXIT_SIGNAL` 只反映任务声明，完成门禁仍须独立评审确认。

## 修改任务定义

直接编辑 `tasks.json`，顶层 `rev` 加一，并在 `progress.txt` 追加原因。受影响的 `passed` 任务标 `regressed` 回到 `active`。不要删除历史 evidence/review。

## 完成标准

只有同时满足以下条件才报告完成：

- 所有任务为 `passed`；
- 每个 `passed` 任务均有对应 evidence 和独立 `pass` review；
- 最新验证可重放，退出码为 0；
- 没有未记录的阻塞、越界修改或未备份破坏性动作；
- 输出最后一条 `HARNESS_STATUS`，其中 `EXIT_SIGNAL: true`。
