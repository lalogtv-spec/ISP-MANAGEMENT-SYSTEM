@echo off
setlocal

set "PROJECT_ROOT=%~dp0.."
set "PYTHON_EXE=%PROJECT_ROOT%\.venv\Scripts\python.exe"

if not exist "%PYTHON_EXE%" (
    echo Could not find the project virtualenv at "%PYTHON_EXE%"
    exit /b 1
)

"%PYTHON_EXE%" %*
