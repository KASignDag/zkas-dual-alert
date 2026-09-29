#Requires -RunAsAdministrator
param(
    [string]$InstallDir = "$env:ProgramData\ZKasDualAlert",
    [string]$MigrateFrom = "",
    [string]$PairingCode = "",
    [string]$MinerLabel = "",
    [string]$BridgeUrl = ""
)

$ErrorActionPreference = "Stop"
$SourceDir = $PSScriptRoot
$DataDir = Join-Path $InstallDir "data"

Write-Host "Installing ZKas Dual Alert v0.2.2 - Unofficial Community Tool..."
Write-Host "Target: $InstallDir"
Write-Host ""

function Test-Bridge([string]$BaseUrl) {
    try {
        Invoke-RestMethod -Uri ($BaseUrl.TrimEnd('/') + '/api/stats') -TimeoutSec 3 | Out-Null
        return $true
    } catch {
        try {
            Invoke-WebRequest -UseBasicParsing -Uri ($BaseUrl.TrimEnd('/') + '/metrics') -TimeoutSec 3 | Out-Null
            return $true
        } catch {
            return $false
        }
    }
}

function Find-Bridge {
    param([string]$Preferred)
    $candidates = @()
    if ($Preferred) { $candidates += $Preferred.TrimEnd('/') }
    $candidates += @(
        'http://127.0.0.1:3033',
        'http://127.0.0.1:18114',
        'http://localhost:3033',
        'http://localhost:18114'
    )
    foreach ($candidate in ($candidates | Select-Object -Unique)) {
        Write-Host "Checking bridge: $candidate"
        if (Test-Bridge $candidate) {
            Write-Host "Bridge detected: $candidate"
            return $candidate
        }
    }
    return $null
}

# Stop the old scheduled instance if present.
$task = Get-ScheduledTask -TaskName "ZKas Dual Alert" -ErrorAction SilentlyContinue
if ($task) {
    Stop-ScheduledTask -TaskName "ZKas Dual Alert" -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
}

# When migrating an older portable install, stop only Python processes launched from that exact folder.
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

# Copy only program/release files. Never overwrite data with package defaults.
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

# Migrate existing settings/state/credentials if requested.
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

$configPath = Join-Path $DataDir "config.json"
$config = Get-Content $configPath -Raw | ConvertFrom-Json

$detectedBridge = Find-Bridge -Preferred $BridgeUrl
if ($detectedBridge) {
    $config.bridge.base_url = $detectedBridge
} elseif ($BridgeUrl) {
    $config.bridge.base_url = $BridgeUrl.TrimEnd('/')
    Write-Host "Bridge was not reachable during setup; saved the address anyway."
} else {
    Write-Host "No compatible local bridge was detected yet. Dual Alert will keep the default address and retry after startup."
}

if (-not $MinerLabel) {
    $MinerLabel = $env:COMPUTERNAME
}
if (-not $config.PSObject.Properties['community_dashboard']) {
    $config | Add-Member -NotePropertyName community_dashboard -NotePropertyValue ([pscustomobject]@{
        enabled = $false
        miner_label = ""
        publisher_token = ""
        pairing_url = "https://zkas.stream/api/solo-pairing?action=claim"
        telemetry_url = "https://zkas.stream/api/solo-telemetry"
    })
}
$config.community_dashboard.miner_label = $MinerLabel

if (-not $PairingCode) {
    Write-Host ""
    Write-Host "Optional: paste your ZKAS.stream Solo Alert pairing code."
    Write-Host "Press Enter to skip and pair later from the local dashboard."
    $PairingCode = Read-Host "Pairing code"
}
if ($PairingCode) {
    try {
        $pairBody = @{ pairingCode = $PairingCode.Trim().ToUpperInvariant() } | ConvertTo-Json -Compress
        $pairResult = Invoke-RestMethod -Method Post -Uri $config.community_dashboard.pairing_url -ContentType 'application/json' -Body $pairBody -TimeoutSec 15
        if (-not $pairResult.publisherToken) { throw "No publisher token returned." }
        $config.community_dashboard.publisher_token = [string]$pairResult.publisherToken
        $config.community_dashboard.enabled = $true
        Write-Host "ZKAS.stream pairing successful."
    } catch {
        Write-Host "Pairing did not complete: $($_.Exception.Message)"
        Write-Host "You can pair later from http://127.0.0.1:3040."
    }
}

$config | ConvertTo-Json -Depth 8 | Set-Content -Path $configPath -Encoding UTF8

# Protect stored credentials/settings from ordinary local users.
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
Write-Host ""
Write-Host "Setup finished. Opening the local dashboard..."
Start-Process "http://127.0.0.1:3040"
