@echo off
TITLE SilphDB Master Control
color 0F

echo Booting SilphDB Systems...
echo.

:: 1. Start Docker Database
echo [1/3] Waking up the Postgres Database...
docker compose up -d

:: 2. Start API in background using the venv explicitly
echo [2/3] Spinning up FastAPI Backend...
taskkill /FI "WINDOWTITLE eq SilphDB_API" /F >nul 2>&1
start "SilphDB_API" /MIN cmd /c "venv\Scripts\uvicorn api:app --port 8000"

:: Wait 3 seconds for the API to fully boot
timeout /t 3 /nobreak >nul

:MENU
cls
echo =================================================
echo              SILPH DB - CONTROL DESK
echo =================================================
echo 1. Launch Hardware Emulator (Pygame Display)
echo 2. Add/Edit Assets (CLI)
echo 3. Manage Binders (CLI)
echo 4. Shutdown Everything and Exit
echo =================================================
set /p choice="Awaiting input (1-4): "

if "%choice%"=="1" (
    cls
    echo Launching Emulator...
    venv\Scripts\python emulator.py
    goto MENU
)
if "%choice%"=="2" (
    cls
    venv\Scripts\python tools\manage-assets.py
    pause
    goto MENU
)
if "%choice%"=="3" (
    cls
    venv\Scripts\python tools\manage-binders.py
    pause
    goto MENU
)
if "%choice%"=="4" (
    echo.
    echo Shutting down SilphDB API...
    taskkill /FI "WINDOWTITLE eq SilphDB_API" /F >nul 2>&1
    echo Suspending Database (SAFE STOP)...
    docker compose stop
    echo.
    echo Systems offline. Goodbye.
    timeout /t 2 >nul
    exit
)

goto MENU