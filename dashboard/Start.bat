@echo off
setlocal
set "DIR=%~dp0"
set "EXE=%DIR%dist\TaskHarness.exe"
if not exist "%EXE%" (
  echo [INFO] Building TaskHarness.exe ...
  powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%DIR%Build.ps1"
)
if not exist "%EXE%" (
  echo [FAIL] TaskHarness.exe was not found. Run dashboard\Build.ps1 first.
  exit /b 1
)
start "" "%EXE%"
endlocal
exit /b 0
