@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "SKILL_DIR=%%~fI"
set "EXAMPLES_DIR=%SKILL_DIR%\examples"
set "REQUEST=%EXAMPLES_DIR%\news-index-crisis-request.json"
set "RESULT=%EXAMPLES_DIR%\news-index-crisis-result.json"
set "REPORT=%EXAMPLES_DIR%\news-index-crisis-report.md"

echo [1/1] Building base news-index result...
call "%SCRIPT_DIR%run_news_index.cmd" "%REQUEST%" --output "%RESULT%" --markdown-output "%REPORT%" --quiet
if errorlevel 1 exit /b %errorlevel%

echo.
echo News-index demo complete.
echo Request: %REQUEST%
echo Result: %RESULT%
echo Report: %REPORT%

exit /b 0
