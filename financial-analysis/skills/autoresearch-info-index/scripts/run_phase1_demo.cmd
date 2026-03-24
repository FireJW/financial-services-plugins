@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "SKILL_DIR=%%~fI"
set "EXAMPLES_DIR=%SKILL_DIR%\examples"
set "REQUEST=%EXAMPLES_DIR%\news-index-crisis-request.json"
set "RESULT=%EXAMPLES_DIR%\news-index-crisis-result.json"
set "REPORT=%EXAMPLES_DIR%\news-index-crisis-report.md"
set "REFRESH_INPUT=%EXAMPLES_DIR%\news-index-refresh-update.json"
set "REFRESHED_RESULT=%EXAMPLES_DIR%\news-index-crisis-refreshed.json"
set "REFRESHED_REPORT=%EXAMPLES_DIR%\news-index-crisis-refreshed.md"
set "RUN_RECORD=%EXAMPLES_DIR%\news-index-crisis-run-record.json"
set "EVALUATED=%EXAMPLES_DIR%\news-index-crisis-evaluated.json"
set "DEMO_EVALUATED_DIR=%EXAMPLES_DIR%\news-index-demo-evaluated"
set "PHASE1_REPORT=%EXAMPLES_DIR%\news-index-phase1-report.md"

echo [1/5] Building base news-index result...
call "%SCRIPT_DIR%run_news_index.cmd" "%REQUEST%" --output "%RESULT%" --markdown-output "%REPORT%" --quiet
if errorlevel 1 exit /b %errorlevel%

echo [2/5] Refreshing recent windows...
call "%SCRIPT_DIR%run_news_refresh.cmd" "%RESULT%" "%REFRESH_INPUT%" --output "%REFRESHED_RESULT%" --markdown-output "%REFRESHED_REPORT%" --quiet
if errorlevel 1 exit /b %errorlevel%

echo [3/5] Bridging retrieval result into a phase-1 run record...
call "%SCRIPT_DIR%run_news_index_to_run_record.cmd" "%RESULT%" --output "%RUN_RECORD%" --quiet
if errorlevel 1 exit /b %errorlevel%

echo [4/5] Evaluating candidate against the phase-1 scorecard...
call "%SCRIPT_DIR%run_evaluate_info_index.cmd" "%RUN_RECORD%" --output "%EVALUATED%" --quiet
if errorlevel 1 (
  if not errorlevel 2 exit /b %errorlevel%
)

if not exist "%DEMO_EVALUATED_DIR%" mkdir "%DEMO_EVALUATED_DIR%"
copy /Y "%EVALUATED%" "%DEMO_EVALUATED_DIR%\news-index-crisis-evaluated.json" >nul

echo [5/5] Building markdown report...
call "%SCRIPT_DIR%run_build_run_report.cmd" "%DEMO_EVALUATED_DIR%" --output "%PHASE1_REPORT%" --quiet
if errorlevel 1 exit /b %errorlevel%

echo.
echo Phase 1 recency-first demo complete.
echo Request: %REQUEST%
echo Result: %RESULT%
echo Refresh result: %REFRESHED_RESULT%
echo Run record: %RUN_RECORD%
echo Evaluated result: %EVALUATED%
echo Report: %PHASE1_REPORT%

exit /b 0
