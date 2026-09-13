# Codex Native 安装脚本（Windows PowerShell）
# 只安装到 CODEX_HOME/skills/task-harness，绝不写入 .cc-switch 或 .claude。
$ErrorActionPreference = 'Stop'
$RepoDir = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$CodexDir = if ($env:CODEX_HOME) { [IO.Path]::GetFullPath($env:CODEX_HOME) } else { Join-Path $HOME '.codex' }
$SkillsDir = Join-Path $CodexDir 'skills'
$Target = Join-Path $SkillsDir 'task-harness'
$BackupRoot = Join-Path $CodexDir 'skill-backups'
$Stamp = Get-Date -Format 'yyyyMMdd-HHmmss'

New-Item -ItemType Directory -Force -Path $SkillsDir,$BackupRoot | Out-Null
if (Test-Path -LiteralPath $Target) {
  $Backup = Join-Path $BackupRoot "task-harness-before-codex-native-$Stamp"
  Move-Item -LiteralPath $Target -Destination $Backup
  Write-Host "[BACKUP] $Target -> $Backup"
}

$Stage = Join-Path $SkillsDir ".task-harness.staging-$Stamp"
try {
  New-Item -ItemType Directory -Force -Path $Stage | Out-Null
  Copy-Item -LiteralPath (Join-Path $RepoDir 'SKILL.md') -Destination $Stage
  Copy-Item -LiteralPath (Join-Path $RepoDir 'harness_db.py') -Destination $Stage
  Copy-Item -LiteralPath (Join-Path $RepoDir 'references') -Destination $Stage -Recurse
  $RuntimeScripts = Join-Path $Stage 'scripts'
  New-Item -ItemType Directory -Force -Path $RuntimeScripts | Out-Null
  Copy-Item -LiteralPath (Join-Path $RepoDir 'scripts/check_task_harness_language.py') -Destination $RuntimeScripts
  Copy-Item -LiteralPath (Join-Path $RepoDir 'scripts/convert_harness_json.py') -Destination $RuntimeScripts
  Get-ChildItem -LiteralPath $Stage -Recurse -Directory -Filter '__pycache__' | Remove-Item -Recurse -Force
  Move-Item -LiteralPath $Stage -Destination $Target
  Write-Host "[OK] Codex Skill -> $Target"
  Write-Host "[INFO] 未安装 commands/；未访问 .cc-switch 和 .claude。"
} catch {
  if (Test-Path -LiteralPath $Stage) { Remove-Item -LiteralPath $Stage -Recurse -Force }
  throw
}

$skill = Join-Path $Target 'SKILL.md'
$lineCount = @(Get-Content -LiteralPath $skill).Count
Write-Host "[VERIFY] $lineCount lines"
if ((Get-Content -LiteralPath $skill -Raw) -notmatch 'Codex Native') { throw '安装后的 SKILL.md 未检测到 Codex Native 标记。' }
if ((Get-Content -LiteralPath $skill -Raw) -notmatch 'harness.db') { throw '安装后的 SKILL.md 未检测到 harness.db 存储契约。' }
if (-not (Test-Path -LiteralPath (Join-Path $Target 'harness_db.py'))) { throw '安装后缺少 harness_db.py。' }
