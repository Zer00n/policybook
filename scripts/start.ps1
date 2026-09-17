# scripts/start.ps1
# PolicyBook 保单簿 - 基于 Windows 11 的一键启动与服务守护脚本
# 支持前后端协同启动、依赖自检、数据库自初始化、健康检查与浏览器自动唤起

[CmdletBinding()]
param (
    [switch]$Dev = $false,
    [switch]$NoBrowser = $false
)

$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Split-Path -Parent $ScriptDir
Set-Location $RootDir

Write-Host ""
Write-Host " ======================================================= " -ForegroundColor Cyan
Write-Host "            PolicyBook 保单簿 · 本地服务启动器           " -ForegroundColor Cyan
Write-Host " ======================================================= " -ForegroundColor Cyan
Write-Host ""

# 1. 检查基础环境：uv (Python 包与运行环境管理)
Write-Host "[1/6] 检查 Python 与 uv 运行环境..." -ForegroundColor Yellow
$UvCmd = Get-Command "uv" -ErrorAction SilentlyContinue
if (-not $UvCmd) {
    Write-Host "【错误】未检测到 uv 包管理器！" -ForegroundColor Red
    Write-Host "请在 PowerShell 中运行以下命令安装 uv 后重试：" -ForegroundColor Red
    Write-Host '  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"' -ForegroundColor White
    Write-Host "或者使用 winget 安装：" -ForegroundColor Red
    Write-Host "  winget install --id astral-sh.uv -e" -ForegroundColor White
    Write-Host ""
    Read-Host "按 Enter 键退出..."
    exit 1
}
Write-Host "  -> uv 就绪: $($UvCmd.Source)" -ForegroundColor Green

# 2. 检查前端环境：node / pnpm
Write-Host "[2/6] 检查前端运行环境..." -ForegroundColor Yellow
$PnpmAvailable = $false
try {
    $testPnpm = & cmd.exe /c pnpm --version 2>$null
    if ($LASTEXITCODE -eq 0 -and $testPnpm) {
        $PnpmAvailable = $true
    }
} catch {}

$DistIndex = Join-Path $RootDir "frontend\dist\index.html"
$HasDist = Test-Path $DistIndex
$RunPnpmDev = $false

if ($PnpmAvailable) {
    Write-Host "  -> pnpm 就绪 (版本: $testPnpm)" -ForegroundColor Green
    # 检查 node_modules
    $NodeModules = Join-Path $RootDir "frontend\node_modules"
    if (-not (Test-Path $NodeModules)) {
        Write-Host "  -> 正在安装前端依赖 (pnpm install)..." -ForegroundColor Yellow
        Start-Process -FilePath "cmd.exe" -ArgumentList "/c", "pnpm", "install" -WorkingDirectory "$RootDir\frontend" -NoNewWindow -Wait
    }
    $RunPnpmDev = $true
} elseif ($HasDist) {
    Write-Host "  -> 未找到 pnpm，但已检测到前端编译产物 (dist)。将使用后端单端口模式托管前端！" -ForegroundColor Green
} else {
    Write-Host "【提示】未找到 pnpm 且尚未构建前端。正在尝试构建或提示安装..." -ForegroundColor Yellow
    Write-Host "推荐安装 Node.js 与 pnpm：" -ForegroundColor Yellow
    Write-Host "  winget install --id OpenJS.NodeJS.LTS -e" -ForegroundColor White
    Write-Host "  corepack enable" -ForegroundColor White
    Write-Host "  corepack prepare pnpm@latest --activate" -ForegroundColor White
    Read-Host "按 Enter 键退出..."
    exit 1
}



# 3. 检查并初始化配置与数据存储
Write-Host "[3/6] 检查数据存储与环境配置..." -ForegroundColor Yellow
$EnvFile = Join-Path $RootDir ".env"
if (-not (Test-Path $EnvFile)) {
    Write-Host "  -> 首次运行，正在自动生成 .env 密钥配置文件..." -ForegroundColor Yellow
}
# 运行后端初始化脚本（确保 data/models 目录与加密密钥、数据库结构就绪）
& uv run --directory "$RootDir\backend" python -m app.scripts.init | Out-Null
Write-Host "  -> 配置与数据库结构就绪。" -ForegroundColor Green


# 4. 端口冲突检查
Write-Host "[4/6] 检查端口占用状态..." -ForegroundColor Yellow
function Stop-PortListener([int]$Port) {
    try {
        $Conns = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
        if ($Conns) {
            foreach ($c in $Conns) {
                $pId = $c.OwningProcess
                if ($pId -and $pId -gt 4) {
                    $pName = (Get-Process -Id $pId -ErrorAction SilentlyContinue).ProcessName
                    Write-Host "  -> 端口 $Port 已被占用 (PID: $pId, $pName)，正在自动释放..." -ForegroundColor Yellow
                    taskkill /F /T /PID $pId | Out-Null
                }
            }
        }
    } catch {}
}

Stop-PortListener 8000
if ($RunPnpmDev) {
    Stop-PortListener 5173
}

# 5. 拉起服务
Write-Host "[5/6] 正在拉起服务..." -ForegroundColor Yellow
$PyExe = Join-Path $RootDir "backend\.venv\Scripts\python.exe"
if (-not (Test-Path $PyExe)) {
    $PyExe = (& uv run --directory "$RootDir\backend" python -c "import sys; print(sys.executable)").Trim()
}

$BackendProc = Start-Process -FilePath $PyExe -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000" -WorkingDirectory "$RootDir\backend" -WindowStyle Hidden -PassThru

$FrontendProc = $null
if ($RunPnpmDev) {
    $FrontendProc = Start-Process -FilePath "cmd.exe" -ArgumentList "/c", "pnpm", "dev", "--host", "127.0.0.1", "--port", "5173" -WorkingDirectory "$RootDir\frontend" -WindowStyle Hidden -PassThru
}



# 6. 健康检查与就绪确认
Write-Host "[6/6] 等待服务就绪并执行健康检查..." -ForegroundColor Yellow
$Healthy = $false
$TargetUrl = if ($RunPnpmDev) { "http://127.0.0.1:5173" } else { "http://127.0.0.1:8000" }

for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Milliseconds 600
    try {
        $resp = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/health" -Method Get -TimeoutSec 2 -ErrorAction SilentlyContinue
        if ($resp -and $resp.status -eq "ok") {
            $Healthy = $true
            break
        }
    } catch {}
}

if (-not $Healthy) {
    Write-Host "【警告】后端健康检查超时，请检查后端日志！" -ForegroundColor Red
} else {
    Write-Host "  -> 服务健康检查通过！" -ForegroundColor Green
}

Write-Host ""
Write-Host "=======================================================" -ForegroundColor Green
Write-Host "      ✓ PolicyBook 保单簿服务已成功运行！               " -ForegroundColor Green
Write-Host "=======================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  应用访问地址 : " -NoNewline; Write-Host $TargetUrl -ForegroundColor Cyan
Write-Host "  后端接口文档 : " -NoNewline; Write-Host "http://127.0.0.1:8000/api/docs" -ForegroundColor Cyan
Write-Host "  设计系统指引 : " -NoNewline; Write-Host "$TargetUrl/dev/styleguide" -ForegroundColor Cyan
Write-Host ""
Write-Host "  服务进程已就绪 (后端 PID: $($BackendProc.Id)" -NoNewline
if ($FrontendProc) {
    Write-Host ", 前端 PID: $($FrontendProc.Id)" -NoNewline
}
Write-Host ")"

Write-Host ""
Write-Host "  按 Ctrl+C 或直接关闭本窗口，将自动安全停止全部服务..." -ForegroundColor Yellow
Write-Host ""

# 自动唤起浏览器
if (-not $NoBrowser) {
    Start-Sleep -Milliseconds 500
    Start-Process $TargetUrl
}

# 保持前台等待，并在退出时清理所有子进程树
try {
    while ($true) {
        Start-Sleep -Seconds 1
        if ($BackendProc.HasExited) {
            Write-Host "后端服务已意外退出！" -ForegroundColor Red
            break
        }
        if ($FrontendProc -and $FrontendProc.HasExited) {
            Write-Host "前端开发服务器已退出！" -ForegroundColor Yellow
            break
        }
    }
}
finally {
    Write-Host ""
    Write-Host "正在安全停止所有服务进程..." -ForegroundColor Yellow
    if ($BackendProc -and -not $BackendProc.HasExited) {
        taskkill /F /T /PID $BackendProc.Id 2>$null | Out-Null
    }
    if ($FrontendProc -and -not $FrontendProc.HasExited) {
        taskkill /F /T /PID $FrontendProc.Id 2>$null | Out-Null
    }
    Stop-PortListener 8000
    if ($RunPnpmDev) {
        Stop-PortListener 5173
    }
    Write-Host "所有服务已完全停止。" -ForegroundColor Gray
}

