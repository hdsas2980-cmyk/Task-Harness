#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

if command -v python3 >/dev/null 2>&1; then
  PYTHON=(python3)
elif command -v python >/dev/null 2>&1; then
  PYTHON=(python)
elif command -v py >/dev/null 2>&1; then
  PYTHON=(py -3)
else
  printf 'BLOCKED: Python 3 is required to validate the harness.\n' >&2
  exit 2
fi

printf 'Task Harness project: %s\n' "$PROJECT_DIR"
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git status --short --branch
  if git rev-parse --verify HEAD >/dev/null 2>&1; then
    printf 'HEAD: '
    git rev-parse HEAD
  else
    printf 'HEAD: (no commits yet)\n'
  fi
  printf 'Remote: '
  git remote get-url origin 2>/dev/null || printf '(none)\n'
else
  printf 'VCS: no Git worktree; evidence must use a workspace fingerprint.\n'
fi

VALIDATOR="$PROJECT_DIR/.task-harness/scripts/validate_harness.py"
if [ ! -f "$VALIDATOR" ]; then
  printf 'BLOCKED: validator missing: %s\n' "$VALIDATOR" >&2
  exit 2
fi

"${PYTHON[@]}" "$VALIDATOR" --root "$PROJECT_DIR" --strict-paths
printf '\nRead progress.txt, then select the highest-priority ready task whose dependencies passed.\n'
printf 'Do not install, commit, push, or access production without current authorization.\n'
