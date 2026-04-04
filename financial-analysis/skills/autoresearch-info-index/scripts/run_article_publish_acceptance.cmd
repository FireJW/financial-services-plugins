@echo off
setlocal

echo [1/4] article workflow canonical snapshots
call "%~dp0python-local.cmd" "%~dp0..\tests\test_article_workflow_canonical_snapshots.py"
if errorlevel 1 exit /b %errorlevel%

echo [2/4] article publish canonical snapshots
call "%~dp0python-local.cmd" "%~dp0..\tests\test_article_publish_canonical_snapshots.py"
if errorlevel 1 exit /b %errorlevel%

echo [3/4] article workflow regression suite
call "%~dp0python-local.cmd" "%~dp0..\tests\test_article_workflow.py"
if errorlevel 1 exit /b %errorlevel%

echo [4/4] article publish regression suite
call "%~dp0python-local.cmd" "%~dp0..\tests\test_article_publish.py"
if errorlevel 1 exit /b %errorlevel%

echo Acceptance suite passed.
endlocal
