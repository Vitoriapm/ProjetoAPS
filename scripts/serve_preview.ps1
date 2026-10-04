param([string]$Python = 'python', [int]$Port = 5173)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath (Join-Path $projectRoot 'mobile')
& flutter build web --dart-define=API_BASE_URL=http://127.0.0.1:8000
if ($LASTEXITCODE -ne 0) { throw 'Falha ao compilar a prévia web.' }
& $Python -m http.server $Port --bind 127.0.0.1 --directory build/web
