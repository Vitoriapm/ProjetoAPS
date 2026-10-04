param([string]$Device = 'chrome', [string]$ApiUrl = 'http://127.0.0.1:8000')
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Join-Path (Split-Path -Parent $PSScriptRoot) 'mobile')
& flutter run -d $Device "--dart-define=API_BASE_URL=$ApiUrl"
if ($LASTEXITCODE -ne 0) { throw 'Falha ao executar Flutter.' }
