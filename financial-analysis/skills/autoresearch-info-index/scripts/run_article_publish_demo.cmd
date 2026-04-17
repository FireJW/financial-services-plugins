@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "SKILL_DIR=%%~fI"
for %%I in ("%SKILL_DIR%\..\..\..") do set "REPO_ROOT=%%~fI"
set "REQUEST=%SKILL_DIR%\examples\wechat-article-publish-demo-request.json"
set "OUTDIR=%REPO_ROOT%\.tmp\article-cli-smoke\article-publish-demo"
set "RESULT=%OUTDIR%\article-publish-result.json"
set "REPORT=%OUTDIR%\article-publish-report.md"
set "STAGES=%OUTDIR%\stages"

pushd "%REPO_ROOT%"
if not exist "%OUTDIR%" mkdir "%OUTDIR%"
echo [1/1] Building deterministic WeChat article publish demo...
call "%SCRIPT_DIR%run_article_publish.cmd" "%REQUEST%" --output "%RESULT%" --markdown-output "%REPORT%" --output-dir "%STAGES%" --quiet
if errorlevel 1 (
  popd
  exit /b %errorlevel%
)

echo.
echo WeChat article publish demo complete.
echo Request: %REQUEST%
echo Result: %RESULT%
echo Report: %REPORT%
echo Stage dir: %STAGES%
popd

exit /b 0
