@echo off
setlocal

set "ROOT_DIR=%~dp0.."
cd /d "%ROOT_DIR%"

set "PYTHON_CMD=python"
where py >nul 2>nul
if %ERRORLEVEL%==0 set "PYTHON_CMD=py -3"

set "BUILD_VENV=.venv-build"
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd"') do set "DATE_TAG=%%i"
set "RELEASE_DIR=release"
set "ZIP_PATH=%RELEASE_DIR%\ASETMarker-Windows-%DATE_TAG%.zip"

echo [1/5] Creating build virtual environment
%PYTHON_CMD% -m venv %BUILD_VENV%
if errorlevel 1 goto :fail

call "%BUILD_VENV%\Scripts\activate.bat"
if errorlevel 1 goto :fail

echo [2/5] Installing dependencies
python -m pip install --upgrade pip
if errorlevel 1 goto :fail
python -m pip install -r requirements.txt pyinstaller
if errorlevel 1 goto :fail

echo [3/5] Building app with PyInstaller
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
pyinstaller --noconfirm --clean ASETMarker.spec
if errorlevel 1 goto :fail

copy /y "scripts\run_windows_client.bat" "dist\Run_ASETMarker.bat" >nul
if errorlevel 1 goto :fail

echo [4/5] Preparing release bundle
if not exist "%RELEASE_DIR%" mkdir "%RELEASE_DIR%"
if exist "%ZIP_PATH%" del /f /q "%ZIP_PATH%"
powershell -NoProfile -Command "Compress-Archive -Path 'dist\*' -DestinationPath '%ZIP_PATH%' -Force"
if errorlevel 1 goto :fail

echo [5/5] Done
echo Build output: %ROOT_DIR%\dist
echo Client handover zip: %ROOT_DIR%\%ZIP_PATH%
exit /b 0

:fail
echo Build failed.
exit /b 1
