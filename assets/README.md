# 静态资源说明

本系统需要以下静态资源：

## Chart.js (必需)

**版本**: 4.4.0

### 自动下载（推荐）

```bash
# Linux/macOS
bash scripts/download_assets.sh

# Windows
scripts\download_assets.bat
```

### 手动下载

如果自动下载失败，请按以下步骤手动下载：

1. 访问 Chart.js 官网或 CDN：
   - https://www.chartjs.org/docs/latest/getting-started/installation.html
   - 或直接下载: https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js

2. 保存到：`assets/js/chart.umd.min.js`

### 目录结构

```
assets/
└── js/
    └── chart.umd.min.js    # Chart.js 库 (必需)
```

## 验证

检查文件是否存在：

```bash
# Linux/macOS
ls -lh assets/js/chart.umd.min.js

# Windows
dir assets\js\chart.umd.min.js
```

预期大小：约 200 KB
