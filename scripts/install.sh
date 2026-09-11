#!/usr/bin/env bash
# DSH installer. Writes only DSH_HOME/skills/task-harness.
set -euo pipefail
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
HOME_DIR="${DSH_HOME:-$HOME/.dsh}"
SKILLS_DIR="$HOME_DIR/skills"
TARGET="$SKILLS_DIR/task-harness"
BACKUP_ROOT="$HOME_DIR/skill-backups"
STAMP="$(date +%Y%m%d-%H%M%S)"
mkdir -p "$SKILLS_DIR" "$BACKUP_ROOT"
if [ -e "$TARGET" ]; then
  BACKUP="$BACKUP_ROOT/task-harness-$STAMP"
  mv "$TARGET" "$BACKUP"
  echo "[BACKUP] $TARGET -> $BACKUP"
fi
STAGE="$SKILLS_DIR/.task-harness.staging-$STAMP"
cleanup(){ rm -rf "$STAGE"; }
trap cleanup EXIT
mkdir -p "$STAGE"
cp "$REPO_DIR/SKILL.md" "$STAGE/"
cp -R "$REPO_DIR/references" "$STAGE/"
find "$STAGE" -type d -name "__pycache__" -prune -exec rm -rf {} +
mv "$STAGE" "$TARGET"
trap - EXIT
echo "[OK] DSH skill -> $TARGET"
grep -q 'DeepSeek Harness' "$TARGET/SKILL.md"
echo "[VERIFY] DSH marker OK"
