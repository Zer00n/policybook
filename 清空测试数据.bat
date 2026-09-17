@echo off
chcp 65001 >nul
title PolicyBook 保单簿 - 清空测试数据

cd /d "%~dp0"

echo 正在清空 PolicyBook 平台测试数据，请稍候...

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\reset_data.ps1" %*

echo.
pause
