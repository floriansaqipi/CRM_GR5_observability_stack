param(
    [Parameter(Mandatory)][ValidateSet('baseline','cpu-05','cpu-1','cpu-2','memory-256','memory-512','memory-1024','replica-1','replica-2')][string]$Preset
)
# The common startup path handles maintenance, recreation and verification.
& "$PSScriptRoot/start.ps1" -Preset $Preset -NoBuild
