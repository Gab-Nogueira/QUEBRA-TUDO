@echo off
setlocal
chcp 65001 >nul
set "PYTHONIOENCODING=utf-8"
set "PYTHONDONTWRITEBYTECODE=1"
set "consultaRaiz=%~dp0.."
set "consultaPython=%LOCALAPPDATA%\CyolaConsultaAssistida\venv\Scripts\python.exe"
if not exist "%consultaPython%" (
    echo Execute scripts\INSTALAR_AUTOMATICO.cmd primeiro.
    pause
    exit /b 2
)
"%consultaPython%" -c "import flask, waitress" >nul 2>&1
if errorlevel 1 (
    "%consultaPython%" -m pip install -r "%consultaRaiz%\requirements_web.txt"
    if errorlevel 1 exit /b 2
)
set "PYTHONPATH=%consultaRaiz%\src;%PYTHONPATH%"
"%consultaPython%" -m consulta_assistida.web_demo.launch %*
pause
