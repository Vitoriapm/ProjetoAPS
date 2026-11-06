[CmdletBinding()]
param([switch]$SkipBuild)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
& (Join-Path $PSScriptRoot 'start_cluster.ps1') -PrepareOnly
$dockerCommand = Get-Command docker -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
$dockerClient = if ($dockerCommand) { $dockerCommand.Source } else { $null }
if (-not $dockerClient) {
    $dockerCandidates = @(
        (Join-Path $env:LOCALAPPDATA 'Programs/DockerDesktop/resources/bin/docker.exe'),
        (Join-Path $env:ProgramFiles 'Docker/Docker/resources/bin/docker.exe')
    )
    $dockerClient = $dockerCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
}
if (-not $dockerClient) { throw 'Docker nao encontrado.' }
$env:ECOPULSE_IMAGE_TAG = 'apresentacao'
$composeArguments = @('compose', '-p', 'ecopulse-apresentacao', '--env-file', '.env',
    '-f', 'infra/compose.yaml', '-f', 'infra/compose.cluster.yaml', '-f', 'infra/compose.presentation.yaml')
& $dockerClient @composeArguments config --quiet
if ($LASTEXITCODE -ne 0) { throw 'Configuracao Docker invalida.' }
if (-not $SkipBuild) {
    & $dockerClient @composeArguments build api
    if ($LASTEXITCODE -ne 0) { throw 'Falha ao preparar a imagem.' }
}
& $dockerClient @composeArguments up -d
if ($LASTEXITCODE -ne 0) { throw 'Falha ao iniciar a infraestrutura da apresentacao.' }
for ($attempt = 0; $attempt -lt 90; $attempt++) {
    try {
        $health = Invoke-RestMethod -Uri 'http://127.0.0.1:8011/health' -TimeoutSec 4
        if ($health.mode -eq 'full' -and $health.status -eq 'ok') {
            Write-Host 'Ambiente full pronto: http://127.0.0.1:8011/health'
            Write-Host 'Painel: execute backend/.venv/Scripts/python.exe scripts/apresentacao_dsd.py painel'
            return
        }
    } catch { }
    Start-Sleep -Seconds 2
}
throw 'O ambiente foi iniciado, mas ainda nao esta saudavel. Execute o diagnostico da apresentacao.'
