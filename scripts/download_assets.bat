@echo off
REM 下载静态资源脚本 (Windows)

echo ============================================================
echo 下载静态资源
echo ============================================================

set ASSETS_DIR=assets
set JS_DIR=%ASSETS_DIR%\js

if not exist %ASSETS_DIR% mkdir %ASSETS_DIR%
if not exist %JS_DIR% mkdir %JS_DIR%

echo.
echo [1/1] 下载 Chart.js...
set CHART_VERSION=4.4.0
set CHART_URL=https://cdn.jsdelivr.net/npm/chart.js@%CHART_VERSION%/dist/chart.umd.min.js

curl -L -o %JS_DIR%\chart.umd.min.js %CHART_URL%
if errorlevel 1 (
    echo [ERROR] Chart.js 下载失败
    echo.
    echo 请手动下载：
    echo 1. 访问: https://www.chartjs.org/docs/latest/getting-started/installation.html
    echo 2. 下载 Chart.js 4.4.0 到: %JS_DIR%\chart.umd.min.js
    echo.
    echo 或使用以下镜像：
    echo   wget %CHART_URL% -O %JS_DIR%\chart.umd.min.js
    pause
    exit /b 1
)

echo [OK] Chart.js 已下载到: %JS_DIR%\chart.umd.min.js
echo.
echo ============================================================
echo 下载完成！
echo ============================================================
pause
