# Stop FinAlly (Windows PowerShell). Idempotent. The data volume is kept.
$Container = "finally"

docker container inspect $Container *> $null
if ($LASTEXITCODE -eq 0) {
    docker rm -f $Container | Out-Null
    Write-Host "Stopped and removed container '$Container'. Data volume 'finally-data' is preserved."
} else {
    Write-Host "Container '$Container' is not running."
}
