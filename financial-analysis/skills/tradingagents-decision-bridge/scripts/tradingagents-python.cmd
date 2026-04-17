@echo off
setlocal
for %%I in ("%~dp0..\..\..\..") do set "TRADINGAGENTS_REPO_ROOT=%%~fI"
if not defined TRADINGAGENTS_PYTHON (
  if exist "%TRADINGAGENTS_REPO_ROOT%\.tmp\tradingagents-operator-venv\Scripts\python.exe" (
    set "TRADINGAGENTS_PYTHON=%TRADINGAGENTS_REPO_ROOT%\.tmp\tradingagents-operator-venv\Scripts\python.exe"
  )
)
if not defined TRADINGAGENTS_PYTHONPATH (
  if exist "%TRADINGAGENTS_REPO_ROOT%\.tmp\tradingagents-site-packages" if exist "%TRADINGAGENTS_REPO_ROOT%\.tmp\tradingagents-upstream\tradingagents" (
    set "TRADINGAGENTS_PYTHONPATH=%TRADINGAGENTS_REPO_ROOT%\.tmp\tradingagents-site-packages;%TRADINGAGENTS_REPO_ROOT%\.tmp\tradingagents-upstream"
  )
)
if defined TRADINGAGENTS_PYTHONPATH (
  if defined PYTHONPATH (
    set "PYTHONPATH=%TRADINGAGENTS_PYTHONPATH%;%PYTHONPATH%"
  ) else (
    set "PYTHONPATH=%TRADINGAGENTS_PYTHONPATH%"
  )
)
if defined TRADINGAGENTS_PYTHON (
  if exist "%TRADINGAGENTS_PYTHON%" (
    "%TRADINGAGENTS_PYTHON%" %*
    exit /b %ERRORLEVEL%
  )
  echo TRADINGAGENTS_PYTHON does not exist: %TRADINGAGENTS_PYTHON% 1>&2
  exit /b 1
)
call "%~dp0..\..\autoresearch-info-index\scripts\python-local.cmd" %*
exit /b %ERRORLEVEL%
