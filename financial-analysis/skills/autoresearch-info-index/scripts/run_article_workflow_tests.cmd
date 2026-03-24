@echo off
call "%~dp0python-local.cmd" -m unittest discover -s "%~dp0..\tests" -p "test_article_workflow.py"
