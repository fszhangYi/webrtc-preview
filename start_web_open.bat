@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title webrtc-preview web+browser :7050
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

echo [webrtc-preview] web + browser  http://127.0.0.1:7050/
"%PYTHON%" -m webrtc_preview_app web --host 0.0.0.0 --port 7050 --open
set "ERR=%ERRORLEVEL%"
goto :end

:fail
set "ERR=1"
:end
echo.
echo Exit code %ERR%. Press any key to close.
pause >nul
exit /b %ERR%
