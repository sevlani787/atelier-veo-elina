@echo off
chcp 65001 >nul
title Atelier VEO - Boardroom Server

echo ============================================================
echo    ATELIER VEO - EXECUTIVE BOARDROOM SERVER
echo    Address: http://localhost:8080/boardroom
echo ============================================================
echo.

:: Free port 8080 if an old stuck process is lingering
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8080 ^| findstr LISTENING') do (
    taskkill /f /pid %%a >nul 2>&1
)

cd /d "D:\Antigravity\Элин"
python -m admin.app
