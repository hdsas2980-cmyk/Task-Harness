param(
  [Alias('HarnessDir')][string]$ProjectDir = (Get-Location).Path,
  [switch]$NoOpen,
  [switch]$Open,
  [switch]$StatusOnly
)
$ErrorActionPreference = 'Stop'
$Python = $null
foreach ($candidate in @('python3', 'python', 'py')) {
  if (Get-Command $candidate -ErrorAction SilentlyContinue) {
    & $candidate -c 'import sys' 2>$null
    if ($LASTEXITCODE -eq 0) { $Python = $candidate; break }
  }
}
if (-not $Python) { throw 'Need Python 3.' }
if ($StatusOnly) {
  & $Python (Join-Path $PSScriptRoot 'init.py') --project $ProjectDir
  if ($LASTEXITCODE -ne 0) { throw 'status init failed' }
  exit $LASTEXITCODE
}
$Arguments = @((Join-Path $PSScriptRoot 'serve_dashboard.py'), $ProjectDir)
if ($NoOpen) { $Arguments += '--no-open' }
if ($Open) { $Arguments += '--open' }
& $Python @Arguments
if ($LASTEXITCODE -ne 0) { throw 'dashboard init failed; task files were not modified' }
