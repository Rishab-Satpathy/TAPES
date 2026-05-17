@echo off
setlocal

set "ROOT=%~dp0"
set "VENV=%ROOT%.venv"
set "SCRIPTS=%VENV%\Scripts"
set "PYEXE=%SCRIPTS%\python.exe"
set "TAPES_EXE=%SCRIPTS%\tapes.exe"

echo.
echo TAPES Windows installer
echo =======================
echo.

where python >nul 2>nul
if errorlevel 1 (
  echo Python was not found in PATH.
  echo Install Python 3.12+ and try again.
  exit /b 1
)

if not exist "%VENV%" (
  echo Creating virtual environment...
  python -m venv "%VENV%"
  if errorlevel 1 exit /b 1
)

echo Installing TAPES...
pushd "%ROOT%"
"%PYEXE%" -m pip install --upgrade pip >nul
"%PYEXE%" -m pip install -e . >nul
if errorlevel 1 (
  popd
  echo Installation failed.
  exit /b 1
)
popd

if not exist "%TAPES_EXE%" (
  echo tapes.exe was not created.
  exit /b 1
)

echo Adding TAPES to your user PATH...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$scripts = [IO.Path]::GetFullPath('%SCRIPTS%');" ^
  "$userPath = [Environment]::GetEnvironmentVariable('Path', 'User');" ^
  "if (-not ($userPath -split ';' | Where-Object { $_ -eq $scripts })) {" ^
  "  [Environment]::SetEnvironmentVariable('Path', ($scripts + ';' + $userPath).Trim(';'), 'User')" ^
  "}"

set "PATH=%SCRIPTS%;%PATH%"

echo.
echo TAPES is installed.
echo.
echo In this window you can now run:
echo   tapes
echo.
echo In new cmd windows, reopen cmd and then run:
echo   tapes
echo.

"%TAPES_EXE%" --help
