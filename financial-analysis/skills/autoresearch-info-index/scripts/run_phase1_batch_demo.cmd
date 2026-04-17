@echo off
setlocal EnableExtensions

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "SKILL_DIR=%%~fI"
set "ITEM_DIR=%SKILL_DIR%\sample-pool\items"
set "EXAMPLES_DIR=%SKILL_DIR%\examples"
set "RESULT_DIR=%EXAMPLES_DIR%\batch-news-index-results"
set "RUN_RECORD_DIR=%EXAMPLES_DIR%\batch-run-records"
set "EVALUATED_DIR=%EXAMPLES_DIR%\batch-evaluated"
set "VALIDATION_OUT=%SKILL_DIR%\sample-pool\validation-summary.json"
set "REPORT_OUT=%EXAMPLES_DIR%\phase1-batch-run-report.md"

if not exist "%RESULT_DIR%" mkdir "%RESULT_DIR%"
if not exist "%RUN_RECORD_DIR%" mkdir "%RUN_RECORD_DIR%"
if not exist "%EVALUATED_DIR%" mkdir "%EVALUATED_DIR%"
if exist "%RESULT_DIR%\item-template-result.json" del /Q "%RESULT_DIR%\item-template-result.json"
if exist "%RUN_RECORD_DIR%\item-template-run-record.json" del /Q "%RUN_RECORD_DIR%\item-template-run-record.json"
if exist "%EVALUATED_DIR%\item-template-evaluated.json" del /Q "%EVALUATED_DIR%\item-template-evaluated.json"

echo [1/4] Validating benchmark sample pool...
call "%SCRIPT_DIR%run_validate_sample_pool.cmd" "%ITEM_DIR%" --output "%VALIDATION_OUT%" --quiet
if errorlevel 1 exit /b %errorlevel%

echo [2/4] Building recency-first batch retrieval results...
for %%F in ("%ITEM_DIR%\*.json") do (
  if /I not "%%~nxF"=="item-template.json" (
    echo    - %%~nxF
    call "%SCRIPT_DIR%run_news_index.cmd" "%%~fF" --output "%RESULT_DIR%\%%~nF-result.json" --quiet
    if errorlevel 1 exit /b 1
    call "%SCRIPT_DIR%run_news_index_to_run_record.cmd" "%RESULT_DIR%\%%~nF-result.json" --output "%RUN_RECORD_DIR%\%%~nF-run-record.json" --task-id "%%~nF" --quiet
    if errorlevel 1 exit /b 1
  )
)

echo [3/4] Evaluating batch run records...
call "%SCRIPT_DIR%run_evaluate_all_run_records.cmd" "%RUN_RECORD_DIR%" --output-dir "%EVALUATED_DIR%" --quiet
if errorlevel 1 (
  if not errorlevel 2 exit /b %errorlevel%
)

echo [4/4] Building batch markdown report...
call "%SCRIPT_DIR%run_build_run_report.cmd" "%EVALUATED_DIR%" --output "%REPORT_OUT%" --quiet
if errorlevel 1 exit /b %errorlevel%

echo.
echo Phase 1 batch demo complete.
echo Sample pool: %ITEM_DIR%
echo Batch news-index results: %RESULT_DIR%
echo Validation summary: %VALIDATION_OUT%
echo Batch run records: %RUN_RECORD_DIR%
echo Batch evaluated: %EVALUATED_DIR%
echo Batch report: %REPORT_OUT%

exit /b 0
