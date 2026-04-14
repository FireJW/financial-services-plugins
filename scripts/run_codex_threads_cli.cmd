@echo off
setlocal

set "REPO_ROOT=%~dp0.."
pushd "%REPO_ROOT%"

node "apps\codex-threads-cli\src\index.mjs" %*
set "EXIT_CODE=%ERRORLEVEL%"

popd
exit /b %EXIT_CODE%
