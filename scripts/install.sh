#!/usr/bin/env bash
# task-harness v3 一次性安装脚本 (Linux/macOS/Windows-bash)
# 用法: git clone <repo> && cd Task-Harness && bash scripts/install.sh
# 幂等: 可重复运行; 每次覆盖为仓库当前版本。
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CLAUDE_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
CC_SWITCH_DIR="$HOME/.cc-switch"

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

echo "task-harness v3 安装"
echo "源: $REPO_DIR"

# 1. Claude Code 实际读取目录 (必装)
install_to "$CLAUDE_DIR" "Claude Code"

# 2. CC Switch 主库 (存在才装; 它是 auto 同步权威源, 不同步会被回滚)
if [ -d "$CC_SWITCH_DIR" ]; then
  install_to "$CC_SWITCH_DIR" "CC Switch 主库"
else
  echo "  [跳过] 未检测到 CC Switch ($CC_SWITCH_DIR); 仅装到 Claude Code。"
fi

# 3. 斜杠命令 (只装到 Claude Code 命令目录)
CMD_DIR="$CLAUDE_DIR/commands"
mkdir -p "$CMD_DIR"
if [ -d "$REPO_DIR/commands" ]; then
  cp "$REPO_DIR/commands/"task-harness-next-*.md "$CMD_DIR/"
  echo "  [OK] 斜杠命令 -> $CMD_DIR (/task-harness-next-a|b|c)"
fi

echo ""
echo "完成。校验 SKILL.md:"
head -1 "$CLAUDE_DIR/skills/task-harness/SKILL.md" >/dev/null && echo "  Claude: $(wc -l < "$CLAUDE_DIR/skills/task-harness/SKILL.md") 行"
echo ""
echo "下一步: 在目标项目里进入相 1 设计, 复制 references/templates/ 下模板起草 tasks.json。"
