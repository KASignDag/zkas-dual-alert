#Requires -RunAsAdministrator
param(
    [string]$InstallDir = "$env:ProgramData\ZKasDualAlert"
)
$ErrorActionPreference = "Stop"
Stop-ScheduledTask -TaskName "ZKas Dual Alert" -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName "ZKas Dual Alert" -Confirm:$false -ErrorAction SilentlyContinue
Write-Host "Removed startup task: ZKas Dual Alert (Unofficial Community Tool)"
