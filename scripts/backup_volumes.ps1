# WisOps V2.0 Data Volume Backup
# Usage: powershell -ExecutionPolicy Bypass -File scripts\backup_volumes.ps1
#
# Archives HugeGraph / Qdrant / PostgreSQL / api_storage volumes to backups/<timestamp>/
# Uses read-only volume mount; does not interrupt running containers.

param(
    [string]$BackupRoot = "backups"
)

$ErrorActionPreference = "Stop"
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backupDir = Join-Path -Path (Resolve-Path .).Path -ChildPath "$BackupRoot\$timestamp"
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null

Write-Host "==> Backup directory: $backupDir"

$volumes = @{
    "wisops_hugegraph_data" = "/hugegraph-server/rocksdb-data"
    "wisops_qdrant_data"    = "/qdrant/storage"
    "wisops_pg_data"        = "/var/lib/postgresql/data"
    "wisops_api_storage"    = "/app/api/storage"
}

foreach ($volName in $volumes.Keys) {
    Write-Host "`n--> Backing up $volName"

    $tarFile = Join-Path -Path $backupDir -ChildPath "$volName.tar"
    docker run --rm `
        -v "${volName}:/data:ro" `
        -v "${backupDir}:/backup" `
        alpine:latest `
        sh -c "cd /data && tar cf /backup/$volName.tar ."

    if ($LASTEXITCODE -eq 0) {
        $size = (Get-Item $tarFile).Length / 1MB
        Write-Host ("    OK: {0:N2} MB" -f $size)
    } else {
        Write-Warning "    FAILED: $volName"
    }
}

Write-Host "`n==> Backup complete: $backupDir"
Write-Host "    Tip: keep recent 7 days of backups, archive or remove older ones manually."
