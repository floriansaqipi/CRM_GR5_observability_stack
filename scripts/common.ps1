$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot

function Invoke-Compose {
    $state = Get-DeploymentState
    $selected = if ($script:LabPreset) { $script:LabPreset } elseif ($state) { $state.preset } else { 'baseline' }
    $profiles = @()
    if ($selected -eq 'replica-2') { $profiles += @('--profile','replica') }
    $traceMode = if ($null -ne $script:LabTracing) { $script:LabTracing } elseif ($state) { $state.tracing } else { $false }
    $env:LAB_TRACING_ENABLED = "$traceMode".ToLowerInvariant()
    if ($traceMode) { $profiles += @('--profile','tracing') }
    & docker compose --project-directory $ProjectRoot -f "$ProjectRoot/compose.yaml" -f "$ProjectRoot/deployment/$selected.yaml" @profiles @args
    if ($LASTEXITCODE -ne 0) { throw "Docker Compose failed (exit $LASTEXITCODE)." }
}

function Get-DeploymentState {
    $path = Join-Path $ProjectRoot '.runtime/deployment.json'
    if (Test-Path -LiteralPath $path) { return Get-Content -Raw -LiteralPath $path | ConvertFrom-Json -AsHashtable }
    return $null
}

function Write-AtomicJson($Path, $Value) {
    $tempPath = "$Path.tmp"
    $Value | ConvertTo-Json -Depth 30 | Set-Content -LiteralPath $tempPath -Encoding utf8
    Move-Item -LiteralPath $tempPath -Destination $Path -Force
}

function Get-LabSettings {
    $settings = @{}
    $envPath = Join-Path $ProjectRoot '.env'
    if (-not (Test-Path -LiteralPath $envPath)) { throw 'Run scripts/start.ps1 first.' }
    foreach ($line in Get-Content -LiteralPath $envPath) {
        if ($line -match '^([A-Z_]+)=(.*)$') { $settings[$matches[1]] = $matches[2].Trim().Trim('"').Trim("'") }
    }
    return $settings
}

function Get-GrafanaHeaders {
    $settings = Get-LabSettings
    $pair = '{0}:{1}' -f $settings.GRAFANA_ADMIN_USER, $settings.GRAFANA_ADMIN_PASSWORD
    return @{ Authorization = 'Basic ' + [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($pair)) }
}

function Invoke-PromQuery([string]$Query) {
    $url = 'http://127.0.0.1:9090/api/v1/query?query=' + [Uri]::EscapeDataString($Query)
    $result = Invoke-RestMethod -Uri $url -TimeoutSec 10
    if ($result.status -ne 'success') { throw 'Prometheus query failed.' }
    return $result.data.result
}

