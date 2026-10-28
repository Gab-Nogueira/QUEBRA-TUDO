@echo off
call "%~dp0INICIAR_WEB.cmd" --port 5086 %*
exit /b %errorlevel%
