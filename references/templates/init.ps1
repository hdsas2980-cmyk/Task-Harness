# task-harness v3.2 - compact status + single-task loader (PowerShell entry, TRAE default shell)
# Usage: powershell -File .harness\init.ps1   or  & .\.harness\init.ps1
# Prints only the minimal info needed to advance the next step; does not change the working directory.
$ErrorActionPreference = "Stop"

$dir = Split-Path -Parent $PSCommandPath
$python = Get-Command python -ErrorAction SilentlyContinue
$py = $null
if ($python) {
    $py = $python.Source
} else {
    $pyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($pyLauncher) { $py = $pyLauncher.Source }
}
if (-not $py) { Write-Host "python / py not found (need a Python 3 interpreter)"; exit 1 }

& $py (Join-Path $dir "init.py")
exit $LASTEXITCODE