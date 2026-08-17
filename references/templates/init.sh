#!/bin/bash
# task-harness v3.2 — 紧凑状态 + 单任务加载（bash 入口，TRAE/通用 Linux/macOS 用）
# 用法: bash init.sh   （每轮执行开始时运行，只输出推进下一步所需的最小信息；不改动当前工作目录）
set -euo pipefail

# 探测可用的 Python 解释器（跨平台：Linux/macOS 用 python3，Windows 常为 python 或 py）
PY=""
for c in python3 python py; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c "import sys" >/dev/null 2>&1; then PY="$c"; break; fi
done
if [ -z "$PY" ]; then echo "未找到可用的 Python 解释器（python3/python/py）"; exit 1; fi

"$PY" "$(dirname "$0")/init.py"