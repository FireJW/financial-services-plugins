@echo off
set PYTHONDONTWRITEBYTECODE=1
if not defined FINANCIAL_ANALYSIS_RUNTIME_ROOT (
  if exist "D:\Users\%USERNAME%\" (
    set "FINANCIAL_ANALYSIS_RUNTIME_ROOT=D:\Users\%USERNAME%\codex-runtime\financial-services-plugins"
  )
)
set "VENDOR_PYTHON=D:\Users\rickylu\.codex\vendor\python312\python.exe"
if exist "%VENDOR_PYTHON%" (
  "%VENDOR_PYTHON%" %*
  exit /b %ERRORLEVEL%
)

set "CODEX_BUNDLED_PYTHON=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if exist "%CODEX_BUNDLED_PYTHON%" (
  "%CODEX_BUNDLED_PYTHON%" %*
  exit /b %ERRORLEVEL%
)

set "LOCAL_PY_LAUNCHER=%LOCALAPPDATA%\Programs\Python\Launcher\py.exe"
if exist "%LOCAL_PY_LAUNCHER%" (
  "%LOCAL_PY_LAUNCHER%" -3 %*
  exit /b %ERRORLEVEL%
)

where py >nul 2>nul
if not errorlevel 1 (
  py -3 %*
  exit /b %ERRORLEVEL%
)

where python >nul 2>nul
if not errorlevel 1 (
  python %*
  exit /b %ERRORLEVEL%
)

echo Python runtime not found. Expected "%VENDOR_PYTHON%", "%CODEX_BUNDLED_PYTHON%", or a system py/python on PATH.
exit /b 1
