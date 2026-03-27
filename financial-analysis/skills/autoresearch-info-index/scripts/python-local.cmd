@echo off
set PYTHONDONTWRITEBYTECODE=1
if not defined FINANCIAL_ANALYSIS_RUNTIME_ROOT (
  if exist "D:\Users\%USERNAME%\" (
    set "FINANCIAL_ANALYSIS_RUNTIME_ROOT=D:\Users\%USERNAME%\codex-runtime\financial-services-plugins"
  )
)
"D:\Users\rickylu\.codex\vendor\python312\python.exe" %*
