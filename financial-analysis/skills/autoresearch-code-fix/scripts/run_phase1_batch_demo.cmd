@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "SKILL_DIR=%%~fI"
set "BUG_DIR=%SKILL_DIR%\sample-pool\bugs"
set "EXAMPLES_DIR=%SKILL_DIR%\examples"
set "RUN_RECORD_DIR=%EXAMPLES_DIR%\batch-run-records"
set "EVALUATED_DIR=%EXAMPLES_DIR%\batch-evaluated"
set "VALIDATION_OUT=%SKILL_DIR%\sample-pool\validation-summary.json"
set "REPORT_OUT=%EXAMPLES_DIR%\phase1-batch-run-report.md"

call "%SCRIPT_DIR%run_validate_sample_pool.cmd" "%BUG_DIR%" --output "%VALIDATION_OUT%"
if errorlevel 1 exit /b %errorlevel%

call "%SCRIPT_DIR%run_init_all_run_records.cmd" "%BUG_DIR%" --output-dir "%RUN_RECORD_DIR%"
if errorlevel 1 exit /b %errorlevel%

call "%SCRIPT_DIR%run_evaluate_all_run_records.cmd" "%RUN_RECORD_DIR%" --output-dir "%EVALUATED_DIR%"
if errorlevel 1 (
  if not errorlevel 2 exit /b %errorlevel%
)

call "%SCRIPT_DIR%run_build_run_report.cmd" "%EVALUATED_DIR%" --output "%REPORT_OUT%"
if errorlevel 1 exit /b %errorlevel%

echo.
echo Phase 1 batch demo complete.
echo Sample pool: %BUG_DIR%
echo Validation summary: %VALIDATION_OUT%
echo Batch run records: %RUN_RECORD_DIR%
echo Batch evaluated: %EVALUATED_DIR%
echo Batch report: %REPORT_OUT%

exit /b 0
