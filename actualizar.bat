@echo off
REM Trading Scanner - Actualizar
REM Actualiza dependencias y código

setlocal enabledelayedexpansion

echo.
echo ╔════════════════════════════════════════════════════════════════════════╗
echo ║                   TRADING SCANNER - ACTUALIZAR                         ║
echo ╚════════════════════════════════════════════════════════════════════════╝
echo.

REM Verificar que uv está instalado
where uv >nul 2>nul
if errorlevel 1 (
    echo ✗ Error: uv no está instalado
    pause
    exit /b 1
)

REM Git pull
echo ▶ Actualizando código desde git...
call git pull
if errorlevel 1 (
    echo ⚠ Advertencia: git pull falló (probablemente no hay cambios)
)

REM uv sync para actualizar lockfile
echo ▶ Sincronizando dependencias...
call uv sync
if errorlevel 1 (
    echo ✗ Error sincronizando dependencias
    pause
    exit /b 1
)

echo.
echo ✓ Sistema actualizado correctamente
echo.
pause
