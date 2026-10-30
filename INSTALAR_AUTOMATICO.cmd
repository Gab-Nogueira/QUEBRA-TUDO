@echo off
setlocal
chcp 65001 >nul
set "PYTHONIOENCODING=utf-8"
set "consultaEnv=%LOCALAPPDATA%\CyolaConsultaAssistida\venv"
set "consultaPython=%consultaEnv%\Scripts\python.exe"
if exist "%consultaPython%" goto instalar
py -3.13 -c "import struct; assert struct.calcsize('P') == 8" >nul 2>&1
if errorlevel 1 goto usar_python
py -3.13 -m venv "%consultaEnv%"
if errorlevel 1 goto falha
goto instalar
:usar_python
python -c "import sys, struct; assert (3, 10) <= sys.version_info[:2] < (3, 14) and struct.calcsize('P') == 8" >nul 2>&1
if errorlevel 1 goto sem_python
python -m venv "%consultaEnv%"
if errorlevel 1 goto falha
:instalar
"%consultaPython%" -c "import sys, struct; assert (3, 10) <= sys.version_info[:2] < (3, 14) and struct.calcsize('P') == 8" >nul 2>&1
if errorlevel 1 goto ambiente_incompativel
echo Instalando as dependencias do Quebra Tudo. Aguarde a conclusao.
"%consultaPython%" -m pip install -r "%~dp0requirements_web.txt"
if errorlevel 1 goto falha
"%consultaPython%" -m pip check
if errorlevel 1 goto falha
echo.
echo Instalacao concluida. Execute INICIAR_WEB.cmd para abrir o painel.
echo Para a demonstracao ficticia, execute APRESENTAR.cmd.
echo O modelo de audio sera baixado no primeiro teste de reCAPTCHA.
pause
exit /b 0
:sem_python
echo Instale Python 3.13 de 64 bits e marque Add python.exe to PATH.
echo Depois feche esta janela e execute este instalador novamente.
goto falha
:ambiente_incompativel
echo O ambiente existente usa uma versao de Python incompativel.
echo Consulte a secao de solucao de problemas no README.md.
:falha
echo A instalacao nao foi concluida. Confira a mensagem acima.
pause
exit /b 2
