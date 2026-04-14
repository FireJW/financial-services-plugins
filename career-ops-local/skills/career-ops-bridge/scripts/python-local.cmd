@echo off
setlocal

set "CODEX_LOCAL_PYTHON=D:\Users\rickylu\.codex\vendor\python312\python.exe"
if exist "%CODEX_LOCAL_PYTHON%" (
  "%CODEX_LOCAL_PYTHON%" %*
  exit /b %errorlevel%
)

where py >nul 2>nul
if %errorlevel%==0 (
  py %*
  exit /b %errorlevel%
)

where python >nul 2>nul
if %errorlevel%==0 (
  python %*
  exit /b %errorlevel%
)

echo No Python interpreter was found. Update career-ops-local\skills\career-ops-bridge\scripts\python-local.cmd with a working path. 1>&2
exit /b 1
