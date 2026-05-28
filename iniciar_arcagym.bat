@echo off
setlocal EnableExtensions EnableDelayedExpansion

cd /d "%~dp0"

set "HOST=127.0.0.1"
set "PORT=5990"
set "URL=http://%HOST%:%PORT%"

echo.
echo ========================================
echo  ARCA Gym - Servidor local
echo ========================================
echo.

if not exist ".env" (
    if exist ".env.example" (
        echo Creando .env desde .env.example...
        copy ".env.example" ".env" >nul
    )
)

set "PID_TO_CLOSE="
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":%PORT% .*LISTENING"') do (
    set "PID_TO_CLOSE=%%P"
)

if defined PID_TO_CLOSE (
    echo El puerto %PORT% esta en uso por el proceso !PID_TO_CLOSE!.
    echo Cerrando proceso para liberar el puerto...
    taskkill /F /PID !PID_TO_CLOSE! >nul 2>&1
    timeout /t 2 /nobreak >nul
) else (
    echo Puerto %PORT% disponible.
)

set "PYTHON_CMD=python"
if exist ".venv\Scripts\python.exe" (
    set "PYTHON_CMD=.venv\Scripts\python.exe"
)

echo.
echo Arrancando servidor en %URL%
echo Pulsa Ctrl+C para detenerlo.
echo.

start "" powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -Command "$url='%URL%'; $health='%URL%/dashboard'; for ($i=0; $i -lt 40; $i++) { try { Invoke-WebRequest -UseBasicParsing -Uri $health -TimeoutSec 1 -ErrorAction Stop | Out-Null; Start-Process $url; exit 0 } catch { Start-Sleep -Milliseconds 500 } }; Start-Process $url"

"%PYTHON_CMD%" -m uvicorn app.main:app --host %HOST% --port %PORT% --reload

echo.
echo Servidor detenido.
pause
