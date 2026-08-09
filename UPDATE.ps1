#Requires -RunAsAdministrator
param(
    [string]$InstallDir = "$env:ProgramData\ZKasDualAlert"
)
$ErrorActionPreference = "Stop"
& "$PSScriptRoot\INSTALL.ps1" -InstallDir $InstallDir
