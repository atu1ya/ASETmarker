@echo off
setlocal

set "ROOT_DIR=%~dp0.."
set "APP_EXE=%ROOT_DIR%\dist\ASETMarker.exe"

if not exist "%APP_EXE%" (
  echo Could not find "%APP_EXE%".
  echo Build first using scripts\build_windows.bat
  exit /b 1
)

start "ASET Marker" "%APP_EXE%"
exit /b 0
