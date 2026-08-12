#!/bin/bash
# task-harness v3 — 紧凑状态 + 单任务加载
# 用法: bash init.sh   （每轮执行开始时运行，只输出推进下一步所需的最小信息）
set -euo pipefail
cd "$(dirname "$0")"

# 探测可用的 Python 解释器（跨平台：Linux/macOS 用 python3，Windows 常为 python 或 py）
PY=""
for c in python3 python py; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c "import sys" >/dev/null 2>&1; then PY="$c"; break; fi
done
if [ -z "$PY" ]; then echo "未找到可用的 Python 解释器（python3/python/py）"; exit 1; fi

"$PY" - <<'PY'
import json, os, sys
try:
    sys.stdout.reconfigure(encoding="utf-8")  # Windows 控制台默认 gbk，强制 utf-8 防中文乱码
except Exception:
    pass

if not os.path.exists("tasks.json"):
    print("tasks.json 不存在，先进入相 1 设计。"); sys.exit(0)

d = json.load(open("tasks.json", encoding="utf-8"))
tasks = d["tasks"]
by_id = {t["id"]: t for t in tasks}
passed = [t for t in tasks if t["status"] == "passed"]

print(f"PROGRESS: {len(passed)}/{len(tasks)}  rev={d.get('rev',1)}")

# 待评审（相 3 的输入）
ready = [t for t in tasks if t["status"] == "evidence_ready"]
if ready:
    print("待评审 (按 references/review/completion-review.md 独立评审): " + ", ".join(t["id"] for t in ready))

# 阻塞项
blocked = [t for t in tasks if t["status"] == "blocked"]
if blocked:
    print("阻塞: " + ", ".join(t["id"] for t in blocked))

def deps_ok(t):
    return all(by_id.get(d, {}).get("status") == "passed" for d in t.get("depends_on", []))

# 下一个 eligible：依赖已满足、优先级最高的 pending/regressed
elig = [t for t in tasks if t["status"] in ("pending", "regressed") and deps_ok(t)]
elig.sort(key=lambda t: t["priority"])

if all(t["status"] == "passed" for t in tasks):
    print("EXIT_SIGNAL: true  — 全部任务已通过。")
elif elig:
    t = elig[0]
    print("\n下一个任务 (置 active):")
    print(f"  [{t['id']}] P{t['priority']}: {t['desc']}")
    print(f"  verify: {t['verify']}")
    if t.get("depends_on"):
        print(f"  depends_on: {', '.join(t['depends_on'])} (已满足)")
else:
    print("\n无 eligible 任务：均处于评审中/阻塞/依赖未满足。先处理上面列出的项。")
PY

echo ""
echo "提醒: 只推进这一个任务；完成后追加 evidence.jsonl 并置 evidence_ready；结尾输出 HARNESS_STATUS 块。"
