$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $env:LOCALAPPDATA 'CyolaConsultaAssistida\venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw 'Execute .\scripts\INSTALAR.ps1 primeiro.'
}
$sourcePath = Join-Path $projectRoot 'src'
$env:PYTHONDONTWRITEBYTECODE = '1'
if ($env:PYTHONPATH) {
    $env:PYTHONPATH = "$sourcePath$([IO.Path]::PathSeparator)$env:PYTHONPATH"
} else {
    $env:PYTHONPATH = $sourcePath
}
& $pythonPath -m consulta_assistida.consultar @args
exit $LASTEXITCODE
