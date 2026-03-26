@echo off
chcp 65001 > nul
title VidGet v3.2 - Instalador

net session > nul 2>&1
if %errorLevel% neq 0 (
    echo Solicitando permisos de administrador...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

cd /d "%~dp0"
echo.
echo  Iniciando instalador de VidGet v3.2...
echo  No cierres ninguna ventana durante la instalacion.
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0INSTALAR_v3.2.ps1"

if %errorLevel% neq 0 (
    echo.
    echo  Ocurrio un error. Revisa los mensajes de arriba.
    echo.
    pause
)
