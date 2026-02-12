#!/bin/bash
# 一键安装脚本 (Linux/macOS) - v2.0 with venv support

set -e  # 遇到错误立即退出

echo "============================================================"
echo "外设新品监控报告生成系统 - 一键安装 v2.0"
echo "============================================================"

# 检查 Python 版本
echo "[1/6] 检查 Python 版本..."
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] 未找到 Python3，请先安装 Python 3.9 或更高版本"
    echo "下载地址: https://www.python.org/downloads/"
    exit 1
fi

python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "检测到 Python 版本: $python_version"

# 检查是否满足最低版本要求
if ! python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" 2>/dev/null; then
    echo "[ERROR] Python 版本过低，需要 Python 3.9 或更高版本"
    exit 1
fi

echo "[OK] Python 版本满足要求"

# 创建虚拟环境（强制）
echo ""
echo "[2/6] 创建虚拟环境..."
if [ -d "venv" ]; then
    echo "[SKIP] 虚拟环境已存在，删除后重新创建？"
    read -p "删除并重建？[y/N] " recreate
    if [ "$recreate" = "y" ] || [ "$recreate" = "Y" ]; then
        rm -rf venv
        python3 -m venv venv
        echo "[OK] 虚拟环境已重建"
    else
        echo "[INFO] 使用现有虚拟环境"
    fi
else
    python3 -m venv venv
    echo "[OK] 虚拟环境已创建"
fi

# 激活虚拟环境
source venv/bin/activate
echo "[OK] 虚拟环境已激活"

# 升级 pip
echo ""
echo "[3/6] 升级 pip..."
pip install --upgrade pip setuptools wheel
echo "[OK] pip 已升级"

# 安装依赖
echo ""
echo "[4/6] 安装 Python 依赖..."
pip install -r requirements.txt
echo "[OK] 依赖安装完成"

# 创建配置文件
echo ""
echo "[5/6] 创建配置文件..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo "[OK] 已创建 .env 配置文件"
    echo ""
    echo "请编辑 .env 文件，填入你的 LLM API Key："
    echo "  nano .env"
    echo "  或"
    echo "  vim .env"
else
    echo "[SKIP] .env 文件已存在"
fi

# 创建输出和日志目录
echo ""
echo "[6/6] 创建输出和日志目录..."
mkdir -p output logs
echo "[OK] 目录已创建"

# 安装完成
echo ""
echo "============================================================"
echo "安装完成！"
echo "============================================================"
echo ""
echo "下一步："
echo "1. 编辑 .env 文件，填入你的 LLM API Key"
echo "2. 激活虚拟环境（如果需要重新激活）："
echo "   source venv/bin/activate"
echo "3. 准备输入数据："
echo "   cp examples/input_example.json output/report_data_2026_01.json"
echo "4. 生成报告："
echo "   python etl_pipeline.py --month 2026-01"
echo ""
echo "查看帮助："
echo "  python etl_pipeline.py --help"
echo ""
