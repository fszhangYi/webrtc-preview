@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"
title webrtc-preview · Windows 打包
echo [webrtc-preview] Windows -^> Windows package (official CPython, no Miniconda)
echo Follows pyqt-web-win-win-package / port-scan packaging.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0packaging\build_windows.ps1"
set "ERR=%ERRORLEVEL%"
echo.
echo Exit code %ERR%. Press any key to close.
pause >nul
exit /b %ERR%
