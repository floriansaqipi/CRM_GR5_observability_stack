param([switch]$DuringDeployment)
. "$PSScriptRoot/common.ps1"

# Grafana and Prometheus may just have restarted to load provisioned files.
$readinessDeadline = [DateTime]::UtcNow.AddSeconds(90)
do {
    try {
        $null = Invoke-RestMethod http://127.0.0.1:3000/api/health -TimeoutSec 3
        $null = Invoke-WebRequest http://127.0.0.1:9090/-/ready -TimeoutSec 3 -UseBasicParsing
        break
    } catch {
        if ([DateTime]::UtcNow -gt $readinessDeadline) { throw 'Grafana or Prometheus readiness timed out.' }
        Start-Sleep -Seconds 2
    }
} while ($true)

$health = Invoke-RestMethod http://127.0.0.1:5000/health -TimeoutSec 5
if ($health.status -ne 'ok') { throw 'Flask health check failed.' }
$grafanaHeaders = Get-GrafanaHeaders
$dashboard = Invoke-RestMethod http://127.0.0.1:3000/api/dashboards/uid/cloud-lab1-resources -Headers $grafanaHeaders -TimeoutSec 10
# Stable ASCII identifiers avoid Windows PowerShell's legacy HTTP text decoding.
if ($dashboard.dashboard.uid -ne 'cloud-lab1-resources') { throw 'Provisioned dashboard not found.' }
$dataSource = Invoke-RestMethod http://127.0.0.1:3000/api/datasources/uid/prometheus/health -Headers $grafanaHeaders -TimeoutSec 10
if ($dataSource.status -ne 'OK') { throw 'Grafana cannot query Prometheus.' }

# Discovery and rate calculations need multiple samples after a fresh start.
$deadline = [DateTime]::UtcNow.AddSeconds(90)
do {
    $ready = $true
    foreach ($metric in @('container_cpu_usage_seconds_total', 'container_memory_working_set_bytes', 'container_network_receive_bytes_total', 'container_network_transmit_bytes_total')) {
        $series = @(Invoke-PromQuery ($metric + '{project="cloud-lab1",service="compute"}'))
        if ($series.Count -eq 0) { $ready = $false }
    }
    $services = @(Invoke-PromQuery 'count by (service) (container_memory_working_set_bytes{project="cloud-lab1",service!=""})')
    $expected = @('controller','compute','data','mongodb','cadvisor','prometheus','grafana')
    $deployment = Invoke-RestMethod http://127.0.0.1:5000/api/deployment -TimeoutSec 5
    if ('compute-2' -in $deployment.instances) { $expected += 'compute-2' }
    if (@($expected | Where-Object { $_ -notin $services.metric.service }).Count -ne 0) { $ready = $false }
    $up = @(Invoke-PromQuery 'up{job="cadvisor"}')
    if ($up.Count -ne 1 -or $up[0].value[1] -ne '1') { $ready = $false }
    foreach ($panel in $dashboard.dashboard.panels | Where-Object { $_.type -eq 'timeseries' -and $_.id -le 5 }) {
        $query = $panel.targets[0].expr.Replace('$service', 'compute')
        $result = @(Invoke-PromQuery $query)
        if ($result.Count -ne 1 -or $result[0].value[1] -eq 'NaN') { $ready = $false }
    }
    if (-not $ready) { Start-Sleep -Seconds 3 }
} until ($ready -or [DateTime]::UtcNow -gt $deadline)
if (-not $ready) { throw 'Container metric gate failed: inspect cAdvisor logs, Docker access, and Compose labels.' }
Write-Host "PASS: controller, provisioned dashboards, Prometheus, and $($expected.Count) core/replica services."
Write-Host 'PASS: actual CPU, RAM, network receive and transmit series exist for compute.'
Write-Host 'PASS: all four resource panel queries return a real numeric value.'
$catalog = Invoke-RestMethod http://127.0.0.1:5000/api/workloads -TimeoutSec 5
if ((-not $DuringDeployment -and -not $catalog.ready) -or -not $catalog.coordinator_ready -or
    @($catalog.workers.PSObject.Properties.Value | Where-Object { -not $_ }).Count -gt 0) { throw 'Workload services have not reconciled yet.' }
if (-not $deployment.verified) { throw 'Effective deployment limits are not verified.' }
Write-Host "PASS: workload coordinator ready. MongoDB available: $($catalog.storage_available)."
$appDashboard = Invoke-RestMethod http://127.0.0.1:3000/api/dashboards/uid/cloud-lab1-application -Headers $grafanaHeaders -TimeoutSec 10
if ($appDashboard.dashboard.uid -ne 'cloud-lab1-application') { throw 'Application dashboard not provisioned.' }
$appDeadline = [DateTime]::UtcNow.AddSeconds(45)
do {
    $targets = @(Invoke-PromQuery '(up{job="applications",project="cloud-lab1"} == 1) and (timestamp(up{job="applications",project="cloud-lab1"}) > time()-15)')
    if ($targets.Count -eq (1+$deployment.instances.Count)) { break }
    Start-Sleep -Seconds 2
} until ([DateTime]::UtcNow -gt $appDeadline)
if ($targets.Count -ne (1+$deployment.instances.Count)) { throw 'Application metric targets do not match enabled services.' }
if ($catalog.observability.tracing_enabled) {
    $code = "import urllib.request; [urllib.request.urlopen(url, timeout=3).read() for url in ('http://otel-collector:13133/', 'http://tempo:3200/ready')]"
    Invoke-Compose exec -T controller python -c $code
    $telemetryServices = @(Invoke-PromQuery 'count by(service) (container_memory_working_set_bytes{project="cloud-lab1",service=~"tempo|otel-collector"})')
    if ($telemetryServices.Count -ne 2) { throw 'Tracing services missing from resource monitoring.' }
    Write-Host "PASS: $($expected.Count+2)-service mode, Collector and Tempo ready."
} else {
    Write-Host "PASS: $($expected.Count)-service mode, tracing disabled."
}
Write-Host "PASS: application dashboard and $($targets.Count) healthy application scrapes."

