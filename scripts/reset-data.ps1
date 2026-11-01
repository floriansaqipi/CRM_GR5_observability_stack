param([switch]$ConfirmDataDeletion)
. "$PSScriptRoot/common.ps1"
if (-not $ConfirmDataDeletion) {
    throw 'This deletes metrics, Grafana data, MongoDB experiment history, and Tempo traces. To deliberately reset, pass -ConfirmDataDeletion.'
}
Invoke-Compose --profile tracing --profile replica down --volumes --timeout 10
Write-Host 'Deleted monitoring, experiment history, and trace volumes. Source files and .env remain.'

