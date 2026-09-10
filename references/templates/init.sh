#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PY=""
for c in python3 python py; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c "import sys" >/dev/null 2>&1; then PY="$c"; break; fi
done
if [ -z "$PY" ]; then echo "需要 Python 3 来生成项目任务看板。" >&2; exit 1; fi
# Preserve the caller's working directory, not the skill's template directory.
"$PY" "$SCRIPT_DIR/render_dashboard.py" "$@"
