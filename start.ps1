# WisOps 启动脚本
# 用法：
#   .\start.ps1          # 启动核心服务（Dify + 基础设施）
#   .\start.ps1 -Graph   # 启动全部服务（含图谱 API + 图谱界面）
#   .\start.ps1 -Build   # 强制重新构建镜像

param(
    [switch]$Graph,
    [switch]$Build
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "=== WisOps 启动 ===" -ForegroundColor Cyan

# 检查 Docker Desktop 是否运行
$dockerStatus = docker info 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Docker Desktop 未运行，请先启动 Docker Desktop" -ForegroundColor Red
    exit 1
}

$buildFlag = if ($Build) { "--build" } else { "" }

if ($Graph) {
    Write-Host "启动模式：完整服务（核心 + 图谱 API + 图谱界面）" -ForegroundColor Green
    if ($Build) {
        docker compose --profile graph up -d --build
    } else {
        docker compose --profile graph up -d
    }
} else {
    Write-Host "启动模式：核心服务（Dify + 基础设施）" -ForegroundColor Green
    docker compose up -d
}

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] 启动失败，请检查日志：docker compose logs" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "=== 服务启动成功 ===" -ForegroundColor Green
Write-Host "Dify 控制台：    http://localhost:8281" -ForegroundColor Yellow
Write-Host "Dify API：       http://localhost:5002" -ForegroundColor Yellow
if ($Graph) {
    Write-Host "图谱管理界面：   http://localhost:8282" -ForegroundColor Yellow
    Write-Host "图谱 API 文档：  http://localhost:8002/docs" -ForegroundColor Yellow
}
Write-Host ""
Write-Host "查看容器状态：docker compose ps"
Write-Host "查看日志：    docker compose logs --tail 50"
