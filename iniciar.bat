@echo off
REM Trading Scanner - Iniciar Sistema
REM Ejecuta el scanner en desarrollo

setlocal enabledelayedexpansion

echo.
echo ╔════════════════════════════════════════════════════════════════════════╗
echo ║                   TRADING SCANNER - INICIANDO                          ║
echo ╚════════════════════════════════════════════════════════════════════════╝
echo.

REM Verificar que .env existe
if not exist .env (
    echo ✗ Error: archivo .env no encontrado
    echo   Ejecuta primero: setup.bat
    pause
    exit /b 1
)

REM Verificar que uv está instalado
where uv >nul 2>nul
if errorlevel 1 (
    echo ✗ Error: uv no está instalado
    pause
    exit /b 1
)

echo ▶ Iniciando FastAPI server...
echo   Accede a: http://localhost:8001
echo.
call uv run python -m trading_scanner.main
