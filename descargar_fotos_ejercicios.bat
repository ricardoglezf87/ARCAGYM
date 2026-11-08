@echo off
setlocal EnableExtensions

set "APP_DIR=%~dp0"
pushd "%APP_DIR%" >nul 2>&1
if errorlevel 1 (
    echo No se pudo acceder a la carpeta de ARCA Gym: %APP_DIR%
    exit /b 1
)

set "PYTHON_CMD=python"
if exist ".venv\Scripts\python.exe" (
    set "PYTHON_CMD=.venv\Scripts\python.exe"
)

"%PYTHON_CMD%" "scripts\descargar_fotos_ejercicios.py"
set "EXIT_CODE=%ERRORLEVEL%"

popd
exit /b %EXIT_CODE%
