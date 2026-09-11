$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
$Sln = Join-Path $Root "TaskHarness.sln"
$Proj = Join-Path $Root "TaskHarness\TaskHarness.csproj"
$Dist = Join-Path $Root "dist"

dotnet test $Sln -c Release --nologo
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

New-Item -ItemType Directory -Force -Path $Dist | Out-Null
dotnet publish $Proj `
  -c Release `
  -r win-x64 `
  --self-contained true `
  -p:PublishSingleFile=true `
  -p:IncludeNativeLibrariesForSelfExtract=true `
  -p:EnableCompressionInSingleFile=true `
  -p:DebugType=None `
  -p:DebugSymbols=false `
  -o $Dist `
  --nologo

if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$exe = Join-Path $Dist "TaskHarness.exe"
if (-not (Test-Path $exe)) {
  Write-Error "[FAIL] missing $exe"
  exit 1
}
Get-Item $exe | Format-List FullName, Length, LastWriteTime
Write-Host "[ OK ] self-contained single file: $exe"
