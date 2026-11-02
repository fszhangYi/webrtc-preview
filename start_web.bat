@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title webrtc-preview web :7050
call "%~dp0..\scripts\env_python.bat" || goto :fail

"%PYTHON%" -c "import webrtc_preview_app" >nul 2>&1
if errorlevel 1 (
  echo [webrtc-preview] installing editable package into .venv...
  "%PYTHON%" -m pip install -e . --no-build-isolation --no-deps
  if errorlevel 1 (
    echo [webrtc-preview] pip install failed; falling back to PYTHONPATH=src
    set "PYTHONPATH=%CD%\src;%PYTHONPATH%"
  )
)

REM 只启动后端，不打开浏览器。需要自动开页用 start_web_open.bat
REM 0.0.0.0 = 本机 127.0.0.1 与局域网网卡 IP 均可访问
echo [webrtc-preview] backend only  http://127.0.0.1:7050/  ^(also http://^<LAN-IP^>:7050/^)
echo [webrtc-preview] open the URL in a browser yourself, or use start_web_open.bat
"%PYTHON%" -m webrtc_preview_app web --host 0.0.0.0 --port 7050
set "ERR=%ERRORLEVEL%"
goto :end

:fail
set "ERR=1"
:end
echo.
echo Exit code %ERR%. Press any key to close.
pause >nul
exit /b %ERR%
