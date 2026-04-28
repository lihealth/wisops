# WisOps startup script
# Usage:
#   .\start.ps1          # Start core services (Dify + infra)
#   .\start.ps1 -Graph   # Start all services (+ graph-api, graph-ui, gateway)
#   .\start.ps1 -Build   # Force rebuild images

param(
    [switch]$Graph,
    [switch]$Build
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "=== WisOps Starting ===" -ForegroundColor Cyan

# Check Docker Desktop is running
$dockerStatus = docker info 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Docker Desktop is not running. Please start Docker Desktop first." -ForegroundColor Red
    exit 1
}

if ($Graph) {
    Write-Host "Mode: Full (core + graph-api + graph-ui + gateway)" -ForegroundColor Green
    if ($Build) {
        docker compose --profile graph up -d --build
    } else {
        docker compose --profile graph up -d
    }
} else {
    Write-Host "Mode: Core only (Dify + infra)" -ForegroundColor Green
    docker compose up -d
}

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Startup failed. Check logs: docker compose logs" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "=== Services started ===" -ForegroundColor Green
if ($Graph) {
    Write-Host "--- Unified Gateway (recommended) ---" -ForegroundColor Cyan
    Write-Host "  WisOps Portal  : http://localhost:8090          (Dify home)" -ForegroundColor Yellow
    Write-Host "  Graph UI       : http://localhost:8090/graph/   (graph manager)" -ForegroundColor Yellow
    Write-Host "  Graph API docs : http://localhost:8090/graph-api/docs" -ForegroundColor Yellow
    Write-Host "--- Direct debug ports ---" -ForegroundColor DarkGray
    Write-Host "  Dify direct    : http://localhost:8281" -ForegroundColor DarkGray
    Write-Host "  Graph API direct: http://localhost:8002/docs" -ForegroundColor DarkGray
} else {
    Write-Host "  Dify console   : http://localhost:8281" -ForegroundColor Yellow
    Write-Host "  Dify API       : http://localhost:5002" -ForegroundColor Yellow
}
Write-Host ""
Write-Host "Container status : docker compose ps"
Write-Host "View logs        : docker compose logs --tail 50"


