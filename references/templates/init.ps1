param(
  [Alias('HarnessDir')][string]$ProjectDir = (Get-Location).Path,
  [switch]$NoOpen,
  [switch]$Open
)
$ErrorActionPreference = 'Stop'
$Python = $null
foreach($candidate in @('python3', 'python', 'py')) {
  if(Get-Command $candidate -ErrorAction SilentlyContinue) {
    & $candidate -c 'import sys' 2>$null
    if($LASTEXITCODE -eq 0) { $Python = $candidate; break }
  }
}
if(-not $Python) { throw '需要 Python 3 来生成项目任务看板。' }
$Arguments = @((Join-Path $PSScriptRoot 'render_dashboard.py'), $ProjectDir)
if($NoOpen) { $Arguments += '--no-open' }
if($Open) { $Arguments += '--open' }
& $Python @Arguments
if($LASTEXITCODE -ne 0) { throw '任务看板初始化失败，原任务文件未修改。' }
