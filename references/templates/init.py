#!/usr/bin/env python3
# task-harness v3.2 — 紧凑状态 + 单任务加载（幂等）
# 由 init.sh(Windows 用 bash) / init.ps1(PowerShell) 调用；按本文件所在目录读取 tasks.json
import json, os, sys

try:
    sys.stdout.reconfigure(encoding="utf-8")  # Windows 控制台默认 gbk，强制 utf-8 防中文乱码
except Exception:
    pass

base = os.path.dirname(os.path.abspath(__file__))
kp = os.path.join(base, "tasks.json")

if not os.path.exists(kp):
    print("tasks.json 不存在，先进入相 1 设计。"); sys.exit(0)

d = json.load(open(kp, encoding="utf-8-sig"))  # utf-8-sig 兼容可能带 BOM 的 Windows 导出文件
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
    return all(by_id.get(dep, {}).get("status") == "passed" for dep in t.get("depends_on", []))

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

print("\n提醒: 只推进这一个任务；完成后追加 evidence.jsonl 并置 evidence_ready；结尾输出 HARNESS_STATUS 块。")