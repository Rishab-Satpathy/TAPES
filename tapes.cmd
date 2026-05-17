@echo off
setlocal
set "ROOT=%~dp0"

:: Try .venv, then local Python installs, then system Python
set "TAPES_EXE=%ROOT%.venv\Scripts\python.exe"
if not exist "%TAPES_EXE%" set "TAPES_EXE=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not exist "%TAPES_EXE%" set "TAPES_EXE=%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
if not exist "%TAPES_EXE%" set "TAPES_EXE=%ProgramFiles%\Python312\python.exe"
if not exist "%TAPES_EXE%" set "TAPES_EXE=python"
if not exist "%TAPES_EXE%" set "TAPES_EXE=python3"

"%TAPES_EXE%" -m aitapes.tui %*
