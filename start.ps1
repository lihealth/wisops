# WisOps V2.0 启动脚本
# 用法：
#   .\start.ps1              # 仅启动核心服务（Dify + 基础设施）
#   .\start.ps1 -Graph       # 启动全部服务（+ graph-api / graph-ui / portal）
#   .\start.ps1 -Graph -Build # 强制重新构建镜像

param(
    [switch]$Graph,
    [switch]$Build
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "=== WisOps V2.0 启动 ===" -ForegroundColor Cyan

# 检查 .env 文件
if (-not (Test-Path ".env")) {
    Write-Host "[WARN] 未找到 .env 文件，将使用默认开发环境值（生产前请复制 .env.example 并修改）" -ForegroundColor Yellow
}

# 检查 Docker Desktop
$dockerStatus = docker info 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Docker Desktop 未运行，请先启动 Docker Desktop" -ForegroundColor Red
    exit 1
}

if ($Graph) {
    Write-Host "模式：完整（核心 + graph-api + portal V2.0）" -ForegroundColor Green
    if ($Build) {
        docker compose --profile graph up -d --build
    } else {
        docker compose --profile graph up -d
    }
} else {
    Write-Host "模式：仅核心服务（Dify + 基础设施）" -ForegroundColor Green
    docker compose up -d
}

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] 启动失败，请检查日志：docker compose logs" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "=== 服务已启动 ===" -ForegroundColor Green

if ($Graph) {
    Write-Host ""
    Write-Host "─── WisOps Portal V2.0（推荐入口） ───────────────────────" -ForegroundColor Cyan
    Write-Host "  统一门户     : http://localhost:8090         (首页 / AI问答 / 图谱 / 抽取 / 看板)" -ForegroundColor Yellow
    Write-Host "  Graph API    : http://localhost:8090/graph-api/docs  (Swagger 文档)" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "─── 独立调试端口 ──────────────────────────────────────────" -ForegroundColor DarkGray
    Write-Host "  Dify 控制台  : http://localhost:8281" -ForegroundColor DarkGray
    Write-Host "  Dify API     : http://localhost:5002" -ForegroundColor DarkGray
    Write-Host "  HugeGraph    : http://localhost:8081" -ForegroundColor DarkGray
    Write-Host "  Graph API    : http://localhost:8002/docs" -ForegroundColor DarkGray
} else {
    Write-Host "  Dify 控制台  : http://localhost:8281" -ForegroundColor Yellow
    Write-Host "  Dify API     : http://localhost:5002" -ForegroundColor Yellow
    Write-Host "  HugeGraph    : http://localhost:8081" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "提示：运行 .\start.ps1 -Graph -Build 启动包含图谱管理的完整服务" -ForegroundColor DarkGray
}

Write-Host ""
Write-Host "查看容器状态 : docker compose ps"
Write-Host "查看日志     : docker compose logs --tail 50 api web graph-api portal"
Write-Host "导入图谱数据 : python scripts/import_v2.py data/faults_sample.json --source manual"
