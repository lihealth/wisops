# WisOps 停止脚本
# 用法：
#   .\stop.ps1               # 停止并移除核心服务容器（保留数据卷）
#   .\stop.ps1 -Graph        # 同上（兼容 start.ps1 参数习惯）
#   .\stop.ps1 -WithVolumes  # 停止并移除容器+网络+数据卷（危险操作）

param(
    [switch]$Graph,
    [switch]$WithVolumes
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "=== WisOps 停止 ===" -ForegroundColor Cyan

if ($WithVolumes) {
    Write-Host "[WARN] 即将删除容器和数据卷（不可恢复）..." -ForegroundColor Yellow
    docker compose --profile graph down -v
} else {
    docker compose --profile graph down
}

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] 停止失败，请检查：docker compose ps" -ForegroundColor Red
    exit 1
}

Write-Host "服务已停止。" -ForegroundColor Green
if ($WithVolumes) {
    Write-Host "数据卷已删除（含 PostgreSQL/Qdrant/HugeGraph 数据）。" -ForegroundColor Yellow
} else {
    Write-Host "数据卷已保留，可随时重新启动。" -ForegroundColor Green
}

# WisOps 停止脚本
# 用法：
#   .\stop.ps1           # 停止所有容器（保留数据卷）
#   .\stop.ps1 -Clean    # 停止并删除容器（保留数据卷）

param(
    [switch]$Clean
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "=== WisOps 停止 ===" -ForegroundColor Cyan

if ($Clean) {
    Write-Host "停止并删除所有容器（数据卷保留）..." -ForegroundColor Yellow
    docker compose --profile graph down
} else {
    Write-Host "停止所有容器..." -ForegroundColor Yellow
    docker compose --profile graph stop
}

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] 停止失败，请手动执行：docker compose down" -ForegroundColor Red
    exit 1
}

Write-Host "=== 所有服务已停止 ===" -ForegroundColor Green
Write-Host ""
Write-Host "数据卷已保留，重新启动请运行：.\start.ps1"
if ($Clean) {
    Write-Host "注意：容器已删除，下次启动会重新创建容器"
}
