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

function ConvertTo-LabValue($Value) {
    if ($null -eq $Value) { return $null }
    if ($Value -is [PSCustomObject]) {
        $result = @{}
        foreach ($property in $Value.PSObject.Properties) {
            $result[$property.Name] = ConvertTo-LabValue $property.Value
        }
        return $result
    }
    if ($Value -is [Array]) {
        $items = @(foreach ($item in $Value) { ConvertTo-LabValue $item })
        return ,$items
    }
    return $Value
}

function Read-LabJson([string]$Path) {
    $json = Get-Content -Raw -LiteralPath $Path -Encoding utf8
    if ((Get-Command ConvertFrom-Json).Parameters.ContainsKey('AsHashtable')) {
        return $json | ConvertFrom-Json -AsHashtable
    }
    # Windows PowerShell 5.1 needs nested JSON objects converted explicitly.
    return ConvertTo-LabValue ($json | ConvertFrom-Json)
}

function Get-DeploymentState {
    $path = Join-Path $ProjectRoot '.runtime/deployment.json'
    if (Test-Path -LiteralPath $path) { return Read-LabJson $path }
    return $null
}

function Write-AtomicJson($Path, $Value) {
    $tempPath = "$Path.tmp"
    # JSON consumers in Linux containers expect UTF-8 without a byte-order mark.
    [IO.File]::WriteAllText($tempPath, (ConvertTo-Json -InputObject $Value -Depth 30), [Text.UTF8Encoding]::new($false))
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

