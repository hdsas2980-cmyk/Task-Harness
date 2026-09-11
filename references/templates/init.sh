#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PY=""
for c in python3 python py; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c "import sys" >/dev/null 2>&1; then PY="$c"; break; fi
done
if [ -z "$PY" ]; then echo "Need Python 3." >&2; exit 1; fi
STATUS_ONLY=0
OPEN_ARGS=()
PROJECT=""
while [ $# -gt 0 ]; do
  case "$1" in
    --status-only) STATUS_ONLY=1; shift ;;
    --no-open|--open) OPEN_ARGS+=("$1"); shift ;;
    --project|-p) PROJECT="$2"; shift 2 ;;
    --) shift; break ;;
    -*) echo "unknown arg: $1" >&2; exit 2 ;;
    *) PROJECT="$1"; shift ;;
  esac
done
PROJECT="${PROJECT:-.}"
if [ "$STATUS_ONLY" -eq 1 ]; then
  "$PY" "$SCRIPT_DIR/init.py" --project "$PROJECT"
else
  "$PY" "$SCRIPT_DIR/serve_dashboard.py" "${OPEN_ARGS[@]}" "$PROJECT"
fi
