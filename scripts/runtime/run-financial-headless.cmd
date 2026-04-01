@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run-financial-headless.ps1" %*
exit /b %ERRORLEVEL%
