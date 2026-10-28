@echo off
setlocal
chcp 65001 >nul
set "PYTHONIOENCODING=utf-8"
set "consultaPython=%LOCALAPPDATA%\CyolaConsultaAssistida\venv\Scripts\python.exe"
if not exist "%consultaPython%" (
    echo Execute INSTALAR.ps1 primeiro.
    pause
    exit /b 2
)
if "%~1"=="" (
    "%consultaPython%" "%~dp0menu.py"
) else (
    "%consultaPython%" "%~dp0consultar_trf3.py" %*
)
set "consultaExit=%errorlevel%"
pause
exit /b %consultaExit%
