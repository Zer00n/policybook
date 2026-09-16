# scripts/dev.ps1
# 启动 PolicyBook 本地开发服务（同时拉起后端与前端）

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Split-Path -Parent $ScriptDir

Write-Host "=== 启动 PolicyBook 本地开发环境 ===" -ForegroundColor Cyan
Set-Location $RootDir

# 检查 .env
if (-not (Test-Path "$RootDir\.env")) {
    Write-Host "正在从 .env.example 生成 .env..." -ForegroundColor Yellow
    Copy-Item "$RootDir\.env.example" "$RootDir\.env"
}

# 启动后端
Write-Host "正在拉起后端服务 (http://127.0.0.1:8000)..." -ForegroundColor Green
$BackendJob = Start-Process -FilePath "uv" -ArgumentList "run", "uvicorn", "app.main:app", "--reload", "--port", "8000" -WorkingDirectory "$RootDir\backend" -PassThru

# 启动前端
Write-Host "正在拉起前端服务 (http://127.0.0.1:5173)..." -ForegroundColor Green
$FrontendJob = Start-Process -FilePath "pnpm" -ArgumentList "dev" -WorkingDirectory "$RootDir\frontend" -PassThru

Write-Host "前后端服务已启动！" -ForegroundColor Cyan
Write-Host "前端地址: http://127.0.0.1:5173"
Write-Host "后端地址: http://127.0.0.1:8000/api/docs"
Write-Host "设计系统指引: http://127.0.0.1:5173/dev/styleguide"
Write-Host "按 Ctrl+C 退出并将停止所有服务..." -ForegroundColor Yellow

try {
    Wait-Process -Id $BackendJob.Id, $FrontendJob.Id
}
finally {
    Write-Host "正在停止前后端服务..." -ForegroundColor Yellow
    Stop-Process -Id $BackendJob.Id -ErrorAction SilentlyContinue
    Stop-Process -Id $FrontendJob.Id -ErrorAction SilentlyContinue
    Write-Host "服务已停止。" -ForegroundColor Gray
}
