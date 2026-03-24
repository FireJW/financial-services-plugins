@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "SKILL_DIR=%%~fI"
set "BUG_DIR=%SKILL_DIR%\sample-pool\bugs"
set "EXAMPLES_DIR=%SKILL_DIR%\examples"
set "DEFAULT_BUG=%BUG_DIR%\bug-001.json"

set "BUG_FILE=%~1"
if "%BUG_FILE%"=="" set "BUG_FILE=%DEFAULT_BUG%"

for %%I in ("%BUG_FILE%") do (
  set "BUG_STEM=%%~nI"
)

set "VALIDATION_OUT=%SKILL_DIR%\sample-pool\validation-summary.json"
set "RUN_RECORD_OUT=%EXAMPLES_DIR%\%BUG_STEM%-run-record.json"
set "EVALUATED_OUT=%EXAMPLES_DIR%\%BUG_STEM%-evaluated.json"
set "REPORT_OUT=%EXAMPLES_DIR%\phase1-run-report.md"

call "%SCRIPT_DIR%run_validate_sample_pool.cmd" "%BUG_DIR%" --output "%VALIDATION_OUT%"
if errorlevel 1 exit /b %errorlevel%

call "%SCRIPT_DIR%run_init_run_record.cmd" "%BUG_FILE%" --output "%RUN_RECORD_OUT%"
if errorlevel 1 exit /b %errorlevel%

call "%SCRIPT_DIR%run_evaluate_code_fix.cmd" "%RUN_RECORD_OUT%" --output "%EVALUATED_OUT%"
if errorlevel 1 (
  if not errorlevel 2 exit /b %errorlevel%
)

call "%SCRIPT_DIR%run_build_run_report.cmd" "%EXAMPLES_DIR%" --output "%REPORT_OUT%"
if errorlevel 1 exit /b %errorlevel%

echo.
echo Phase 1 demo complete.
echo Bug sample: %BUG_FILE%
echo Validation summary: %VALIDATION_OUT%
echo Run record: %RUN_RECORD_OUT%
echo Evaluated result: %EVALUATED_OUT%
echo Report: %REPORT_OUT%

exit /b 0
