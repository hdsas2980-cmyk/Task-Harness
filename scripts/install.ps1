# task-harness v3 一次性安装脚本 (Windows PowerShell)
# 用法: git clone <repo>; cd Task-Harness; powershell -ExecutionPolicy Bypass -File scripts\install.ps1
# 幂等: 可重复运行; 每次覆盖为仓库当前版本。
$ErrorActionPreference = "Stop"

$RepoDir   = Split-Path -Parent $PSScriptRoot
$ClaudeDir = if ($env:CLAUDE_CONFIG_DIR) { $env:CLAUDE_CONFIG_DIR } else { Join-Path $HOME ".claude" }
$CcSwitch  = Join-Path $HOME ".cc-switch"

function Install-To($base, $label) {
  $dst = Join-Path $base "skills\task-harness"
  New-Item -ItemType Directory -Force -Path (Join-Path $base "skills") | Out-Null
  if (Test-Path $dst) { Remove-Item -Recurse -Force $dst }
  New-Item -ItemType Directory -Force -Path $dst | Out-Null
  Copy-Item (Join-Path $RepoDir "SKILL.md") $dst
  Copy-Item (Join-Path $RepoDir "references") $dst -Recurse
  Write-Host "  [OK] $label -> $dst"
}

Write-Host "task-harness v3 安装"
Write-Host "源: $RepoDir"

# 1. Claude Code 实际读取目录 (必装)
Install-To $ClaudeDir "Claude Code"

# 2. CC Switch 主库 (存在才装; 它是 auto 同步权威源, 不同步会被回滚)
if (Test-Path $CcSwitch) {
  Install-To $CcSwitch "CC Switch 主库"
} else {
  Write-Host "  [跳过] 未检测到 CC Switch ($CcSwitch); 仅装到 Claude Code。"
}

# 3. 斜杠命令 (只装到 Claude Code 命令目录)
$CmdDir = Join-Path $ClaudeDir "commands"
New-Item -ItemType Directory -Force -Path $CmdDir | Out-Null
$CmdSrc = Join-Path $RepoDir "commands"
if (Test-Path $CmdSrc) {
  Copy-Item (Join-Path $CmdSrc "task-harness-next-*.md") $CmdDir -Force
  Write-Host "  [OK] 斜杠命令 -> $CmdDir (/task-harness-next-a|b|c)"
}

$skill = Join-Path $ClaudeDir "skills\task-harness\SKILL.md"
Write-Host ""
Write-Host "完成。Claude SKILL.md 行数: $((Get-Content $skill).Count)"
Write-Host "下一步: 在目标项目里进入相 1 设计, 复制 references/templates/ 下模板起草 tasks.json。"
