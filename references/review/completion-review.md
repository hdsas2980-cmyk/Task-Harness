<!-- 方法论改编自 gstack (github.com/garrytan/gstack, MIT © 2026 Garry Tan)。已剥离 gstack 运行时，仅保留评审内核。 -->

# completion-review.md — 完成评审（相 3）

对一个已实现、已跑 verify、状态为 `evidence_ready` 的任务做独立完成评审，产出 pass/fail。
本文件自包含、零外部依赖；装了 gstack 时可回退调 `gstack/review` 取更深维度（见文末兜底）。

## 铁律
- 实现者不评审自己；评审在独立上下文进行（不复用实现时的对话与假设）。
- 只标真问题，能力覆盖不到就说"未验证"，不臆断"应该没事"。任何"看起来没问题"必须给出证据行（file:line）或降级为未验证。

## 评审对象怎么拿
- 代码面：当前任务在 `tasks.json` 里声明触及的文件/路径。
- 证据面：`evidence.jsonl` 中该任务的记录（`cmd` / `exit` / `tests` / `rev`）。
- diff：git 可用时，用 `rev`（短哈希）看该任务提交的 diff；非 git 工作区 `rev=N/A` 时，直接读任务触及的文件本身。绝不硬依赖 git/PR/gh。

## 两趟评审（先读全部改动，再评）

### Pass 1 — CRITICAL（结构性问题，测试抓不到的）
- SQL 与数据安全：字符串拼接进 SQL（即便已 to_i/to_f）、check-then-set 该原子化却没有、绕过校验直写库。
- LLM 信任边界：LLM 产出的值（email/URL/结构）未做格式/类型/allowlist 校验就落库或外发（注入/SSRF）。
- 条件副作用：某条件分支漏了另一分支该有的副作用；日志声称做了某动作但实际被跳过；状态迁移只更新了一侧关联记录。
- 错误处理：catch/rescue 吞异常只打日志；可部分完成的操作在中途失败后留下不一致状态。
- Shell/命令注入：带变量插值的 `shell=True` / `os.system` / 拼接命令。

### Pass 2 — 范围与质量
- scope drift：是否恰好实现了任务声明的范围——不多做（镀金、越界改无关代码、引入未要求的抽象），也不少做（半实现的枚举/错误路径、缺边界处理）。这是最容易失分的一条。
- 安全：trust boundary 输入校验、authz 默认 deny 而非 allow、越权对象引用。
- 性能：循环内查询/N+1、新 WHERE/ORDER BY 列缺索引、O(n²) 可换 map 查表。
- 可维护性：死代码、魔法数、与改动矛盾的陈旧注释、diff 内 3 行以上的重复。
- 测试：证据里的 `tests` 是否真覆盖了新增分支的失败路径与边界值（0/空/null/单元素/最大值），而不只有 happy path；`exit` 是否为 0。
- 枚举完整性：新增枚举值/状态/类型时，grep 出所有消费同族值的位置并逐个确认新值被处理（需读改动之外的代码）。

## 不要标（抑制项）
- 无害且提升可读性的冗余；"加注释说明这个阈值"类建议；已在本次改动内解决的问题；输入受限时不会发生的边界；经验调校的阈值改动。

## 输出
先按 `[CRITICAL|范围|...] file:line — 问题一句话 → 建议一句话` 逐条列出真问题（无则写 "No issues"），最后固定输出恰好一行契约：

`HARNESS_REVIEW: pass|fail | <task-id> | <一句理由>`

判定：有任一未解决的 CRITICAL，或存在实质 scope drift（多做/少做偏离任务范围），或 `verify` 证据不足以支撑任务目标 → `fail`；否则 `pass`。

## 兜底（可选）
内联清单不足以判定（需 specialists 深度、复杂 diff）且本机装有 gstack 时，可回退调 `gstack/review` 取更深维度，其结论仍按上面的契约行回收；两者都不可用时如实标 `blocked`，绝不伪造 pass。
