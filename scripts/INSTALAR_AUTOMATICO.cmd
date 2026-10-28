@echo off
setlocal
chcp 65001 >nul
set "PYTHONIOENCODING=utf-8"
set "PYTHONDONTWRITEBYTECODE=1"
set "consultaRaiz=%~dp0.."
set "consultaEnv=%LOCALAPPDATA%\CyolaConsultaAssistida\venv"
set "consultaPython=%consultaEnv%\Scripts\python.exe"
if not exist "%consultaPython%" (
    python -m venv "%consultaEnv%"
    if errorlevel 1 goto falha
)
"%consultaPython%" -m pip install -r "%consultaRaiz%\requirements_automatico.txt"
if errorlevel 1 goto falha
set "PYTHONPATH=%consultaRaiz%\src;%PYTHONPATH%"
"%consultaPython%" -m consulta_assistida.testar_recaptcha --preparar-modelo
if errorlevel 1 goto falha
echo Instalacao concluida. Execute scripts\TESTAR_RECAPTCHA.cmd para testar o modo automatico.
pause
exit /b 0
:falha
echo A instalacao nao foi concluida. Confira a mensagem acima.
pause
exit /b 2
