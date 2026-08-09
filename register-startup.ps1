#Requires -RunAsAdministrator
param(
    [string]$InstallDir = "$env:ProgramData\ZKasDualAlert"
)

$ErrorActionPreference = "Stop"

function Resolve-RealPython {
    $candidates = New-Object System.Collections.Generic.List[string]

    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) {
        try {
            foreach ($line in (& py -0p 2>$null)) {
                if ($line -match '([A-Za-z]:\\.*python\.exe)\s*$') {
                    $candidates.Add($matches[1].Trim())
                }
            }
        } catch {}
    }

    foreach ($name in @("python", "python3")) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if ($cmd -and $cmd.Source -and $cmd.Source -notmatch '\\WindowsApps\\') {
            $candidates.Add($cmd.Source)
        }
    }

    foreach ($p in @(
        "$env:LocalAppData\Python",
        "$env:LocalAppData\Programs\Python",
        "$env:ProgramFiles\Python*"
    )) {
        Get-ChildItem $p -Filter python.exe -Recurse -ErrorAction SilentlyContinue |
            ForEach-Object { $candidates.Add($_.FullName) }
    }

    foreach ($candidate in ($candidates | Select-Object -Unique)) {
        if (-not (Test-Path $candidate)) { continue }
        try {
            & $candidate -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)"
            if ($LASTEXITCODE -eq 0) { return $candidate }
        } catch {}
    }

    throw "Python 3.10 or newer was not found. Install Python, then run this script again."
}

if (-not (Test-Path "$InstallDir\app.py")) {
    throw "app.py was not found in $InstallDir"
}

$python = Resolve-RealPython
Write-Host "Using Python: $python"

$action = New-ScheduledTaskAction `
    -Execute $python `
    -Argument "`"$InstallDir\app.py`"" `
    -WorkingDirectory $InstallDir

$trigger = New-ScheduledTaskTrigger -AtStartup
$trigger.Delay = "PT90S"

$principal = New-ScheduledTaskPrincipal `
    -UserId "SYSTEM" `
    -LogonType ServiceAccount `
    -RunLevel Highest

$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -RestartCount 5 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -MultipleInstances IgnoreNew

Register-ScheduledTask `
    -TaskName "ZKas Dual Alert" `
    -Action $action `
    -Trigger $trigger `
    -Principal $principal `
    -Settings $settings `
    -Force | Out-Null

Write-Host "Startup task installed: ZKas Dual Alert (Unofficial Community Tool)"
Write-Host "Boot delay: 90 seconds"
