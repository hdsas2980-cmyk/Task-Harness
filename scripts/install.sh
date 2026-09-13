#!/usr/bin/env bash
# Codex Native 安装脚本。
# 只安装到 CODEX_HOME/skills/task-harness，绝不写入 .cc-switch 或 .claude。
set -euo pipefail
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CODEX_DIR="${CODEX_HOME:-$HOME/.codex}"
SKILLS_DIR="$CODEX_DIR/skills"
TARGET="$SKILLS_DIR/task-harness"
BACKUP_ROOT="$CODEX_DIR/skill-backups"
STAMP="$(date +%Y%m%d-%H%M%S)"
mkdir -p "$SKILLS_DIR" "$BACKUP_ROOT"
if [ -e "$TARGET" ]; then
  BACKUP="$BACKUP_ROOT/task-harness-before-codex-native-$STAMP"
  mv "$TARGET" "$BACKUP"
  echo "[BACKUP] $TARGET -> $BACKUP"
fi
STAGE="$SKILLS_DIR/.task-harness.staging-$STAMP"
cleanup(){ rm -rf "$STAGE"; }
trap cleanup EXIT
mkdir -p "$STAGE"
cp "$REPO_DIR/SKILL.md" "$STAGE/"
cp "$REPO_DIR/harness_db.py" "$STAGE/"
cp -R "$REPO_DIR/references" "$STAGE/"
mkdir -p "$STAGE/scripts"
cp "$REPO_DIR/scripts/check_task_harness_language.py" "$STAGE/scripts/"
cp "$REPO_DIR/scripts/convert_harness_json.py" "$STAGE/scripts/"
find "$STAGE" -type d -name "__pycache__" -prune -exec rm -rf {} +
mv "$STAGE" "$TARGET"
trap - EXIT
echo "[OK] Codex Skill -> $TARGET"
echo "[INFO] 未安装 commands/；未访问 .cc-switch 和 .claude。"
grep -q 'Codex Native' "$TARGET/SKILL.md"
grep -q 'harness.db' "$TARGET/SKILL.md"
test -f "$TARGET/harness_db.py"
echo "[VERIFY] Codex Native marker OK"
