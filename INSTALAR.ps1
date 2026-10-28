$ErrorActionPreference = 'Stop'
$environmentPath = Join-Path $env:LOCALAPPDATA 'CyolaConsultaAssistida\venv'
$pythonPath = Join-Path $environmentPath 'Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    & python -m venv $environmentPath
    if ($LASTEXITCODE -ne 0) { throw 'Não foi possível criar o ambiente Python isolado.' }
}
& $pythonPath -m pip install -r (Join-Path $PSScriptRoot 'requirements.txt')
if ($LASTEXITCODE -ne 0) { throw 'Não foi possível instalar o Playwright.' }
Write-Host 'Instalação concluída. Execute .\INICIAR.ps1 --demo para experimentar no Microsoft Edge.'
