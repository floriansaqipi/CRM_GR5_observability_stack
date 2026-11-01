param(
    [ValidateSet('baseline','cpu-05','cpu-1','cpu-2','memory-256','memory-512','memory-1024','replica-1','replica-2')][string]$Preset,
    [switch]$Tracing,
    [switch]$NoTracing,
    [switch]$NoBuild
)
. "$PSScriptRoot/common.ps1"
if ($Tracing -and $NoTracing) { throw 'Choose -Tracing or -NoTracing, not both.' }
$runtimeDir = Join-Path $ProjectRoot '.runtime'
$null = New-Item -ItemType Directory -Force -Path $runtimeDir
$lockPath = Join-Path $runtimeDir 'deployment.lock'
try { $deploymentLock = [IO.File]::Open($lockPath, 'OpenOrCreate', 'ReadWrite', 'None') }
catch { throw 'Another deployment operation is already running.' }
$prepared = $false
$old = Get-DeploymentState
try {
    $successPath = Join-Path $runtimeDir 'last-success.json'
    $previous = if (Test-Path -LiteralPath $successPath) { Read-LabJson $successPath } else { $old }
    $script:LabPreset = if ($Preset) { $Preset } elseif ($previous) { $previous.preset } else { 'baseline' }
    $script:LabTracing = if ($Tracing) { $true } elseif ($NoTracing) { $false } elseif ($previous) { [bool]$previous.tracing } else { $false }
    $env:LAB_TRACING_ENABLED = "$script:LabTracing".ToLowerInvariant()
    $envPath = Join-Path $ProjectRoot '.env'
    if (-not (Test-Path -LiteralPath $envPath)) {
        $bytes = New-Object byte[] 24
        $random = [Security.Cryptography.RandomNumberGenerator]::Create()
        try { $random.GetBytes($bytes) } finally { $random.Dispose() }
        $password = [BitConverter]::ToString($bytes).Replace('-', '').ToLowerInvariant()
        @('GRAFANA_ADMIN_USER=admin', "GRAFANA_ADMIN_PASSWORD=$password") | Set-Content -LiteralPath $envPath -Encoding ascii
        Write-Host 'Created .env with a random Grafana password.'
    }
    Invoke-Compose config --quiet
    $candidate = @{ preset=$script:LabPreset; tracing=$script:LabTracing; pending=$true;
                    generation=[Guid]::NewGuid().ToString(); updated_utc=[DateTime]::UtcNow.ToString('o'); error=$null }
    $statePath = Join-Path $runtimeDir 'deployment.json'
    # Every Start reads this durable flag while holding the controller's global lock.
    $guardState = if ($old) { $old.Clone() } else { $candidate.Clone() }
    $guardState.pending = $true
    Write-AtomicJson $statePath $guardState
    try {
        if (-not ($old -and $old.pending -and $old.prepared)) {
            $null = Invoke-RestMethod http://127.0.0.1:5000/api/deployment/prepare -Method Post -ContentType application/json -Body '{}' -TimeoutSec 5
        }
    } catch {
        $status = if ($_.Exception.Response) { [int]$_.Exception.Response.StatusCode } else { 0 }
        if ($status -eq 409) {
            if ($old) { Write-AtomicJson $statePath $old }
            throw 'Finish or stop the active experiment before applying a preset.'
        }
        if ($status -eq 404) {
            # One-time migration from Stage 3, which has no maintenance endpoint.
            $active = Invoke-RestMethod http://127.0.0.1:5000/api/runs/active -TimeoutSec 3
            if ($active.run) {
                if ($old) { Write-AtomicJson $statePath $old }
                throw 'Stop the active Stage 3 experiment before upgrading.'
            }
            Invoke-Compose stop controller
        } elseif ($status -ne 0) { throw }
    }
    $prepared = $true
    $candidate.prepared = $true
    Write-AtomicJson $statePath $candidate
    $targets = @('controller','compute','data')
    if ($script:LabPreset -eq 'replica-2') { $targets += 'compute-2' }
    $scrapes = @($targets | ForEach-Object { @{targets=@("${_}:5000");labels=@{project='cloud-lab1';service=$_}} })
    # Preserve an array even in small generated configurations.
    Write-AtomicJson (Join-Path $runtimeDir 'application-targets.json') $scrapes
    if (-not $script:LabTracing) { Invoke-Compose --profile tracing stop otel-collector tempo }
    if ($script:LabPreset -ne 'replica-2') { Invoke-Compose --profile replica stop compute-2 }
    if ($NoBuild) { Invoke-Compose up --detach --no-build --pull never --wait --wait-timeout 180 }
    else { Invoke-Compose up --detach --build --wait --wait-timeout 180 }
    if (-not $NoBuild) { Invoke-Compose restart prometheus grafana }
    # Independently check Docker's applied limits; application checks use cgroup files.
    $presets = Read-LabJson "$ProjectRoot/services/shared/presets.json"
    $settings = $presets[$script:LabPreset]
    $expected = @{ compute=@($settings.compute_cpus,512); data=@(1,$settings.data_memory_mib) }
    if ($settings.replicas -eq 2) { $expected['compute-2'] = @(1,512) }
    $images = @{}
    foreach ($service in $expected.Keys) {
        $id = (& docker compose --project-directory $ProjectRoot ps -q $service).Trim()
        $inspect = (& docker inspect $id | ConvertFrom-Json)[0]
        if ($inspect.HostConfig.NanoCpus -ne [long]($expected[$service][0]*1e9) -or
            $inspect.HostConfig.Memory -ne [long]($expected[$service][1]*1MB)) { throw "$service Docker limits do not match the selected preset." }
        $images[$service] = $inspect.Image
    }
    $candidate.images = $images
    Write-AtomicJson $statePath $candidate
    $deadline = [DateTime]::UtcNow.AddSeconds(60)
    do {
        $deployment = Invoke-RestMethod http://127.0.0.1:5000/api/deployment -TimeoutSec 5
        $catalog = Invoke-RestMethod http://127.0.0.1:5000/api/workloads -TimeoutSec 5
        if ($deployment.verified -and $catalog.coordinator_ready -and
            (@($catalog.workers.PSObject.Properties.Value | Where-Object { -not $_ }).Count -eq 0)) { break }
        Start-Sleep -Seconds 2
    } until ([DateTime]::UtcNow -gt $deadline)
    if (-not $deployment.verified) { throw ('Worker verification failed: ' + ($deployment.errors -join ' ')) }
    # Verification includes monitoring before allowing another experiment.
    & "$PSScriptRoot/verify.ps1" -DuringDeployment
    $candidate.pending = $false
    Write-AtomicJson $statePath $candidate
    Write-AtomicJson $successPath $candidate
    Write-Host "Deployment ready: $script:LabPreset; tracing: $script:LabTracing."
    Write-Host 'Application: http://localhost:5000'
    Write-Host 'Resources:   http://localhost:3000/d/cloud-lab1-resources'
    Write-Host 'Application graphs: http://localhost:3000/d/cloud-lab1-application'
} catch {
    if ($prepared -and $candidate) {
        $candidate.pending = $true
        $candidate.error = $_.Exception.Message
        Write-AtomicJson (Join-Path $runtimeDir 'deployment.json') $candidate
    }
    Write-Host 'Deployment did not complete. Recover with ./scripts/start.ps1 -Preset baseline -Tracing.'
    throw
} finally {
    $deploymentLock.Dispose()
}
