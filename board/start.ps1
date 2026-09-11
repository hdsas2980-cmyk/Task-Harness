# Independent task board launcher. Keep this file ASCII so Windows
# PowerShell 5.1 can parse it even without a UTF-8 BOM.
[CmdletBinding()]
param(
  [Alias('HarnessDir')][string]$ProjectDir = '',
  [int]$Port = 0,
  [switch]$NoOpen,
  [switch]$NoPrompt
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
if (-not $Python) { throw 'Need Python 3 (standard library) to start the board.' }

$Serve = Join-Path $PSScriptRoot 'serve.py'
if (-not (Test-Path -LiteralPath $Serve)) { throw "Missing $Serve" }

$Arguments = @('-X', 'utf8', $Serve)
if ($ProjectDir) { $Arguments += $ProjectDir }
if ($Port -gt 0) { $Arguments += @('--port', "$Port") }
if ($NoOpen) { $Arguments += '--no-open' }
if ($NoPrompt) { $Arguments += '--no-prompt' }
Write-Host 'Starting board...'
& $Python @Arguments
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
