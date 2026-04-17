@echo off
setlocal
call "%~dp0python-local.cmd" -m unittest discover -s "%~dp0..\tests" -p "test_*.py" %*
