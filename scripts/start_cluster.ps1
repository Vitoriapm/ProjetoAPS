[CmdletBinding()]
param(
    [switch]$Development,
    [switch]$PrepareOnly
)
$ErrorActionPreference = 'Stop'
$taskRoot = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$envPath = Join-Path $taskRoot '.env'
$projectName = if ($Development) { 'ecopulse-dev' } else { 'ecopulse-cluster' }
if (-not $Development -and ((Test-Path -LiteralPath (Join-Path $taskRoot 'infra/evidence/primary-fenced.json')) -or (Test-Path -LiteralPath (Join-Path $taskRoot ('infra/evidence/primary-fenced-' + $projectName + '.json'))))) {
    throw 'Este projeto teve o primário isolado. Use os três arquivos Compose com failover e analise a evidência; não reinicie o primário antigo.'
}

function New-TaskSecret {
    $randomBytes = New-Object byte[] 32
    $generator = [Security.Cryptography.RandomNumberGenerator]::Create()
    try { $generator.GetBytes($randomBytes) } finally { $generator.Dispose() }
    return [BitConverter]::ToString($randomBytes).Replace('-', '').ToLowerInvariant()
}

if (-not (Test-Path -LiteralPath $envPath)) {
    $contents = @(
        "POSTGRES_PASSWORD=$(New-TaskSecret)",
        "REPLICATION_PASSWORD=$(New-TaskSecret)",
        "RABBIT_PASSWORD=$(New-TaskSecret)",
        "RABBIT_ERLANG_COOKIE=$(New-TaskSecret)",
        "REDIS_PASSWORD=$(New-TaskSecret)",
        "JWT_SECRET=$(New-TaskSecret)",
        'ECOPULSE_BIND_ADDRESS=127.0.0.1',
        'ORS_API_KEY=',
        'FCM_CREDENTIALS_FILE='
    )
    $stream = [IO.File]::Open($envPath, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
    $writer = New-Object IO.StreamWriter($stream, (New-Object Text.UTF8Encoding($false)))
    try { foreach ($line in $contents) { $writer.WriteLine($line) } } finally { $writer.Dispose() }
    Write-Host '.env criado com segredos aleatórios locais; valores não exibidos.'
} else {
    Write-Host '.env existente preservado.'
}
$secretDir = Join-Path $taskRoot 'secrets'
if (-not (Test-Path -LiteralPath $secretDir)) { New-Item -ItemType Directory -Path $secretDir | Out-Null }
if ($PrepareOnly) { return }

$dockerCommand = Get-Command docker -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
$dockerClient = if ($dockerCommand) { $dockerCommand.Source } else { $null }
if (-not $dockerClient) {
    $dockerCandidates = @(
        (Join-Path $env:LOCALAPPDATA 'Programs/DockerDesktop/resources/bin/docker.exe'),
        (Join-Path $env:ProgramFiles 'Docker/Docker/resources/bin/docker.exe')
    )
    $dockerClient = $dockerCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
}
if (-not $dockerClient) {
    throw 'Docker não foi encontrado. Instale/configure Docker ou use um servidor autorizado. Nenhuma instalação automática foi feita.'
}
& $dockerClient info --format '{{.ServerVersion}}' | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Docker existe, mas o serviço não está disponível.' }

$composeArgs = @('compose', '-p', $projectName, '--env-file', $envPath, '-f', (Join-Path $taskRoot 'infra/compose.yaml'))
if (-not $Development) { $composeArgs += @('-f', (Join-Path $taskRoot 'infra/compose.cluster.yaml')) }
function Invoke-TaskCompose {
    param([string[]]$Arguments)
    & $dockerClient @composeArgs @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Docker Compose falhou no comando: $($Arguments[0])" }
}

# Validate silently: `config` stdout would contain expanded credentials.
Invoke-TaskCompose -Arguments @('config', '--quiet')
if (-not $Development) {
    Invoke-TaskCompose -Arguments @('up', '-d', 'db', 'db-replica', 'rabbit1', 'rabbit2', 'rabbit3', 'rabbit-init', 'redis1', 'redis2', 'redis3', 'redis4', 'redis5', 'redis6', 'redis-init')
}
Invoke-TaskCompose -Arguments @('up', '-d', '--build')
Write-Host "Projeto $projectName solicitado. Verifique /health e docs/infra.md; este comando sozinho não comprova os testes de cluster."
