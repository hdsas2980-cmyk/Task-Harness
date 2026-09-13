# Codex 适配说明

## 1. 一轮边界

把每个 Codex task/thread 当作一个可恢复的工作轮次：读取磁盘状态，完成一个任务，落证据，输出状态块，然后停止。不要依赖上一轮的聊天记录，也不要在一轮里提前实现下一个任务。

## 2. 评审隔离

实现完成后，把以下最小材料交给独立 Codex 评审上下文：

- 项目绝对路径；
- `harness.db` 中当前任务对象；
- 当前任务对应的 evidence 记录；
- 变更文件列表或 diff；
- `references/review/completion-review.md`。

评审上下文只读这些材料和必要源文件，最后只输出：

```text
HARNESS_REVIEW: pass|fail | <task-id> | <一句理由>
```

若当前环境没有可用的独立评审上下文，不能自行把“实现后再看一眼”写成独立 review；应记录 `blocked` 并等待外部评审。

## 3. 工具选择

- Windows：优先 PowerShell；路径使用绝对路径并在破坏性动作前 `Resolve-Path`；
- Git Bash/Linux/macOS：使用 POSIX 工具；可视化看板见独立目录 `board/`；
- 复用项目已有测试/构建命令，不为 Harness 引入运行时依赖；
- 大输出写入 `.harness/artifacts/`，证据只记录摘要和路径。

## 4. 记录格式

推荐 evidence：

```json
{"id":"ev-01","task":"t-01","cmd":"npm test -- --runInBand","exit":0,"tests":"42 passed","rev":"abc1234","artifacts":[],"environment":"Windows + PowerShell","ts":"2026-08-31T12:00:00+08:00"}
```

推荐 review：

```json
{"id":"rv-01","task":"t-01","ev":"ev-01","reviewer_context":"codex-independent-task","verdict":"pass","reason":"范围、验证和回归检查均通过","ts":"2026-08-31T12:05:00+08:00"}
```

## 5. Codex 输出契约

执行轮结束时只要让下一轮能恢复，至少包含：

```text
HARNESS_STATUS: <task-id> <IN_PROGRESS|COMPLETE|BLOCKED>
PROGRESS: <passed>/<total>
EXIT_SIGNAL: <false|true>
```

评审结束时必须包含唯一契约行：

```text
HARNESS_REVIEW: pass|fail | <task-id> | <一句理由>
```
