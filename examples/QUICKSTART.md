# 快速开始示例

本目录包含示例配置和输入/输出文件，帮助你快速上手。

## 📁 文件说明

### input_example.json
示例输入数据文件，包含2个产品（1个鼠标、1个键盘）。

**使用方法**：
```bash
# 1. 将示例数据复制到输出目录
cp examples/input_example.json output/report_data_2026_01.json

# 2. 运行 ETL 生成报告
python etl_pipeline.py --template pm_deep

# 3. 查看生成的报告
open output/monthly_report_2026_01.html
```

### config_example.env
示例配置文件，展示所有可配置项。

**使用方法**：
```bash
# 1. 复制示例配置
cp config_example.env .env

# 2. 编辑配置文件
nano .env  # 或使用其他编辑器

# 3. 填入你的 API Key
LLM_API_KEY=your_actual_api_key_here

# 4. 运行程序
python etl_pipeline.py
```

## 🎯 完整工作流示例

### 示例 1: 使用示例数据生成报告

```bash
# 步骤 1: 准备输入数据
cp examples/input_example.json output/report_data_2026_01.json

# 步骤 2: 配置环境变量
export LLM_API_KEY=sk-your-api-key
export LLM_API_BASE=https://api.deepseek.com/v1
export LLM_MODEL=deepseek-chat

# 步骤 3: 生成报告
python etl_pipeline.py --template pm_deep

# 步骤 4: 校验报告
python scripts/validate_report.py output/monthly_report_2026_01.html

# 步骤 5: 查看报告
# macOS
open output/monthly_report_2026_01.html
# Linux
xdg-open output/monthly_report_2026_01.html
# Windows
start output/monthly_report_2026_01.html
```

### 示例 2: 使用爬虫采集数据并生成报告

```bash
# 步骤 1: 运行爬虫采集数据
python spider.py

# 步骤 2: 确认数据已生成
ls -lh output/report_data_2026_01.json

# 步骤 3: 生成报告
python etl_pipeline.py --template pm_deep

# 步骤 4: 校验报告
python scripts/validate_report.py output/monthly_report_2026_01.html
```

### 示例 3: 仅校验已有报告

```bash
# 校验报告完整性
python etl_pipeline.py --validate-only --report-path output/monthly_report_2026_01.html

# 或使用独立校验脚本
python scripts/validate_report.py output/monthly_report_2026_01.html --strict
```

## 📊 预期输出

### 成功运行后的控制台输出

```
============================================================
外设新品监控报告生成系统 (Phase 4 最终优化版)
模板模式: PM深度分析版（完整三栏布局 + nav-bar + 搜索）
PM 深度分析版 | 产品去重合并 | 交互优化
============================================================

[步骤 1/5] 数据预处理与清洗
[OK] 加载原始数据: 2 条记录
[OK] 关键词筛选: 2 条记录
...

[步骤 2/5] LLM PM 深度分析（并发模式）
...

[步骤 3/5] 生成 HTML 报告
[OK] HTML 报告已生成: output/monthly_report_2026_01.html

============================================================
执行生成后校验...
============================================================

[校验] 检查HTML报告: output/monthly_report_2026_01.html
[OK] 所有关键组件校验通过:
  ✓ nav-bar: 导航栏（包含快速跳转和搜索框）
  ✓ searchInput: 搜索输入框
  ✓ product-overview: 产品概览模块（左栏）
  ✓ product-specs: 硬核参数模块（中栏）
  ✓ product-analysis: PM深度洞察模块（右栏）
  ✓ PM 深度洞察: PM深度洞察标题
```

### 生成的文件

```
output/
├── monthly_report_2026_01.html      # 主报告（PM 深度分析版）
├── processed_products.json          # 处理后的产品数据
└── report_data_2026_01.json         # 原始输入数据
```

## 🔧 自定义配置

### 修改目标年月

**方法 1: 环境变量**
```bash
export TARGET_YEAR=2026
export TARGET_MONTH=2
python etl_pipeline.py
```

**方法 2: 直接修改 config.py**
```python
TARGET_YEAR = 2026
TARGET_MONTH = 2
```

### 修改并发数

```bash
export MAX_WORKERS=20  # 增加并发
python etl_pipeline.py
```

### 切换模板

```bash
# 生成简化版报告
python etl_pipeline.py --template simple
```

## ❓ 常见问题

### Q: 如何使用自己的数据？

A: 将你的数据按照 `input_example.json` 的格式保存为 JSON 文件，然后放置到 `output/report_data_YYYY_MM.json`。

### Q: 如何仅校验报告不重新生成？

A: 使用 `--validate-only` 参数：
```bash
python etl_pipeline.py --validate-only --report-path output/monthly_report_2026_01.html
```

### Q: LLM API 连接失败怎么办？

A: 检查以下配置：
1. `.env` 文件中的 `LLM_API_BASE` 是否正确
2. `LLM_API_KEY` 是否有效
3. 网络是否可访问 API 端点

### Q: 如何调试字段映射问题？

A: 启用 DEBUG 模式：
```bash
export DEBUG=true
python etl_pipeline.py
```

## 📞 获取帮助

```bash
# 查看完整帮助
python etl_pipeline.py --help

# 查看示例配置
cat config_example.env

# 查看校验脚本帮助
python scripts/validate_report.py --help
```
