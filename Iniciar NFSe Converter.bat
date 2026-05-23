@echo off
chcp 65001 > nul

:: Verifica se o Python está instalado
python --version > nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo  ╔══════════════════════════════════════════════════════╗
    echo  ║           Python nao encontrado!                     ║
    echo  ║                                                      ║
    echo  ║  Para usar o NFSe Converter, instale o Python:       ║
    echo  ║  https://www.python.org/downloads/                   ║
    echo  ║                                                      ║
    echo  ║  Marque a opcao "Add Python to PATH" na instalacao.  ║
    echo  ╚══════════════════════════════════════════════════════╝
    echo.
    pause
    exit /b 1
)

:: Vai para a pasta do script
cd /d "%~dp0"

:: Inicia a interface grafica
start "" pythonw nfse_gui.py
