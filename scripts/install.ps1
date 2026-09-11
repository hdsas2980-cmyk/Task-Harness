# WorkBuddy installer. Writes only WORKBUDDY_HOME/skills/task-harness.
$ErrorActionPreference = 'Stop'
$RepoDir = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$HomeDir = if ($env:WORKBUDDY_HOME) { [IO.Path]::GetFullPath($env:WORKBUDDY_HOME) } else { Join-Path $HOME '.workbuddy' }
$SkillsDir = Join-Path $HomeDir 'skills'
$Target = Join-Path $SkillsDir 'task-harness'
$BackupRoot = Join-Path $HomeDir 'skill-backups'
$Stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
New-Item -ItemType Directory -Force -Path $SkillsDir,$BackupRoot | Out-Null
if (Test-Path -LiteralPath $Target) {
  $Backup = Join-Path $BackupRoot "task-harness-$Stamp"
  Move-Item -LiteralPath $Target -Destination $Backup
  Write-Host "[BACKUP] $Target -> $Backup"
}
$Stage = Join-Path $SkillsDir ".task-harness.staging-$Stamp"
try {
  New-Item -ItemType Directory -Force -Path $Stage | Out-Null
  Copy-Item -LiteralPath (Join-Path $RepoDir 'SKILL.md') -Destination $Stage
  Copy-Item -LiteralPath (Join-Path $RepoDir 'references') -Destination $Stage -Recurse
  Get-ChildItem -LiteralPath $Stage -Recurse -Directory -Filter '__pycache__' | Remove-Item -Recurse -Force
  Move-Item -LiteralPath $Stage -Destination $Target
  Write-Host "[OK] WorkBuddy skill -> $Target"
} catch {
  if (Test-Path -LiteralPath $Stage) { Remove-Item -LiteralPath $Stage -Recurse -Force }
  throw
}
$skill = Join-Path $Target 'SKILL.md'
if ((Get-Content -LiteralPath $skill -Raw) -notmatch 'WorkBuddy') { throw 'installed SKILL.md missing WorkBuddy marker' }
Write-Host "[VERIFY] $((Get-Content -LiteralPath $skill).Count) lines"
