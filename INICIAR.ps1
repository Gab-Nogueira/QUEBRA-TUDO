$ErrorActionPreference = 'Stop'
$pythonPath = Join-Path $env:LOCALAPPDATA 'CyolaConsultaAssistida\venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw 'Execute .\INSTALAR.ps1 primeiro.'
}
& $pythonPath (Join-Path $PSScriptRoot 'consultar.py') @args
exit $LASTEXITCODE
