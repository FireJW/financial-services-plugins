@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "SKILL_DIR=%%~fI"
for %%I in ("%SKILL_DIR%\..\..\..") do set "REPO_ROOT=%%~fI"
set "EXAMPLES_DIR=%SKILL_DIR%\examples"
set "REQUEST=%EXAMPLES_DIR%\news-index-realistic-offline-request.json"
set "RESULT=%EXAMPLES_DIR%\news-index-realistic-offline-result.json"
set "REPORT=%EXAMPLES_DIR%\news-index-realistic-offline-report.md"
set "REFRESH_INPUT=%EXAMPLES_DIR%\news-index-realistic-offline-refresh.json"
set "REFRESHED_RESULT=%EXAMPLES_DIR%\news-index-realistic-offline-refreshed.json"
set "REFRESHED_REPORT=%EXAMPLES_DIR%\news-index-realistic-offline-refreshed.md"
set "RUN_RECORD=%EXAMPLES_DIR%\news-index-realistic-offline-run-record.json"
set "EVALUATED=%EXAMPLES_DIR%\news-index-realistic-offline-evaluated.json"
set "DEMO_EVALUATED_DIR=%EXAMPLES_DIR%\news-index-realistic-offline-evaluated-dir"
set "PHASE1_REPORT=%EXAMPLES_DIR%\news-index-realistic-offline-phase1-report.md"

pushd "%REPO_ROOT%"
echo [1/5] Building realistic offline news-index result...
call "%SCRIPT_DIR%run_news_index.cmd" "%REQUEST%" --output "%RESULT%" --markdown-output "%REPORT%" --quiet
if errorlevel 1 (
  popd
  exit /b %errorlevel%
)

echo [2/5] Refreshing recent windows...
call "%SCRIPT_DIR%run_news_refresh.cmd" "%RESULT%" "%REFRESH_INPUT%" --output "%REFRESHED_RESULT%" --markdown-output "%REFRESHED_REPORT%" --quiet
if errorlevel 1 (
  popd
  exit /b %errorlevel%
)

echo [3/5] Bridging retrieval result into a phase-1 run record...
call "%SCRIPT_DIR%run_news_index_to_run_record.cmd" "%RESULT%" --output "%RUN_RECORD%" --quiet
if errorlevel 1 (
  popd
  exit /b %errorlevel%
)

echo [4/5] Evaluating candidate against the phase-1 scorecard...
call "%SCRIPT_DIR%run_evaluate_info_index.cmd" "%RUN_RECORD%" --output "%EVALUATED%" --quiet
if errorlevel 1 (
  if not errorlevel 2 (
    popd
    exit /b %errorlevel%
  )
)

if not exist "%DEMO_EVALUATED_DIR%" mkdir "%DEMO_EVALUATED_DIR%"
copy /Y "%EVALUATED%" "%DEMO_EVALUATED_DIR%\news-index-realistic-offline-evaluated.json" >nul

echo [5/5] Building markdown report...
call "%SCRIPT_DIR%run_build_run_report.cmd" "%DEMO_EVALUATED_DIR%" --output "%PHASE1_REPORT%" --quiet
if errorlevel 1 (
  popd
  exit /b %errorlevel%
)

echo.
echo Realistic offline phase-1 demo complete.
echo Request: %REQUEST%
echo Result: %RESULT%
echo Refresh result: %REFRESHED_RESULT%
echo Run record: %RUN_RECORD%
echo Evaluated result: %EVALUATED%
echo Report: %PHASE1_REPORT%
popd

exit /b 0
