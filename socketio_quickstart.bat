@echo off
REM Socket.IO Real-Time Integration - Quick Start Script (Windows)
REM This script sets up and starts the Traffic Dashboard with Socket.IO

setlocal enabledelayedexpansion

echo ==========================================
echo Traffic Dashboard - Socket.IO Quick Start
echo ==========================================
echo.

REM Check if Docker is running
echo [1/5] Checking Docker...
docker --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker not found. Please install Docker Desktop.
    pause
    exit /b 1
)
echo [OK] Docker found

REM Check if Redis is running
echo.
echo [2/5] Checking Redis...
docker ps | findstr "traffic_redis" >nul 2>&1
if errorlevel 1 (
    echo Attempting to start Redis...
    docker-compose up -d redis
    if errorlevel 1 (
        echo [ERROR] Failed to start Redis
        pause
        exit /b 1
    )
    echo [OK] Redis started
) else (
    echo [OK] Redis already running
)

REM Wait for Redis to be ready
echo.
echo [3/5] Waiting for Redis to be ready...
setlocal enabledelayedexpansion
for /L %%i in (1,1,30) do (
    docker exec traffic_redis redis-cli ping >nul 2>&1
    if !errorlevel! equ 0 (
        echo [OK] Redis is ready
        goto redis_ready
    )
    timeout /t 1 /nobreak >nul
)
echo [ERROR] Redis failed to start
pause
exit /b 1

:redis_ready

REM Check Python
echo.
echo [4/5] Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.8+
    pause
    exit /b 1
)
echo [OK] Python found

REM Check requirements.txt
if exist requirements.txt (
    echo [OK] requirements.txt found
) else (
    echo [ERROR] requirements.txt not found
    pause
    exit /b 1
)

REM Check dependencies
echo.
echo [5/5] Checking dependencies...
python -c "import socketio" >nul 2>&1
if errorlevel 1 (
    echo Installing packages...
    pip install -r requirements.txt
)
python -c "import redis" >nul 2>&1
python -c "import fastapi" >nul 2>&1

REM Set environment variable
set SOCKETIO_REDIS_URL=redis://localhost:6379/0

echo.
echo ==========================================
echo [OK] Setup complete!
echo ==========================================
echo.
echo Next steps:
echo.
echo 1. Set environment variables (optional, already set above):
echo    set SOCKETIO_REDIS_URL=redis://localhost:6379/0
echo.
echo 2. Start the application:
echo    python -m uvicorn app:app --host 0.0.0.0 --port 8000 --reload
echo.
echo 3. Open browser and navigate to:
echo    http://localhost:8000/police/supervisor
echo.
echo 4. Check Socket.IO connection (DevTools Console - F12):
echo    console.log(commandCenterSocket.connected)
echo.
echo 5. Create an incident to test real-time updates
echo.
echo For more information, see:
echo   - SOCKETIO_SETUP.md (detailed guide)
echo   - SOCKETIO_QUICK_REFERENCE.md (quick tips)
echo   - IMPLEMENTATION_SUMMARY.md (overview)
echo.
echo Need help? Check the troubleshooting section in SOCKETIO_SETUP.md
echo.
pause
