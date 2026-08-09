param([string]$Version = "v0.2.2")
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Out = Join-Path $Root "dist"
$Stage = Join-Path $Out "zkas-dual-alert-$Version"
Remove-Item $Out -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path $Stage -Force | Out-Null

$excludeDirs = @('.git','data','dist','__pycache__','.venv','venv')
$excludeFiles = @('config.json','web_config.json','state.json','alert.log','.env','wallet-token.txt')
Get-ChildItem $Root -Force | Where-Object {
    $_.Name -notin $excludeDirs -and $_.Name -notin $excludeFiles -and $_.Extension -notin @('.zip','.sha256','.db','.sqlite','.sqlite3','.log','.pid')
} | ForEach-Object {
    Copy-Item $_.FullName $Stage -Recurse -Force
}

$zip = Join-Path $Out "zkas-dual-alert-$Version-windows.zip"
Compress-Archive -Path "$Stage\*" -DestinationPath $zip -Force
$hash = (Get-FileHash $zip -Algorithm SHA256).Hash.ToLowerInvariant()
"$hash  $(Split-Path $zip -Leaf)" | Set-Content "$zip.sha256" -Encoding ascii
Write-Host "Created: $zip"
Write-Host "SHA-256: $hash"
