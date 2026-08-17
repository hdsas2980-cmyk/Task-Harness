#!/usr/bin/env bash
# task-harness v3.2 (TRAE edition) install script (Linux/macOS/Windows-bash)
# Usage: git clone <repo> && cd Task-Harness && bash scripts/install.sh
#        Add --claude to also install to legacy Claude Code + CC Switch targets.
# Idempotent: safe to rerun; overwrites to current repo state each time.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TRAE_DIR="$HOME/.trae-cn"
CLAUDE_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
CC_SWITCH_DIR="$HOME/.cc-switch"
LEGACY=0
for a in "$@"; do [ "$a" = "--claude" ] && LEGACY=1; done

install_to() {
  local base="$1" label="$2"
  local dst="$base/skills/task-harness"
  mkdir -p "$base/skills"
  rm -rf "$dst"
  mkdir -p "$dst"
  cp "$REPO_DIR/SKILL.md" "$dst/"
  cp -r "$REPO_DIR/references" "$dst/"
  echo "  [OK] $label -> $dst"
}

echo "task-harness v3.2 (TRAE edition) install"
echo "source: $REPO_DIR"

# 1. TRAE global skill + commands + agents (default, required)
install_to "$TRAE_DIR" "TRAE skill"
CMD_DIR="$TRAE_DIR/commands"
mkdir -p "$CMD_DIR"
cp "$REPO_DIR/commands/"task-harness-next-*.md "$CMD_DIR/"
echo "  [OK] TRAE slash commands -> $CMD_DIR (/task-harness-next-a|b|c)"
AGENTS_DIR="$TRAE_DIR/agents"
if [ -d "$REPO_DIR/agents" ]; then
  mkdir -p "$AGENTS_DIR"
  cp "$REPO_DIR/agents/"*.md "$AGENTS_DIR/"
  echo "  [OK] 评审子智能体 -> $AGENTS_DIR (harness-reviewer)"
fi

# 2. legacy Claude Code + CC Switch (optional, --claude)
if [ "$LEGACY" = "1" ]; then
  install_to "$CLAUDE_DIR" "Claude Code (legacy)"
  mkdir -p "$CLAUDE_DIR/commands"
  cp "$REPO_DIR/commands/"task-harness-next-*.md "$CLAUDE_DIR/commands/"
  if [ -d "$CC_SWITCH_DIR" ]; then
    install_to "$CC_SWITCH_DIR" "CC Switch (legacy)"
  else
    echo "  [跳过] no CC Switch at $CC_SWITCH_DIR"
  fi
fi

echo ""
echo "done. TRAE SKILL.md: $(wc -l < "$TRAE_DIR/skills/task-harness/SKILL.md") lines"
echo "next: restart/reload TRAE, verify smoke, then design phase 1 in a project."