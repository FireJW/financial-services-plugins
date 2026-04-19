@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "SKILL_DIR=%%~fI"
for %%I in ("%SKILL_DIR%\..\..\..") do set "REPO_ROOT=%%~fI"
set "EXAMPLES_DIR=%SKILL_DIR%\examples"
set "REQUEST=%EXAMPLES_DIR%\news-index-realistic-offline-request.json"
set "RESULT=%EXAMPLES_DIR%\news-index-realistic-offline-result.json"
set "REPORT=%EXAMPLES_DIR%\news-index-realistic-offline-report.md"

pushd "%REPO_ROOT%"
echo [1/1] Building realistic offline news-index result...
call "%SCRIPT_DIR%run_news_index.cmd" "%REQUEST%" --output "%RESULT%" --markdown-output "%REPORT%" --quiet
if errorlevel 1 (
  popd
  exit /b %errorlevel%
)

echo.
echo Realistic offline news-index demo complete.
echo Request: %REQUEST%
echo Result: %RESULT%
echo Report: %REPORT%
popd

exit /b 0
