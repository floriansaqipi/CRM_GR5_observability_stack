param(
    [ValidateSet('cpu','cpu_fixed','memory','network','database','combined','all')][string]$Workload = 'all',
    [ValidateSet('low','medium','high')][string]$Profile = 'medium',
    [ValidateRange(15,180)][int]$DurationSeconds = 30
)
. "$PSScriptRoot/common.ps1"
$kinds = if ($Workload -eq 'all') { @('cpu','memory','network','database','combined') } else { @($Workload) }
foreach ($kind in $kinds) {
    $settings = @{ workload=$kind; profile=$Profile; name="Demo: $kind ($Profile)" }
    if ($kind -ne 'cpu_fixed') { $settings.duration_seconds = $DurationSeconds }
    $body = $settings | ConvertTo-Json
    $run = Invoke-RestMethod 'http://127.0.0.1:5000/api/runs' -Method Post -ContentType 'application/json' -Body $body -TimeoutSec 5
    Write-Host "Started $kind ($($run.id)). Watch the control panel or $($run.grafana_url)"
    $timeout = if ($kind -eq 'cpu_fixed') { 195 } else { $DurationSeconds + 15 }
    $deadline = [DateTime]::UtcNow.AddSeconds($timeout)
    do {
        Start-Sleep -Seconds 1
        $run = Invoke-RestMethod "http://127.0.0.1:5000/api/runs/$($run.id)" -TimeoutSec 5
        if ([DateTime]::UtcNow -gt $deadline) { throw 'Run exceeded the demonstration wait deadline.' }
    } while ($run.state -in @('starting','running','stopping'))
    $run | Select-Object id,workload,state,elapsed_seconds,counters,rates,persistence
    if ($run.state -ne 'completed') { throw "Experiment ended as $($run.state): $($run.error)" }
    if ($Workload -eq 'all') { Write-Host 'Cooling down for 20 seconds.'; Start-Sleep -Seconds 20 }
}
