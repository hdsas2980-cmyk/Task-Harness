# 长任务看板（独立项目，不随 skill 安装）
# UTF-8。Windows 控制台先切 65001，再交给 python -X utf8。
[CmdletBinding()]
param(
  [Alias('HarnessDir')][string]$ProjectDir = '',
  [int]$Port = 0,
  [switch]$NoOpen
)
$ErrorActionPreference = 'Stop'
try { chcp 65001 | Out-Null } catch {}
[Console]::InputEncoding  = New-Object System.Text.UTF8Encoding $false
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false
$OutputEncoding = [Console]::OutputEncoding
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUTF8 = '1'

$Python = $null
foreach ($candidate in @('python', 'python3', 'py')) {
  if (Get-Command $candidate -ErrorAction SilentlyContinue) {
    & $candidate -c "import sys" 2>$null
    if ($LASTEXITCODE -eq 0) { $Python = $candidate; break }
  }
}
if (-not $Python) { throw '需要 Python 3（标准库即可）来启动看板。' }

$Serve = Join-Path $PSScriptRoot 'serve.py'
if (-not (Test-Path -LiteralPath $Serve)) { throw "缺少 $Serve" }

$Arguments = @('-X', 'utf8', $Serve)
if ($ProjectDir) { $Arguments += $ProjectDir }
if ($Port -gt 0) { $Arguments += @('--port', "$Port") }
if ($NoOpen) { $Arguments += '--no-open' }
Write-Host "启动看板..."
& $Python @Arguments
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
