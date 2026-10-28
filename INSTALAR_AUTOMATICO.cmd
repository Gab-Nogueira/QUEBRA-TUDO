@echo off
setlocal
chcp 65001 >nul
set "PYTHONIOENCODING=utf-8"
set "consultaEnv=%LOCALAPPDATA%\CyolaConsultaAssistida\venv"
set "consultaPython=%consultaEnv%\Scripts\python.exe"
if not exist "%consultaPython%" (
    python -m venv "%consultaEnv%"
    if errorlevel 1 goto falha
)
"%consultaPython%" -m pip install -r "%~dp0requirements_automatico.txt"
if errorlevel 1 goto falha
"%consultaPython%" "%~dp0testar_recaptcha.py" --preparar-modelo
if errorlevel 1 goto falha
echo Instalacao concluida. Execute TESTAR_RECAPTCHA.cmd para testar o modo automatico.
pause
exit /b 0
:falha
echo A instalacao nao foi concluida. Confira a mensagem acima.
pause
exit /b 2
