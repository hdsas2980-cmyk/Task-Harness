# SQLite 存储契约

唯一真相源：`.harness/harness.db`。**不兼容** JSON 活路径。

- Agent 只读写此库。没有 DB = 未初始化，不是回退 `tasks.json` / `evidence.jsonl` / `reviews.jsonl` / `progress.txt`。
- 旧项目跑一次转换脚本整目录导入；旧文件保留作只读备份，运行时不读。
- 禁止手写 SQL，禁止把旧 JSON 一条条 INSERT。

## Agent API

```python
from harness_db import HarnessDB

with HarnessDB.open(project, create=True) as db:
    db.set_meta("project", "中文项目名")
    db.set_meta("description", "中文说明")
    db.set_meta("rev", 1)
    db.upsert_task({"id": "t-01", "name": "任务名", "desc": "描述", "reason": "暂无阻塞", "next": "开始实现", "status": "pending", "depends_on": [], "verify": "pytest -q", "priority": 1})
    db.append_evidence({"id": "ev-01", "task": "t-01", "summary": "测试通过", "cmd": "pytest -q", "exit": 0})
    db.append_review({"id": "rv-01", "task": "t-01", "ev": "ev-01", "verdict": "pass", "reason": "独立评审通过", "reviewer_context": "reviewer"})
    db.append_progress("## 2026-09-13 | t-01 | 执行\n- 进展：已验证")
    snapshot = db.read_snapshot()
```

- `HarnessDB.open(project, create=True)`：新项目建 `.harness/harness.db`。
- `HarnessDB.open(project, create=False)`：只读；没有 DB 抬 `FileNotFoundError`。
- `upsert_task` / `append_evidence` / `append_review` / `append_progress` / `set_meta`：日常写库。
- `read_snapshot()`：返回 `schema_version`、`storage`、`meta`、`tasks`、`evidence`、`reviews`、`progress`、`counts`、`revision`。
- `passed` 仍要 evidence + 独立 review，只是存在 DB 表里。

## 一次性转换

```text
python -X utf8 "<技能目录>/scripts/convert_harness_json.py" "<项目绝对路径>"
```

`import_legacy()` / 转换脚本一次读入旧四文件，幂等，不删旧文件。这不是兼容层。
