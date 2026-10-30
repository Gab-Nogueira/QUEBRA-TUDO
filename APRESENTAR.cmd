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
"%consultaPython%" "%~dp0web_demo\launch.py" --port 5092
if errorlevel 1 (
    echo Nao foi possivel abrir a apresentacao. Confira a mensagem acima.
    pause
    exit /b 1
)
start "" "http://localhost:5092/#demonstracao"
exit /b 0
