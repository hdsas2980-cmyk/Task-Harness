@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
title Task board
powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1" %*
set ERR=%ERRORLEVEL%
if not %ERR%==0 (
  echo.
  echo Start failed. Errorlevel %ERR%
  pause
)
