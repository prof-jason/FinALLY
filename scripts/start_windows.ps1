# Start FinAlly in Docker (Windows PowerShell). Idempotent.
# Usage: .\scripts\start_windows.ps1 [-Build] [-NoOpen]
param(
    [switch]$Build,
    [switch]$NoOpen
)
$ErrorActionPreference = "Stop"

$Image = "finally"
$Container = "finally"
$Volume = "finally-data"
$Port = if ($env:FINALLY_PORT) { $env:FINALLY_PORT } else { "8000" }
$Url = "http://localhost:$Port"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

docker info *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Error "Docker is not running. Start Docker Desktop and try again."
    exit 1
}

docker image inspect $Image *> $null
if ($Build -or $LASTEXITCODE -ne 0) {
    Write-Host "Building image '$Image'..."
    docker build -t $Image .
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

# Replace any existing container (running or stopped); the volume keeps the data.
docker container inspect $Container *> $null
if ($LASTEXITCODE -eq 0) {
    Write-Host "Removing existing container '$Container'..."
    docker rm -f $Container | Out-Null
}

$RunArgs = @("run", "-d", "--name", $Container, "-v", "${Volume}:/app/db", "-p", "${Port}:8000")
if (Test-Path ".env") {
    $RunArgs += @("--env-file", ".env")
} else {
    Write-Warning ".env not found; copy .env.example to .env and set OPENROUTER_API_KEY for AI chat."
}
$RunArgs += $Image

docker @RunArgs | Out-Null
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host -NoNewline "Waiting for FinAlly to become healthy"
for ($i = 0; $i -lt 60; $i++) {
    try {
        $resp = Invoke-WebRequest -Uri "$Url/api/health" -UseBasicParsing -TimeoutSec 2
        if ($resp.StatusCode -eq 200) { Write-Host " ready."; break }
    } catch { }
    Write-Host -NoNewline "."
    Start-Sleep -Seconds 1
}
Write-Host ""

Write-Host "FinAlly is running at $Url"
Write-Host "Stop it with: .\scripts\stop_windows.ps1"

if (-not $NoOpen) {
    Start-Process $Url
}
