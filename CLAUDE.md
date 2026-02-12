# Claude Code 自动化指南

> 本文档定义 Claude Code 在本项目中如何理解用户意图并自动执行外设新品调研任务

---

## 用户意图识别

### 支持的自然语言表达

Claude Code 应识别以下同义表达，均触发"外设新品调研报告生成"流程：

- "调研{月份}的键鼠新品"
- "生成{月份}的外设新品报告"
- "{月份}外设新品监控"
- "分析{月份}的键鼠市场"
- "抓取{月份}的外设数据并生成报告"

### 月份格式识别与规范化

Claude Code 应支持以下月份格式，并统一规范化为 `YYYY-MM`：

| 输入格式示例 | 规范化输出 |
|-------------|-----------|
| 2026年1月 | 2026-01 |
| 2026-01 | 2026-01 |
| 2026/01 | 2026-01 |
| 2026.01 | 2026-01 |
| 2026年01月 | 2026-01 |
| 今年1月 | 根据当前年份推断 |

**规范化规则**：
1. 提取年份和月份数字
2. 月份补零（如 `1` → `01`）
3. 格式化为 `YYYY-MM`

---

## 自动执行流程

### 前置检查（必须）

在执行任务前，Claude Code 应检查以下条件：

1. **目录位置**：必须在项目根目录（包含 `etl_pipeline.py` 的目录）
   - 检查命令：`ls etl_pipeline.py`
   - 如果不存在：提示用户"请先进入项目根目录"

2. **Python 虚拟环境**：检查 `.venv` 是否存在
   - 如果存在：优先使用虚拟环境中的 Python
   - 如果不存在：提示用户"未检测到虚拟环境，建议先运行 `scripts\install.bat`（Windows）或 `bash scripts/install.sh`（Unix）"

3. **依赖安装**：检查 `requirements.txt` 是否已安装
   - 可通过尝试导入关键包验证：`try import pandas, requests, beautifulsoup4`

4. **环境变量**：检查 `.env` 文件是否存在
   - 如果不存在：提示用户"请先配置 `.env` 文件，填入 LLM API Key"

### 执行命令序列

一旦通过前置检查，执行以下命令序列：

```bash
# 步骤 1：一键爬取 + 生成报告
python etl_pipeline.py --month YYYY-MM --fetch --template pm_deep

# 步骤 2：校验报告完整性
python scripts/validate_report.py --file output/monthly_report_YYYY_MM.html
```

**Python 路径优先级**（按优先级排序）：
1. `.venv\Scripts\python.exe`（Windows 虚拟环境）
2. `.venv/bin/python`（Unix 虚拟环境）
3. `python`（系统默认）

---

## 成功输出格式

### 标准成功输出

执行成功后，Claude Code 必须在对话中输出以下信息：

```
✅ 外设新品调研报告已生成！

📊 数据概况：
  - 抓取记录数：{N} 条
  - 去重后产品数：{M} 款

📄 报告路径：output/monthly_report_YYYY_MM.html

🚀 快速查看：
  - Windows：start output/monthly_report_YYYY_MM.html
  - macOS：open output/monthly_report_YYYY_MM.html
  - Linux：xdg-open output/monthly_report_YYYY_MM.html
```

### 带警告的成功输出

如果存在数据覆盖率警告（如"未知"占比 >80%），应额外提示：

```
⚠️ 数据覆盖率警告：
  - 传感器数据覆盖率：{X}%
  - 价格数据覆盖率：{Y}%
  - 部分产品可能存在信息缺失，请在报告中查看具体详情

📋 查看失败项日志：
  - 日志路径：logs/failed_items_*.json
  - 如需补充数据，可手动编辑 output/processed_products.json 后重新生成
```

---

## 失败处理

### 失败类型与输出

#### 1. 爬虫未采集到数据

**错误信息**：
```
❌ 爬取失败：未采集到任何数据

可能原因：
  1. 目标月份 {YYYY-MM} 可能没有新品发布
  2. 网络连接问题，请检查：
     - 目标网站是否可访问（inwaishe.com, wstx.com）
     - 公司代理配置是否正确
  3. 反爬限制，请稍后重试

下一步建议：
  - 尝试使用浏览器手动访问目标网站确认内容
  - 检查 logs/spider.log 获取详细错误信息
  - 如需手动补充数据，请参考 README.md 的"使用已有数据"章节
```

#### 2. LLM API 调用失败

**错误信息**：
```
❌ LLM 分析失败

可能原因：
  1. API Key 无效或已过期
  2. API 服务不可用：{LLM_API_BASE}
  3. 网络连接问题

下一步建议：
  1. 检查 .env 文件中的 LLM_API_KEY 是否正确
  2. 测试 API 连接：curl {LLM_API_BASE}/v1/models
  3. 查看 logs/failed_items_*.json 获取失败详情
```

#### 3. 报告校验失败

**错误信息**：
```
❌ 报告校验失败

缺失组件：
  - {具体缺失的组件列表}

可能原因：
  1. LLM 返回的数据格式不完整
  2. 模板文件被修改

下一步建议：
  1. 查看 output/processed_products.json 确认数据完整性
  2. 使用 --validate-only --report-path 单独校验报告
  3. 尝试重新生成：python etl_pipeline.py --month YYYY-MM --template pm_deep
```

---

## 调试与日志

### 日志文件位置

- **爬虫日志**：`output/spider.log`
- **失败项日志**：`logs/failed_items_*.json`（按时间戳命名）
- **处理后的数据**：`output/processed_products.json`

### 启用调试模式

如需更详细的日志输出，可在命令前添加环境变量：

```bash
# Windows PowerShell
$env:DEBUG = "true"
python etl_pipeline.py --month 2026-01 --fetch

# Linux / macOS
DEBUG=true python3 etl_pipeline.py --month 2026-01 --fetch
```

---

## 兼容性要求

### 运行环境

| 项目 | 要求 |
|------|------|
| Python 版本 | 3.9 - 3.12（**避免使用 3.14**） |
| 操作系统 | Windows / macOS / Linux |
| 运行目录 | **必须**在项目根目录 |

### 依赖资源

- **本地资源**：如需离线图表，需先运行 `scripts/download_assets.bat`（Windows）或 `bash scripts/download_assets.sh`（Unix）
- **网络要求**：爬虫需要访问目标网站，LLM 需要访问 API 服务

---

## 示例对话流程

### 场景 1：首次使用

**用户输入**：
```
调研2026年1月份的键鼠新品
```

**Claude Code 响应**：
```
检测到您想生成 2026-01 的外设新品调研报告。

正在检查环境...
✓ 项目根目录正确
⚠️ 未检测到虚拟环境，建议先运行安装脚本

是否继续使用系统 Python？(y/n)
```

### 场景 2：正常执行

**用户输入**：
```
分析2026-02的外设新品
```

**Claude Code 响应**：
```
正在为 2026-02 执行外设新品调研...

[执行命令]
python etl_pipeline.py --month 2026-02 --fetch --template pm_deep

[输出爬取进度...]

✅ 外设新品调研报告已生成！

📊 数据概况：
  - 抓取记录数：45 条
  - 去重后产品数：18 款

📄 报告路径：output/monthly_report_2026_02.html

🚀 快速查看：start output/monthly_report_2026_02.html
```

### 场景 3：数据覆盖率警告

**用户输入**：
```
生成2025年12月的报告
```

**Claude Code 响应**：
```
✅ 外设新品调研报告已生成！

📊 数据概况：
  - 抓取记录数：32 条
  - 去重后产品数：12 款

📄 报告路径：output/monthly_report_2025_12.html

⚠️ 数据覆盖率警告：
  - 传感器数据覆盖率：45%
  - 价格数据覆盖率：60%
  - 部分产品可能存在信息缺失

📋 查看失败项日志：logs/failed_items_*.json
```

---

## 快速参考

### Slash 命令

用户也可使用 `/research` slash command：

```
/research 2026-01
```

### 手动命令

如需更多控制，可手动执行：

```bash
# 一键模式（推荐）
python etl_pipeline.py --month 2026-01 --fetch --template pm_deep

# 分步模式
python spider.py  # 先爬取
python etl_pipeline.py --month 2026-01 --template pm_deep  # 再生成

# 仅校验
python scripts/validate_report.py --file output/monthly_report_2026_01.html
```

---

## 故障排查

详见 [README.md](README.md) 的"常见问题"章节。
