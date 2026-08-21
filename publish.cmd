@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0publish.ps1"
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" echo Publish failed. Review the message above.
pause
exit /b %EXIT_CODE%
