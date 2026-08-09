param(
    [string]$InstallDir = "$env:ProgramData\ZKasDualAlert"
)
$ErrorActionPreference = "Continue"

Write-Host "ZKas Dual Alert - Unofficial Community Tool verification"
Write-Host "Install: $InstallDir"
Write-Host ""

$task = Get-ScheduledTask -TaskName "ZKas Dual Alert" -ErrorAction SilentlyContinue
if ($task) {
    $info = Get-ScheduledTaskInfo -TaskName "ZKas Dual Alert"
    Write-Host "Task: $($task.State) | Last result: $($info.LastTaskResult)"
} else {
    Write-Host "Task: NOT INSTALLED"
}

$web = Get-NetTCPConnection -LocalPort 3040 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
Write-Host ("Web 3040: " + $(if ($web) {"LISTENING (PID $($web.OwningProcess))"} else {"NOT LISTENING"}))

$bridge = Get-NetTCPConnection -LocalPort 3033 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
Write-Host ("Bridge 3033: " + $(if ($bridge) {"LISTENING"} else {"NOT LISTENING"}))

$log = Join-Path $InstallDir "data\alert.log"
if (Test-Path $log) {
    Write-Host ""
    Write-Host "Recent app log:"
    Get-Content $log -Tail 8
}
