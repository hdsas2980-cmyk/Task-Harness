param(
  [Alias('HarnessDir')][string]$ProjectDir = (Get-Location).Path,
  [switch]$NoOpen,
  [switch]$Open
)
$ErrorActionPreference = 'Stop'
$Init = Join-Path $PSScriptRoot 'references\templates\init.ps1'
if (-not (Test-Path -LiteralPath $Init)) { throw "缺少 $Init" }
& $Init -ProjectDir $ProjectDir -NoOpen:$NoOpen -Open:$Open
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
