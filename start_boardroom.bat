@echo off
chcp 65001 >nul
title Atelier VEO | Executive Boardroom Server
echo ============================================================
echo    ATELIER VEO ^| VEO BOARDROOM SERVER
echo    Адрес Зала: http://localhost:8080/boardroom
echo ============================================================
echo.
cd /d "D:\Antigravity\Элин"
python -m admin.app
pause
