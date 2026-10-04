param([string]$Python = 'python', [int]$Port = 8000, [switch]$Seed)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$venvPython = Join-Path $projectRoot 'backend/.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $venvPython)) {
    & $Python -m venv 'backend/.venv'
    if ($LASTEXITCODE -ne 0) { throw 'Falha ao criar ambiente Python.' }
}
& $venvPython -m pip install -r 'backend/requirements.txt'
if ($LASTEXITCODE -ne 0) { throw 'Falha ao instalar dependências do backend.' }
if ($Seed) {
    & $venvPython 'scripts/seed_demo.py' --url "http://127.0.0.1:$Port"
    if ($LASTEXITCODE -ne 0) { throw 'Inicie o servidor antes de usar -Seed.' }
    exit
}
$env:ECOPULSE_MODE = 'demo'
Write-Host "EcoPulse DEMONSTRAÇÃO em http://127.0.0.1:$Port — SQLite local, dados fictícios."
& $venvPython -m uvicorn backend.api.main:app --host 0.0.0.0 --port $Port --no-access-log
