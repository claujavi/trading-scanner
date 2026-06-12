@echo off
REM Trading Scanner - Setup Inicial
REM Este script instala todas las dependencias y configura el entorno

setlocal enabledelayedexpansion

echo.
echo ╔════════════════════════════════════════════════════════════════════════╗
echo ║                   TRADING SCANNER - SETUP INICIAL                      ║
echo ╚════════════════════════════════════════════════════════════════════════╝
echo.

REM Verificar que uv está instalado
where uv >nul 2>nul
if errorlevel 1 (
    echo ✗ Error: uv no está instalado o no está en PATH
    echo   Descargalo desde: https://docs.astral.sh/uv/
    pause
    exit /b 1
)
echo ✓ uv encontrado

REM Crear archivo .env si no existe
if not exist .env (
    echo ✓ Creando archivo .env desde plantilla...
    copy .env.example .env >nul
    echo ✗ Edita .env con tus credenciales de Turso y Schwab:
    echo   - TURSO_DATABASE_URL
    echo   - TURSO_AUTH_TOKEN
    echo   - SCHWAB_APP_KEY
    echo   - SCHWAB_APP_SECRET
    pause
) else (
    echo ✓ Archivo .env ya existe
)

REM Instalar dependencias con uv
echo.
echo ▶ Instalando dependencias con uv...
call uv sync
if errorlevel 1 (
    echo ✗ Error instalando dependencias
    pause
    exit /b 1
)
echo ✓ Dependencias instaladas

REM Crear directorios necesarios
echo ▶ Creando directorios...
if not exist "backtest_data" mkdir backtest_data
if not exist "input\processed" mkdir input\processed
echo ✓ Directorios creados

echo.
echo ╔════════════════════════════════════════════════════════════════════════╗
echo ║                    SETUP COMPLETADO CORRECTAMENTE                      ║
echo ║                                                                        ║
echo ║  Próximos pasos:                                                       ║
echo ║  1. Edita .env con tus credenciales                                    ║
echo ║  2. Ejecuta: iniciar.bat                                               ║
echo ╚════════════════════════════════════════════════════════════════════════╝
echo.
pause
