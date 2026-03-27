@echo off
setlocal

set "EDGE_EXE=C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
if not exist "%EDGE_EXE%" set "EDGE_EXE=C:\Program Files\Microsoft\Edge\Application\msedge.exe"

if not exist "%EDGE_EXE%" (
  echo Edge executable not found.
  exit /b 1
)

tasklist /FI "IMAGENAME eq msedge.exe" | find /I "msedge.exe" >nul
if not errorlevel 1 (
  echo Edge is already running.
  echo Please close all Edge windows first, then run this command again.
  exit /b 1
)

echo Launching Edge with remote debugging on http://127.0.0.1:9222
start "" "%EDGE_EXE%" --remote-debugging-port=9222 --profile-directory=Default --new-window https://x.com/home
exit /b 0
