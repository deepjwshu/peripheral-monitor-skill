# 📦 外设监控 Skill 发布包 - 交付物清单

> 版本: v1.0.0
> 发布日期: 2026-02-10
> 状态: ✅ 完成交付

---

## 🎯 交付物总览

本次交付包含完整的"外设新品监控报告生成系统"，支持一键安装和运行。

### 核心功能

- ✅ 数据采集（in外设、外设天下）
- ✅ 智能清洗与去重
- ✅ LLM PM 深度分析（DeepSeek V3）
- ✅ 自动合并相同产品
- ✅ 极客风 HTML 报告生成
- ✅ 自动校验（缺失关键组件直接失败）

---

## 📋 完整文件清单

### 1️⃣ 文档文件 (4 个)

| 文件 | 行数 | 说明 |
|------|------|------|
| **README.md** | ~350 | 用户手册：安装、配置、使用、常见问题 |
| **SKILL_SPEC.md** | ~700 | 技术规范：流程、Schema、校验、扩展点 |
| **ONE_COMMAND_RUN.md** | ~250 | 一键运行指南：从安装到生成的完整命令 |
| **FILE_STRUCTURE.md** | ~400 | 目录结构说明：发布包组织、打包流程 |

### 2️⃣ 核心程序 (3 个)

| 文件 | 大小 | 说明 |
|------|------|------|
| **etl_pipeline.py** | ~150KB | 主程序：ETL + LLM分析 + 报告生成 |
| **spider.py** | ~20KB | 爬虫程序（可选，可使用已有数据） |
| **config.py** | ~2KB | 配置文件：目标年月、输出路径 |

### 3️⃣ 配置与依赖 (3 个)

| 文件 | 说明 |
|------|------|
| **requirements.txt** | Python 依赖清单（requests, pandas, beautifulsoup4 等） |
| **.env.example** | 环境变量示例（LLM API 配置、并发数等） |
| **.gitignore** | Git 忽略规则（保护敏感信息） |

### 4️⃣ 脚本工具 (3 个)

| 文件 | 说明 |
|------|------|
| **scripts/validate_report.py** | 报告校验脚本（检查必需组件） |
| **scripts/install.sh** | 一键安装脚本（Linux/macOS） |
| **scripts/install.bat** | 一键安装脚本（Windows） |

### 5️⃣ 示例文件 (2 个)

| 文件 | 说明 |
|------|------|
| **examples/input_example.json** | 输入数据示例（2个产品） |
| **examples/QUICKSTART.md** | 快速开始指南 |

---

## 📊 统计信息

```
总文件数: 15 个
总代码行数: ~15,000 行（含注释和文档）
总文档字数: ~50,000 字
压缩包大小: ~230 KB（不含输出文件）
```

---

## 🎓 使用契约

### 输入约定

| 项目 | 说明 |
|------|------|
| **输入文件** | `output/report_data_YYYY_MM.json` |
| **文件格式** | JSON 数组，包含 title, source, url, publish_date, content_text |
| **最低数量** | 1 条记录 |
| **推荐数量** | 10-100 条记录 |

### 输出约定

| 项目 | 说明 |
|------|------|
| **主报告** | `output/monthly_report_YYYY_MM.html` |
| **数据文件** | `output/processed_products.json` |
| **校验结果** | 控制台输出 + 退出码（0=成功，1=失败） |

### 环境要求

| 项目 | 要求 |
|------|------|
| **Python** | >= 3.9 |
| **操作系统** | Windows / macOS / Linux |
| **LLM API** | DeepSeek V3 或兼容 API |
| **内存** | >= 2GB（推荐 4GB） |
| **网络** | 需访问 LLM API |

---

## 🔧 配置项说明

### 必需配置（.env）

```bash
LLM_API_KEY=sk-your-api-key-here      # LLM API 密钥
LLM_API_BASE=https://api.deepseek.com/v1  # API 端点
LLM_MODEL=deepseek-chat               # 模型名称
```

### 可选配置（.env）

```bash
TARGET_YEAR=2026                      # 目标年份
TARGET_MONTH=1                        # 目标月份
MAX_WORKERS=10                        # 并发 LLM 请求数
TEMPLATE_MODE=pm_deep                 # 报告模板模式
DEBUG=false                           # 调试模式
```

---

## 🚀 快速开始（3 步）

### 步骤 1: 安装

```bash
# Linux/macOS
bash scripts/install.sh

# Windows
scripts\install.bat
```

### 步骤 2: 配置

```bash
# 复制配置文件
cp .env.example .env

# 编辑并填入 API Key
nano .env  # 或 notepad .env
```

### 步骤 3: 运行

```bash
# 使用示例数据
cp examples/input_example.json output/report_data_2026_01.json

# 生成报告
python etl_pipeline.py --template pm_deep

# 查看报告
open output/monthly_report_2026_01.html
```

---

## ✅ 校验规则

### 必需组件（缺一不可）

| 组件 ID | 说明 | 检测方式 |
|---------|------|---------|
| `nav-bar` | 导航栏 | `id="nav-bar" in html` |
| `searchInput` | 搜索框 | `id="searchInput" in html` |
| `product-overview` | 产品概览 | `class="product-overview" in html` |
| `product-specs` | 硬核参数 | `class="product-specs" in html` |
| `product-analysis` | PM 洞察 | `class="product-analysis" in html` |
| `PM 深度洞察` | 标题文本 | `"PM 深度洞察" in html` |

### 校验命令

```bash
# 自动校验（报告生成后自动执行）
python etl_pipeline.py --validate-only --report-path output/monthly_report_2026_01.html

# 手动校验
python scripts/validate_report.py output/monthly_report_2026_01.html --strict
```

---

## 🔍 Schema 定义

### 鼠标 Top 15 Schema

```json
{
  "product_pricing": "产品与定价",
  "mold_lineage": "模具血统",
  "weight_center": "重量与重心",
  "sensor_solution": "传感器方案",
  "mcu_chip": "主控芯片",
  "polling_rate": "回报率配置",
  "end_to_end_latency": "全链路延迟",
  "switch_features": "微动特性",
  "scroll_encoder": "滚轮编码器",
  "coating_process": "涂层工艺",
  "high_refresh_battery": "高刷续航",
  "structure_quality": "结构做工",
  "feet_config": "脚贴配置",
  "wireless_interference": "无线抗干扰",
  "driver_experience": "驱动体验"
}
```

### 键盘 Top 15 Schema

```json
{
  "product_layout": "产品与配列",
  "structure_form": "结构形式",
  "tech_route": "技术路线",
  "rt_params": "RT参数",
  "sound_dampening": "声音包填充",
  "switch_details": "轴体详解",
  "measured_latency": "实测延迟",
  "keycap_craftsmanship": "键帽工艺",
  "bigkey_tuning": "大键调校",
  "pcb_features": "PCB特性",
  "case_craftsmanship": "外壳工艺",
  "front_height": "前高数据",
  "battery_efficiency": "电池效率",
  "connection_storage": "连接与收纳",
  "software_support": "软体支持"
}
```

---

## 🐛 故障排查手册

### 问题 1: LLM API 连接失败

```
[ERROR] 504 Server Error: Gateway Time-out
```

**解决方案**：
1. 检查 API 配置：`curl $LLM_API_BASE/v1/models`
2. 确认 API Key 有效
3. 增加超时时间：`export LLM_TIMEOUT=180`

### 问题 2: 图表显示"未知"

```
所有传感器显示为"未知"
```

**解决方案**：
1. 启用 DEBUG 模式：`export DEBUG=true`
2. 查看 `[DEBUG-LLM]` 日志
3. 确认 LLM 返回 `sensor_solution` 字段

### 问题 3: 报告校验失败

```
[FAIL] HTML报告校验失败！缺少以下关键组件
```

**解决方案**：
1. 确认使用 `--template pm_deep`
2. 检查 LLM 返回的数据是否完整
3. 查看完整错误日志

### 问题 4: 内存不足

```
MemoryError
```

**解决方案**：
1. 减少并发数：`export MAX_WORKERS=5`
2. 分批处理数据
3. 增加系统内存

---

## 📞 支持与反馈

- **文档**: 参考 README.md, SKILL_SPEC.md, ONE_COMMAND_RUN.md
- **示例**: 参考 examples/QUICKSTART.md
- **问题**: 提交 GitHub Issue

---

## 📄 许可证

MIT License

---

## ✨ 更新日志

### v1.0.0 (2026-02-10)

- ✅ 初始版本发布
- ✅ 完整的 ETL 流程
- ✅ LLM PM 深度分析
- ✅ PM 深度分析版模板
- ✅ 自动校验功能
- ✅ 完整文档和示例

---

## 🎉 致谢

感谢所有测试和反馈的用户！

---

**生成时间**: 2026-02-10
**工具版本**: Claude Code (Sonnet 4.5)
**作者**: Peripheral Monitor Team
