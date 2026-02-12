#!/bin/bash
# 下载静态资源脚本

echo "============================================================"
echo "下载静态资源"
echo "============================================================"

ASSETS_DIR="assets"
JS_DIR="$ASSETS_DIR/js"

mkdir -p "$JS_DIR"

echo ""
echo "[1/1] 下载 Chart.js..."
CHART_VERSION="4.4.0"
CHART_URL="https://cdn.jsdelivr.net/npm/chart.js@$CHART_VERSION/dist/chart.umd.min.js"

if curl -L -o "$JS_DIR/chart.umd.min.js" "$CHART_URL"; then
    echo "[OK] Chart.js 已下载到: $JS_DIR/chart.umd.min.js"
else
    echo "[ERROR] Chart.js 下载失败"
    echo ""
    echo "请手动下载："
    echo "1. 访问: https://www.chartjs.org/docs/latest/getting-started/installation.html"
    echo "2. 下载 Chart.js 4.4.0 到: $JS_DIR/chart.umd.min.js"
    echo ""
    echo "或使用以下镜像："
    echo "  wget $CHART_URL -O $JS_DIR/chart.umd.min.js"
    exit 1
fi

echo ""
echo "============================================================"
echo "下载完成！"
echo "============================================================"
