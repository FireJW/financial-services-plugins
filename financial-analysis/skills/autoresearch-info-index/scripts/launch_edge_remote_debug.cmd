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
  echo Default X workflow: reuse the last successful flow or open a new Edge window first.
  echo Only close all Edge windows and rerun this helper if the user explicitly approved that interruptive relaunch.
  exit /b 1
)

echo Launching Edge with remote debugging on http://127.0.0.1:9222
start "" "%EDGE_EXE%" --remote-debugging-port=9222 --profile-directory=Default --new-window https://x.com/home
exit /b 0
