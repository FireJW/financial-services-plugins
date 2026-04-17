@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "SKILL_DIR=%%~fI"
set "EXAMPLES_DIR=%SKILL_DIR%\examples"
set "BASE=%EXAMPLES_DIR%\news-index-crisis-result.json"
set "REFRESH=%EXAMPLES_DIR%\news-index-refresh-update.json"
set "OUT=%EXAMPLES_DIR%\news-index-crisis-refreshed.json"
set "REPORT=%EXAMPLES_DIR%\news-index-crisis-refreshed.md"

if not exist "%BASE%" (
  echo [prep] Base result not found. Building it first...
  call "%SCRIPT_DIR%run_news_index_demo.cmd"
  if errorlevel 1 exit /b %errorlevel%
)

echo [1/1] Refreshing recent windows...
call "%SCRIPT_DIR%run_news_refresh.cmd" "%BASE%" "%REFRESH%" --output "%OUT%" --markdown-output "%REPORT%" --quiet
if errorlevel 1 exit /b %errorlevel%

echo.
echo News-refresh demo complete.
echo Base result: %BASE%
echo Refresh input: %REFRESH%
echo Refreshed result: %OUT%
echo Report: %REPORT%

exit /b 0
