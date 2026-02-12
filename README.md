## 一键安装（拿链接就能用）

把本仓库克隆到 Claude Code 的 skills 目录后即可使用。

### Windows（PowerShell）
```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\.claude\skills" | Out-Null
git clone https://github.com/deepjwshu/peripheral-monitor-skill.git "$env:USERPROFILE\.claude\skills\peripheral-monitor-skill"
```

### macOS / Linux
```bash
mkdir -p ~/.claude/skills
git clone https://github.com/deepjwshu/peripheral-monitor-skill.git ~/.claude/skills/peripheral-monitor-skill
```

### 使用方式

确保你的 Skill 入口文件存在：`SKILL.md`

在 Claude Code 中输入：`/peripheral-monitor-skill`（以 SKILL.md 中的 name 为准）

---

# 外设新品监控报告生成系统 (Peripheral Monitor Skill)

> 一键生成专业级外设新品 PM 深度分析 HTML 报告

---

## ⚡ Claude Code 最快使用方式

> 使用 Claude Code？只需一句话或一个命令即可生成报告！

### 一句话触发
```
调研2026年1月份的键鼠新品
```

### Slash 命令
```
/research 2026-01
```

### 首次使用配置（仅一次）

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置环境变量
copy .env.example .env  # Windows
# cp .env.example .env  # Linux/macOS

# 3. 编辑 .env 文件，填入你的 LLM API Key
# LLM_API_KEY=sk-your-api-key-here
# LLM_API_BASE=https://api.deepseek.com/v1
# LLM_MODEL=deepseek-chat
```

**配置完成后，直接在 Claude Code 中输入"调研某月新品"即可！**

---

## 🎯 功能概述

本系统自动化完成"每月键鼠新品调研 → PM 深度分析 → HTML 报告生成"全流程：

1. **数据采集**：从 in外设、外设天下等平台爬取新品资讯
2. **智能清洗**：去重、分类、提取关键信息
3. **LLM 深度分析**：基于 DeepSeek V3 进行 PM 视角的产品分析
4. **自动合并**：合并相同产品的多条报道
5. **极客风报告**：生成包含交互式图表的深色主题 HTML 报告
6. **自动校验**：验证报告完整性，缺失关键组件直接失败

### 报告特性

- ✅ **完整三栏布局**：产品概览 | 硬核参数 | PM 深度洞察
- ✅ **交互式导航**：快速跳转 + 实时搜索
- ✅ **数据可视化**：传感器分布、价格区间、品类占比
- ✅ **移动端适配**：响应式设计
- ✅ **PM 级分析**：竞品对比、目标用户、优缺点评估、购买建议

---

## 📦 快速开始

### 1. 环境要求

```bash
# Python 版本
Python 3.9 - 3.12（⚠️ 避免使用 3.14）
Windows 推荐使用 3.11/3.12

# 操作系统
Windows / macOS / Linux

# 运行目录（重要！）
⚠️ 必须在项目根目录运行（包含 etl_pipeline.py 的那层）
```

### 运行兼容性说明

| 项目 | 要求 |
|------|------|
| **运行目录** | 必须在项目根目录（包含 `etl_pipeline.py`） |
| **Python 版本** | 3.9 - 3.12（Windows 推荐 3.11/3.12，避免 3.14） |
| **虚拟环境** | 推荐使用 `.venv`，首次运行需创建 |
| **首次配置** | 需执行 install 脚本或手动安装 requirements.txt |
| **本地资源** | 如需离线图表，先运行 `scripts/download_assets.bat`（Windows）或 `bash scripts/download_assets.sh`（Unix） |

**Python 路径优先级**（按优先级排序）：
1. `.venv\Scripts\python.exe`（Windows 虚拟环境）
2. `.venv/bin/python`（Unix 虚拟环境）
3. `python`（系统默认）

### 2. 一键安装

```bash
# 克隆或下载项目
cd peripheral-monitor-skill

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 文件，填入你的 API Key
```

### 3. 准备输入数据

**方式一：使用爬虫采集（推荐）**

```bash
# 采集指定年月的新品数据
python spider.py
# 输出：output/report_data_2026_01.json
```

**方式二：使用已有数据**

将你的数据文件放置到 `output/report_data_YYYY_MM.json`，格式如下：

```json
[
  {
    "title": "罗技G Pro X Superlight 2 游戏鼠标发布",
    "source": "in外设",
    "url": "https://www.example.com/article-123",
    "publish_date": "2026-01-15",
    "content_text": "罗技今日发布了G Pro X Superlight 2..."
  }
]
```

### 4. 生成报告

```bash
# 一键模式：爬取 + 生成报告（推荐）
python etl_pipeline.py --month 2026-01 --fetch --template pm_deep

# 基础用法（使用默认配置）
python etl_pipeline.py

# 指定模板和年月
python etl_pipeline.py --template pm_deep

# 仅校验已有报告
python etl_pipeline.py --validate-only --report-path output/monthly_report_2026_01.html
```

### 5. 查看报告

报告生成位置：`output/monthly_report_YYYY_MM.html`

直接在浏览器中打开即可查看。

### 6. 验收步骤

生成报告后，请执行以下验收步骤以确保数据质量和报告完整性：

#### 6.1 基础验收（必做）

```bash
# 1. 使用内置校验工具验证报告结构
python etl_pipeline.py --validate-only --report-path output/monthly_report_2026_01.html
```

**预期输出**：
```
[OK] 报告结构校验通过
  - 品类占比分布 ✓
  - 鼠标传感器分布 ✓
  - 价格区间分布 ✓
  - 产品卡片组件 ✓
  - 宏观洞察板块 ✓
```

#### 6.2 数据质量检查（推荐）

查看生成报告时的控制台输出，确认无 **WARNING** 警告：

**正常输出示例**：
```
[OK] HTML 报告已生成: output/monthly_report_2026_01.html
```

**警告示例（需注意）**：
```
[WARNING] 数据质量警告:
  ⚠️  传感器数据覆盖率为 0%，所有鼠标产品的传感器信息缺失
  ⚠️  价格数据质量差：未公开占比 >80% (5/20)
============================================================
建议：请检查输入数据质量，确保关键字段（sensor_solution、product_pricing）正确提取
```

#### 6.3 可视化验收（手动）

在浏览器中打开 HTML 报告，检查以下内容：

1. **图表标题显示覆盖率**：如"鼠标传感器分布 (15/20)"
   - 格式：`(已提取数量/总数量)`
   - 覆盖率应 ≥ 50%，否则数据质量较差

2. **图表数据分布**：
   - 传感器分布：应显示 PAW3395、PAW3950、Hero系列等具体型号
   - 价格区间：应显示 0-199元、200-499元 等区间分布
   - 如果"未知"或"未公开"占比过高（>80%），说明数据提取不完整

3. **产品卡片完整性**：
   - 左栏：产品概述（名称、价格、创新标签）
   - 中栏：Top 15 参数规格
   - 右栏：PM 深度分析（竞品对比、优缺点、购买建议）

#### 6.4 失败项日志排查

如有处理失败的产品，查看失败日志：

```bash
# 查看最新的失败项日志
ls -lt logs/failed_items_*.json | head -1 | xargs cat
```

**日志内容示例**：
```json
[
  {
    "index": 3,
    "reason": "API调用失败，已达最大重试次数: 429 Client Error: Too Many Requests",
    "product_name": "某产品名"
  }
]
```

---

## 🎮 命令行参数

### 完整参数列表

```bash
python etl_pipeline.py [选项]

选项：
  --month YYYY-MM      目标月份（格式: YYYY-MM，如 2026-01）
                       自动定位到 output/report_data_YYYY_MM.json

  --input PATH         直接指定输入文件路径（JSON 或 Excel 格式）
                       支持 .json 和 .xlsx 文件

  --template, -t {pm_deep,simple}
                        报告模板模式（默认：pm_deep）
    pm_deep      - PM深度分析版（完整三栏布局 + nav-bar + 搜索 + PM洞察）
    simple       - 简化版（仅基本信息，无PM分析）

  --fetch, --crawl     先运行爬虫采集数据，再生成报告（一键模式）
                       自动备份旧数据文件

  --validate-only      仅校验现有报告，不重新生成
  --report-path PATH   指定要校验的HTML报告路径
  --help, -h           显示帮助信息
```

### 使用示例

```bash
# 示例 1：一键模式 - 爬取 + 生成 PM 深度分析版报告（推荐）
python etl_pipeline.py --month 2026-01 --fetch --template pm_deep

# 示例 2：生成 PM 深度分析版报告（使用已有数据）
python etl_pipeline.py

# 示例 3：使用 --month 参数指定月份
python etl_pipeline.py --month 2026-01

# 示例 4：使用 --input 参数直接指定输入文件
python etl_pipeline.py --input examples/input_example_20.json

# 示例 5：生成简化版报告
python etl_pipeline.py --template simple

# 示例 6：组合使用 - 指定月份和模板
python etl_pipeline.py --month 2026-02 --template pm_deep

# 示例 7：校验已有报告
python etl_pipeline.py --validate-only --report-path output/monthly_report_2026_01.html
```

---

## 🔧 配置说明

### 环境变量 (.env)

```bash
# LLM API 配置（必需）
LLM_API_KEY=your_api_key_here
LLM_API_BASE=http://192.168.0.250:7777
LLM_MODEL=xdeepseekv3

# 或使用公开 API
# LLM_API_BASE=https://api.deepseek.com/v1
# LLM_MODEL=deepseek-chat

# MCP 搜索服务配置（可选，用于二次参数补全）
# 公司内网环境可启用，提升参数补全能力
MCP_SEARCH_ENABLED=false                    # 是否启用 MCP 搜索
MCP_BASE_URL=http://192.168.0.250:7891   # MCP 服务地址
MCP_TOKEN=your_mcp_token_here              # MCP 认证 Token
# 详见：[MCP_CONFIG.md](MCP_CONFIG.md)

# 目标年月配置
TARGET_YEAR=2026
TARGET_MONTH=1

# 调试模式
DEBUG=false
```

### config.py 配置文件

```python
# 目标配置
TARGET_YEAR = 2026
TARGET_MONTH = 1

# 输出配置
OUTPUT_DIR = 'output'
OUTPUT_EXCEL = f'report_data_{TARGET_YEAR}_{TARGET_MONTH:02d}.xlsx'
OUTPUT_JSON = f'report_data_{TARGET_YEAR}_{TARGET_MONTH:02d}.json'
```

---

## 📂 输入输出约定

### 输入文件

| 文件 | 格式 | 说明 |
|------|------|------|
| `output/report_data_YYYY_MM.json` | JSON | 爬虫采集的原始数据 |
| `output/report_data_YYYY_MM.xlsx` | Excel | 同上，Excel 格式 |

### 输出文件

| 文件 | 格式 | 说明 |
|------|------|------|
| `output/monthly_report_YYYY_MM.html` | HTML | PM 深度分析报告（主报告） |
| `output/processed_products.json` | JSON | 处理后的产品数据（包含 LLM 分析） |

---

## 🚨 常见问题

### Q1: LLM API 连接失败

**错误信息**：`504 Server Error: Gateway Time-out`

**解决方案**：
1. 检查 `LLM_API_BASE` 和 `LLM_API_KEY` 是否正确
2. 确认 API 服务可访问：`curl http://192.168.0.250:7777/v1/models`
3. 如果使用公开 API，确保网络可访问

### Q2: 图表数据显示为"未知"或"未公开"

**原因**：LLM 未能提取到相关字段

**解决方案**：
1. 检查原始数据是否包含参数信息
2. 查看控制台的 `[DEBUG-LLM]` 日志，确认 LLM 返回的 specs 字段
3. 如果持续失败，考虑启用二次搜索补全（需配置 MCP 服务）

### Q3: 报告校验失败

**错误信息**：`[FAIL] HTML报告校验失败！缺少以下关键组件`

**解决方案**：
1. 确保使用 `--template pm_deep` 参数
2. 检查 LLM 返回的数据是否包含 `specs` 和 `analysis` 字段
3. 查看完整错误日志定位具体缺失的组件

### Q4: 内存不足

**错误信息**：`MemoryError` 或程序崩溃

**解决方案**：
1. 减少并发数：修改 `etl_pipeline.py` 中的 `max_workers=10` 为更小值
2. 分批处理数据：先运行爬虫采集一个月的数据，再生成报告

---

## 📊 数据 Schema 说明

### processed_products.json 字段定义

```json
{
  "product_name": "标准化产品全名",
  "category": "鼠标 | 键盘 | 其他",
  "main_image": "产品主图URL",
  "release_price": "发布价格（如有）",
  "innovation_tags": ["创新标签1", "创新标签2"],
  "specs": {
    // 鼠标 Top 15 Schema 字段
    "product_pricing": "产品与定价",
    "mold_lineage": "模具血统",
    "weight_center": "重量与重心",
    "sensor_solution": "传感器方案",
    ...
  },
  "analysis": {
    "market_position": "产品定位",
    "competitors": "竞品对比",
    "target_audience": "目标用户",
    "selling_point": "核心卖点",
    "verdict": {
      "pros": ["优点1", "优点2"],
      "cons": ["缺点1", "缺点2"]
    },
    "pm_summary": "购买建议"
  }
}
```

### 字段缺失处理规则

- **必须字段**：`product_name`, `category`, `specs`, `analysis`
- **可选字段**：`main_image`, `release_price`, `innovation_tags`
- **specs 子字段**：允许为空字符串，但不允许缺失 key
- **analysis 子字段**：不允许为空，LLM 必须生成所有分析字段

---

## 🎨 UI 模板契约

### PM 深度分析版 (pm_deep) 必需组件

| 组件 ID | 说明 | 缺失处理 |
|---------|------|----------|
| `nav-bar` | 导航栏（快速跳转 + 搜索框） | 直接失败 |
| `searchInput` | 搜索输入框 | 直接失败 |
| `product-overview` | 产品概览模块（左栏） | 直接失败 |
| `product-specs` | 硬核参数模块（中栏） | 直接失败 |
| `product-analysis` | PM 深度洞察模块（右栏） | 直接失败 |
| `PM 深度洞察` | PM 洞察标题 | 直接失败 |

### 校验规则

```bash
# 自动校验（报告生成后自动执行）
python etl_pipeline.py --validate-only --report-path output/monthly_report_2026_01.html

# 预期输出
[OK] 所有关键组件校验通过:
  ✓ nav-bar: 导航栏（包含快速跳转和搜索框）
  ✓ searchInput: 搜索输入框
  ✓ product-overview: 产品概览模块（左栏）
  ✓ product-specs: 硬核参数模块（中栏）
  ✓ product-analysis: PM深度洞察模块（右栏）
  ✓ PM 深度洞察: PM深度洞察标题
```

---

## 📦 发布包结构

```
peripheral-monitor-skill/
├── README.md                    # 本文档（面向使用者）
├── SKILL_SPEC.md               # 技术规范（面向维护者）
├── requirements.txt            # Python 依赖清单
├── .env.example               # 环境变量示例
├── config.py                  # 配置文件
├── etl_pipeline.py            # 主程序（ETL + 报告生成）
├── spider.py                  # 爬虫程序（可选）
├── scripts/
│   ├── validate_report.py    # 报告校验脚本
│   └── install.sh            # 一键安装脚本（Linux/macOS）
├── examples/
│   ├── input_example.json    # 输入数据示例
│   └── output_example.html   # 输出报告示例
└── output/                    # 输出目录（.gitignore）
    ├── monthly_report_*.html
    └── processed_products.json
```

---

## 🔍 故障排查手册

详见 [SKILL_SPEC.md](SKILL_SPEC.md) 的"故障排查"章节。

---

## 📄 许可证

MIT License

---

## 🤝 贡献指南

欢迎提交 Issue 和 Pull Request！

---

## 📧 联系方式

如有问题，请提交 GitHub Issue。
