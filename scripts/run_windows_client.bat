@echo off
setlocal

set "APP_EXE=%~dp0ASETMarker.exe"

if not exist "%APP_EXE%" (
  echo Could not find "%APP_EXE%" in this folder.
  echo Keep this launcher in the same folder as ASETMarker.exe.
  exit /b 1
)

start "ASET Marker" "%APP_EXE%"
exit /b 0
