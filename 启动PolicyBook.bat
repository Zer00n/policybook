﻿@echo off
chcp 65001 >nul
title PolicyBook 保单簿 - 一键启动

cd /d "%~dp0"

echo 正在启动 PolicyBook 保单簿服务，请稍候...

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start.ps1" %*

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo 服务启动异常退出，错误代码：%ERRORLEVEL%
    pause
)
