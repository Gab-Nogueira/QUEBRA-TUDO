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
"%consultaPython%" -c "import flask, waitress" >nul 2>&1
if errorlevel 1 (
    "%consultaPython%" -m pip install -r "%~dp0requirements_web.txt"
    if errorlevel 1 exit /b 2
)
"%consultaPython%" "%~dp0web_demo\launch.py" %*
set "consultaExit=%errorlevel%"
pause
exit /b %consultaExit%
