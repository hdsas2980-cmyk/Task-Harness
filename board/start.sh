#!/usr/bin/env bash
set -euo pipefail
export PYTHONIOENCODING=utf-8
export PYTHONUTF8=1
ROOT="$(cd "$(dirname "$0")" && pwd)"
PY=""
for c in python3 python py; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c "import sys" >/dev/null 2>&1; then PY="$c"; break; fi
done
if [ -z "$PY" ]; then echo "需要 Python 3 来启动看板。" >&2; exit 1; fi
exec "$PY" -X utf8 "$ROOT/serve.py" "$@"
