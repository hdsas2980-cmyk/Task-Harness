#!/usr/bin/env bash
# Codex Native task-harness v3.1 — 紧凑状态 + 单任务加载
set -euo pipefail
cd "$(dirname "$0")"
PY=""
for c in python3 python py; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c "import sys" >/dev/null 2>&1; then PY="$c"; break; fi
done
if [ -z "$PY" ]; then echo "未找到可用的 Python 解释器（python3/python/py）"; exit 1; fi
"$PY" - <<'PY'
#!/usr/bin/env python3
import json, os, sys
try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass
if not os.path.exists("tasks.json"):
    print("tasks.json 不存在，先进入相 1 设计。"); sys.exit(0)
d = json.load(open("tasks.json", encoding="utf-8"))
tasks = d.get("tasks")
if not isinstance(tasks, list): raise SystemExit("tasks.json 的 tasks 必须是数组")
by_id = {}
for t in tasks:
    if not t.get("id"): raise SystemExit("存在缺少 id 的任务")
    if t["id"] in by_id: raise SystemExit(f"重复任务 id: {t['id']}")
    if "status" not in t: raise SystemExit(f"任务 {t['id']} 缺少 status")
    by_id[t["id"]] = t
passed = [t for t in tasks if t["status"] == "passed"]
print(f"PROGRESS: {len(passed)}/{len(tasks)}  rev={d.get('rev',1)}")
ready = [t for t in tasks if t["status"] == "evidence_ready"]
blocked = [t for t in tasks if t["status"] == "blocked"]
if ready: print("待独立评审: " + ", ".join(t["id"] for t in ready))
if blocked: print("阻塞: " + ", ".join(t["id"] for t in blocked))
def deps_ok(t): return all(by_id.get(x, {}).get("status") == "passed" for x in t.get("depends_on", []))
elig = sorted((t for t in tasks if t["status"] in ("pending", "regressed") and deps_ok(t)), key=lambda t: t.get("priority", 999999))
if tasks and len(passed) == len(tasks):
    print("EXIT_SIGNAL: true  — 全部任务已通过。")
elif elig:
    t = elig[0]
    print("\n下一个任务 (置 active):")
    print(f"  [{t['id']}] P{t.get('priority','?')}: {t.get('desc','')}")
    print(f"  verify: {t.get('verify','')}")
    if t.get("depends_on"): print(f"  depends_on: {', '.join(t['depends_on'])} (已满足)")
else:
    print("\n无 eligible 任务：均处于评审中/阻塞/依赖未满足。先处理上面列出的项。")
PY
printf '\n提醒: 只推进这一个任务；完成后追加 evidence.jsonl、置 evidence_ready，并输出 HARNESS_STATUS。\n'
