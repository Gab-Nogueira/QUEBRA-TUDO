@echo off
setlocal
chcp 65001 >nul
set "PYTHONIOENCODING=utf-8"
set "consultaPython=%LOCALAPPDATA%\CyolaConsultaAssistida\venv\Scripts\python.exe"
if not exist "%consultaPython%" (
    echo Execute INSTALAR_AUTOMATICO.cmd primeiro.
    pause
    exit /b 2
)
"%consultaPython%" "%~dp0menu.py" %*
set "consultaExit=%errorlevel%"
pause
exit /b %consultaExit%
