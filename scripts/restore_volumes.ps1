# WisOps V2.0 Data Volume Restore
# Usage: powershell -ExecutionPolicy Bypass -File scripts\restore_volumes.ps1 -BackupDir backups\20260508-120000
#
# WARNING: Restore overwrites existing volume data.
# Stop related containers first:
#   docker compose --profile graph stop hugegraph qdrant postgres api worker

param(
    [Parameter(Mandatory = $true)]
    [string]$BackupDir
)

$ErrorActionPreference = "Stop"
$resolved = Resolve-Path $BackupDir
Write-Host "==> Restoring from $resolved"

$volumes = @(
    "wisops_hugegraph_data",
    "wisops_qdrant_data",
    "wisops_pg_data",
    "wisops_api_storage"
)

foreach ($volName in $volumes) {
    $tarFile = Join-Path -Path $resolved.Path -ChildPath "$volName.tar"
    if (-not (Test-Path $tarFile)) {
        Write-Warning "Skip: $volName.tar not found"
        continue
    }

    Write-Host "`n--> Restoring $volName"
    docker run --rm `
        -v "${volName}:/data" `
        -v "${resolved}:/backup:ro" `
        alpine:latest `
        sh -c "rm -rf /data/* /data/.[!.]* 2>/dev/null; cd /data && tar xf /backup/$volName.tar"

    if ($LASTEXITCODE -eq 0) {
        Write-Host "    OK"
    } else {
        Write-Warning "    FAILED"
    }
}

Write-Host "`n==> Restore complete. Restart containers:"
Write-Host "    docker compose --profile graph up -d"
