@echo off
REM 一键安装脚本 (Windows) - v2.0 with venv support

echo ============================================================
echo 外设新品监控报告生成系统 - 一键安装 v2.0
echo ============================================================
echo.

REM 检查 Python 版本
echo [1/6] 检查 Python 版本...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] 未找到 Python，请先安装 Python 3.9 或更高版本
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo 检测到 Python 版本: %PYTHON_VERSION%
echo [OK] Python 版本满足要求
echo.

REM 创建虚拟环境（强制）
echo [2/6] 创建虚拟环境...
if exist venv (
    echo [SKIP] 虚拟环境已存在
    set /p RECREATE="删除并重建？[y/N]: "
    if /i "%RECREATE%"=="y" (
        rmdir /s /q venv
        python -m venv venv
        echo [OK] 虚拟环境已重建
    ) else (
        echo [INFO] 使用现有虚拟环境
    )
) else (
    python -m venv venv
    echo [OK] 虚拟环境已创建
)

REM 激活虚拟环境
call venv\Scripts\activate.bat
echo [OK] 虚拟环境已激活
echo.

REM 升级 pip
echo [3/6] 升级 pip...
python -m pip install --upgrade pip setuptools wheel
echo [OK] pip 已升级
echo.

REM 安装依赖
echo [4/6] 安装 Python 依赖...
pip install -r requirements.txt
echo [OK] 依赖安装完成
echo.

REM 创建配置文件
echo [5/6] 创建配置文件...
if not exist .env (
    copy .env.example .env
    echo [OK] 已创建 .env 配置文件
    echo.
    echo 请编辑 .env 文件，填入你的 LLM API Key：
    echo   notepad .env
) else (
    echo [SKIP] .env 文件已存在
)
echo.

REM 创建输出和日志目录
echo [6/6] 创建输出和日志目录...
if not exist output mkdir output
if not exist logs mkdir logs
echo [OK] 目录已创建
echo.

REM 安装完成
echo ============================================================
echo 安装完成！
echo ============================================================
echo.
echo 下一步：
echo 1. 编辑 .env 文件，填入你的 LLM API Key
echo 2. 激活虚拟环境（如果需要重新激活）：
echo    venv\Scripts\activate.bat
echo 3. 准备输入数据：
echo    copy examples\input_example.json output\report_data_2026_01.json
echo 4. 生成报告：
echo    python etl_pipeline.py --month 2026-01
echo.
echo 查看帮助：
echo   python etl_pipeline.py --help
echo.
pause
