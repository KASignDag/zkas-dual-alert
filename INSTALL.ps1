#Requires -RunAsAdministrator
param(
    [string]$InstallDir = "$env:ProgramData\ZKasDualAlert",
    [string]$MigrateFrom = ""
)

$ErrorActionPreference = "Stop"
$SourceDir = $PSScriptRoot
$DataDir = Join-Path $InstallDir "data"

Write-Host "Installing ZKas Dual Alert v0.2.2 - Unofficial Community Tool..."
Write-Host "Target: $InstallDir"

$task = Get-ScheduledTask -TaskName "ZKas Dual Alert" -ErrorAction SilentlyContinue
if ($task) {
    Stop-ScheduledTask -TaskName "ZKas Dual Alert" -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
}

if ($MigrateFrom -and (Test-Path $MigrateFrom)) {
    Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object {
            $_.Name -match '^python.*\.exe$' -and
            $_.CommandLine -and
            $_.CommandLine.Contains($MigrateFrom) -and
            ($_.CommandLine -match 'app\.py|monitor\.py')
        } |
        ForEach-Object {
            Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        }
}

New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
New-Item -ItemType Directory -Path $DataDir -Force | Out-Null

$programFiles = @(
    "app.py",
    "monitor.py",
    "zkas_dual_alert.py",
    "config.example.json",
    "README.md",
    "LICENSE",
    "RELEASE_NOTES_v0.2.2.md",
    "register-startup.ps1",
    "unregister-startup.ps1",
    "UPDATE.ps1",
    "VERIFY.ps1",
    "OPEN_DASHBOARD.cmd"
)
foreach ($name in $programFiles) {
    $src = Join-Path $SourceDir $name
    if (Test-Path $src) {
        Copy-Item $src (Join-Path $InstallDir $name) -Force
    }
}

if ($MigrateFrom -and (Test-Path $MigrateFrom)) {
    foreach ($name in @("config.json", "web_config.json", "state.json", "alert.log")) {
        $candidates = @(
            (Join-Path (Join-Path $MigrateFrom "data") $name),
            (Join-Path $MigrateFrom $name)
        )
        foreach ($candidate in $candidates) {
            if (Test-Path $candidate) {
                Copy-Item $candidate (Join-Path $DataDir $name) -Force
                break
            }
        }
    }
}

if (-not (Test-Path (Join-Path $DataDir "config.json"))) {
    Copy-Item (Join-Path $InstallDir "config.example.json") (Join-Path $DataDir "config.json")
}

& icacls.exe $DataDir /inheritance:r | Out-Null
& icacls.exe $DataDir /grant:r '*S-1-5-18:(OI)(CI)F' '*S-1-5-32-544:(OI)(CI)F' | Out-Null

& (Join-Path $InstallDir "register-startup.ps1") -InstallDir $InstallDir
Start-ScheduledTask -TaskName "ZKas Dual Alert"
Start-Sleep -Seconds 4

$taskInfo = Get-ScheduledTask -TaskName "ZKas Dual Alert" -ErrorAction SilentlyContinue
$listener = Get-NetTCPConnection -LocalPort 3040 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1

Write-Host ""
Write-Host "Installation complete."
Write-Host "Task state: $($taskInfo.State)"
if ($listener) {
    Write-Host "Web UI: http://127.0.0.1:3040"
} else {
    Write-Host "The task was started, but port 3040 is not listening yet. Run VERIFY.ps1 in a few seconds."
}
Write-Host "Default login: admin / 12345678"
