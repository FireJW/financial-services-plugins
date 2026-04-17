@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
set "EXAMPLES_DIR=%SCRIPT_DIR%..\examples"
set "REQUEST=%EXAMPLES_DIR%\last30days-bridge-input.json"
set "RESULT=%EXAMPLES_DIR%\last30days-bridge-result.json"
set "REPORT=%EXAMPLES_DIR%\last30days-bridge-report.md"
call "%SCRIPT_DIR%run_last30days_bridge.cmd" "%REQUEST%" --output "%RESULT%" --markdown-output "%REPORT%" --quiet
if errorlevel 1 exit /b %errorlevel%
echo last30days bridge demo written:
echo   %RESULT%
echo   %REPORT%
