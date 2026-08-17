# task-harness v3.2 (TRAE edition) install script (Windows PowerShell)
# Usage: git clone <repo>; cd Task-Harness; powershell -NoProfile -ExecutionPolicy Bypass -File scripts\install.ps1
#        Add -Claude to also install the legacy Claude Code + CC Switch targets.
# Idempotent: safe to rerun; overwrites to current repo state each time.
$ErrorActionPreference = "Stop"

$RepoDir   = Split-Path -Parent $PSScriptRoot
$TraeDir   = Join-Path $HOME ".trae-cn"
$ClaudeDir = if ($env:CLAUDE_CONFIG_DIR) { $env:CLAUDE_CONFIG_DIR } else { Join-Path $HOME ".claude" }
$CcSwitch  = Join-Path $HOME ".cc-switch"

function Copy-Into([string]$src, [string]$dst, [switch]$recurse) {
  New-Item -ItemType Directory -Force -Path $dst | Out-Null
  if ($recurse) { Copy-Item -Path $src -Destination $dst -Recurse -Force }
  else { Copy-Item -Path $src -Destination $dst -Force }
}

# Legacy: copy a skill into an arbitrary base (Claude / CC Switch)
function Install-SkillTo([string]$base, [string]$label) {
  $dst = Join-Path $base "skills\task-harness"
  New-Item -ItemType Directory -Force -Path (Join-Path $base "skills") | Out-Null
  if (Test-Path $dst) { Remove-Item -Recurse -Force $dst }
  New-Item -ItemType Directory -Force -Path $dst | Out-Null
  Copy-Item (Join-Path $RepoDir "SKILL.md") $dst
  Copy-Item (Join-Path $RepoDir "references") $dst -Recurse
  Write-Host "  [OK] $label -> $dst"
}

function Install-TraeBasics([string]$base) {
  # skill core
  $dst = Join-Path $base "skills\task-harness"
  if (Test-Path $dst) { Remove-Item -Recurse -Force $dst }
  New-Item -ItemType Directory -Force -Path $dst | Out-Null
  Copy-Item (Join-Path $RepoDir "SKILL.md") $dst
  Copy-Item (Join-Path $RepoDir "references") $dst -Recurse
  # slash commands -> commands dir
  $cmdDir = Join-Path $base "commands"
  New-Item -ItemType Directory -Force -Path $cmdDir | Out-Null
  Copy-Item (Join-Path $RepoDir "commands\task-harness-next-*.md") $cmdDir -Force
  # export core README path for later
  return $dst
}

Write-Host "task-harness v3.2 (TRAE edition) install"
Write-Host "source: $RepoDir"

# 1. TRAE global skill + commands + agents (default, required)
$traeSkill = Install-TraeBasics $TraeDir
$agentsDir = Join-Path $TraeDir "agents"
New-Item -ItemType Directory -Force -Path $agentsDir | Out-Null
$agentSrc = Join-Path $RepoDir "agents"
if (Test-Path $agentSrc) {
  Copy-Item (Join-Path $agentSrc "*.md") $agentsDir -Force
  Write-Host "  [OK] 评审子智能体 -> $agentsDir (harness-reviewer)"
}
Write-Host "  [OK] TRAE skill -> $traeSkill"
Write-Host "  [OK] TRAE slash commands -> $(Join-Path $TraeDir 'commands')  (/task-harness-next-a|b|c)"

# 2. legacy Claude Code + CC Switch (optional, only with -Claude)
if ($Claude.IsPresent) {
  Install-SkillTo $ClaudeDir "Claude Code (legacy)"
  $claudeCmd = Join-Path $ClaudeDir "commands"
  New-Item -ItemType Directory -Force -Path $claudeCmd | Out-Null
  Copy-Item (Join-Path $RepoDir "commands\task-harness-next-*.md") $claudeCmd -Force
  if (Test-Path $CcSwitch) {
    Install-SkillTo $CcSwitch "CC Switch 主库 (legacy)"
  } else {
    Write-Host "  [跳过] no CC Switch at $CcSwitch"
  }
}

$skill = Join-Path $TraeDir "skills\task-harness\SKILL.md"
Write-Host ""
Write-Host "done. TRAE SKILL.md lines: $((Get-Content $skill).Count)"
Write-Host "next: restart / reload TRAE, verify smoke, then design phase 1 in a project (copy references/templates/* to ~/.harness)."