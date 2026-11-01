. "$PSScriptRoot/common.ps1"
Invoke-Compose --profile tracing --profile replica down --timeout 10
Write-Host 'Stopped the lab. Monitoring data is preserved.'

