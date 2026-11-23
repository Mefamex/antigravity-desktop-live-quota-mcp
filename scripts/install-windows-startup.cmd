@echo off
setlocal
set "REPO_DIR=%~dp0.."
for %%I in ("%REPO_DIR%") do set "REPO_DIR=%%~fI"
set "STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "VBS_PATH=%STARTUP_DIR%\antigravity-live-quota-mcp.vbs"

if not exist "%STARTUP_DIR%" mkdir "%STARTUP_DIR%"

> "%VBS_PATH%" (
    echo Set WshShell = CreateObject("WScript.Shell"^)
    echo WshShell.Run "pythonw.exe -B ""%REPO_DIR%\main.py""", 0, False
)

echo [SUCCESS] Created silent startup launcher: "%VBS_PATH%"
echo Antigravity Live Quota watcher will now start silently on Windows login.
endlocal
