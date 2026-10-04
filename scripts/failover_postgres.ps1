[CmdletBinding()]
param(
    [int]$ReplicaTimeoutSeconds = 90,
    [ValidateSet('ecopulse-cluster','ecopulse-validation')][string]$ProjectName = 'ecopulse-cluster',
    [string]$AdditionalComposeFile
)
$ErrorActionPreference = 'Stop'
$taskRoot = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$envPath = Join-Path $taskRoot '.env'
if (-not (Test-Path -LiteralPath $envPath)) { throw 'Execute start_cluster.ps1 antes do failover.' }
$dockerCommand = Get-Command docker -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
$dockerClient = if ($dockerCommand) { $dockerCommand.Source } else { $null }
if (-not $dockerClient) {
    $dockerCandidates = @(
        (Join-Path $env:LOCALAPPDATA 'Programs/DockerDesktop/resources/bin/docker.exe'),
        (Join-Path $env:ProgramFiles 'Docker/Docker/resources/bin/docker.exe')
    )
    $dockerClient = $dockerCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
}
if (-not $dockerClient) { throw 'Docker não disponível; nenhum failover foi executado.' }
$projectName = $ProjectName
$composeArgs = @('compose', '-p', $projectName, '--env-file', $envPath,
    '-f', (Join-Path $taskRoot 'infra/compose.yaml'), '-f', (Join-Path $taskRoot 'infra/compose.cluster.yaml'))
if ($AdditionalComposeFile) {
    $overlayPath = [IO.Path]::GetFullPath((Join-Path $taskRoot $AdditionalComposeFile))
    if (-not $overlayPath.StartsWith($taskRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase) -or -not (Test-Path -LiteralPath $overlayPath)) {
        throw 'Overlay adicional deve existir dentro do projeto.'
    }
    $composeArgs += @('-f', $overlayPath)
}
$promotedArgs = $composeArgs + @('-f', (Join-Path $taskRoot 'infra/compose.failover.yaml'))

function Invoke-TaskCompose {
    param([string[]]$Arguments, [switch]$Capture)
    if ($Capture) { $result = & $dockerClient @composeArgs @Arguments } else { & $dockerClient @composeArgs @Arguments }
    if ($LASTEXITCODE -ne 0) { throw "Compose falhou: $($Arguments[0]). Consulte os serviços; primário não será reiniciado automaticamente." }
    if ($Capture) { return (($result | Out-String).Trim()) }
}
function Read-TaskSql {
    param([string]$Service, [string]$Sql)
    return Invoke-TaskCompose -Arguments @('exec', '-T', $Service, 'psql', '-U', 'ecopulse', '-d', 'ecopulse', '-tA', '-v', 'ON_ERROR_STOP=1', '-c', $Sql) -Capture
}

& $dockerClient @promotedArgs config --quiet
if ($LASTEXITCODE -ne 0) { throw 'Compose com !override requer versão 2.24.4 ou superior; failover não iniciado.' }
$replicaRecovery = Read-TaskSql -Service 'db-replica' -Sql 'SELECT pg_is_in_recovery();'
if ($replicaRecovery -ne 't') { throw 'A réplica já está promovida ou não está disponível. Não refazer failover sem analisar o estado.' }

$startedAt = [DateTime]::UtcNow
Invoke-TaskCompose -Arguments @('stop', 'api', 'api2', 'worker', 'worker2', 'alerts')
$targetLsn = Read-TaskSql -Service 'db' -Sql 'SELECT pg_current_wal_lsn();'
if ($targetLsn -notmatch '^[0-9A-F]+/[0-9A-F]+$') { throw 'LSN do primário inválida; escritores ficaram parados para inspeção.' }
$deadline = [DateTime]::UtcNow.AddSeconds($ReplicaTimeoutSeconds)
$caughtUp = $false
while ([DateTime]::UtcNow -lt $deadline) {
    $status = Read-TaskSql -Service 'db-replica' -Sql "SELECT coalesce(pg_last_wal_replay_lsn() >= '$targetLsn'::pg_lsn, false);"
    if ($status -eq 't') { $caughtUp = $true; break }
    Start-Sleep -Seconds 1
}
if (-not $caughtUp) { throw 'Réplica não alcançou a LSN. Promoção cancelada; escritores continuam parados e primário preservado.' }

$primaryId = Invoke-TaskCompose -Arguments @('ps', '-q', 'db') -Capture
& $dockerClient network disconnect ($projectName + '_default') $primaryId
if ($LASTEXITCODE -ne 0) { throw 'Não foi possível isolar o primário da rede. Promoção não executada.' }
$evidenceDirectory = Join-Path $taskRoot 'infra/evidence'
if (-not (Test-Path -LiteralPath $evidenceDirectory)) { New-Item -ItemType Directory -Path $evidenceDirectory | Out-Null }
@{ old_primary_fenced=$true; fenced_at=[DateTime]::UtcNow.ToString('o'); target_lsn=$targetLsn;
   notice='Não executar start_cluster.ps1 sobre este projeto; primário antigo exige reconstrução controlada.' } |
    ConvertTo-Json | Set-Content -LiteralPath (Join-Path $evidenceDirectory ('primary-fenced-' + $projectName + '.json')) -Encoding UTF8
Invoke-TaskCompose -Arguments @('stop', 'db')
$promotion = Read-TaskSql -Service 'db-replica' -Sql 'SELECT pg_promote(true, 60);'
if ($promotion -ne 't') { throw 'Promoção não confirmada; primário permanece isolado. Inspecione a réplica.' }
if ((Read-TaskSql -Service 'db-replica' -Sql 'SELECT pg_is_in_recovery();') -ne 'f') { throw 'Réplica ainda está em recovery; serviços não reiniciados.' }

& $dockerClient @promotedArgs up -d --no-deps --force-recreate api api2 worker worker2 alerts nginx
if ($LASTEXITCODE -ne 0) { throw 'Banco promovido, mas algum serviço não iniciou. Não reinicie o primário antigo.' }
$completedAt = [DateTime]::UtcNow
$evidencePath = Join-Path $evidenceDirectory ('failover-' + $projectName + '-' + $completedAt.ToString('yyyyMMdd-HHmmss') + '.json')
@{ operation='controlled_postgres_promotion'; project=$projectName; started_at=$startedAt.ToString('o'); completed_at=$completedAt.ToString('o');
   elapsed_s=($completedAt-$startedAt).TotalSeconds; target_lsn=$targetLsn; replica_caught_up=$caughtUp;
   old_primary_fenced=$true; promoted_endpoint='db-replica'; replication='asynchronous, planned catch-up';
   limitation='Não prova failover inesperado sem perda nem sobrevivência à falha do host.' } |
    ConvertTo-Json | Set-Content -LiteralPath $evidencePath -Encoding UTF8
Write-Host 'Promoção controlada concluída. Use sempre os três arquivos Compose a partir de agora; não execute start_cluster.ps1 sobre este projeto promovido.'
Write-Host "Evidência sem segredos gravada em $evidencePath. Verifique /health, IDs, versões e eventos pendentes."
