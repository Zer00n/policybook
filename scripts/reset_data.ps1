# scripts/reset_data.ps1
# PolicyBook 保单簿 - 清空测试数据脚本

$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Split-Path -Parent $ScriptDir
Set-Location $RootDir

Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host "         PolicyBook 保单簿 · 重置平台测试数据           " -ForegroundColor Cyan
Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host ""

& uv run --directory "$RootDir\backend" python "$RootDir\scripts\reset_data.py"

Write-Host ""
Write-Host "数据清空完毕，平台已回归纯净初始化状态。" -ForegroundColor Green
