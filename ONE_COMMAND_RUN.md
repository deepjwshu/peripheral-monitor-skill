# 最小可运行命令序列

> 从零开始到生成 2026-01 报告的一键命令

---

## ⚡ 一键完整命令（最小推荐）

```bash
# Windows PowerShell
python etl_pipeline.py --month 2026-01 --fetch --template pm_deep

# Linux / macOS
python3 etl_pipeline.py --month 2026-01 --fetch --template pm_deep
```

此命令会自动完成：
1. ✅ 运行爬虫采集指定月份的键鼠新品数据
2. ✅ 自动备份旧数据文件
3. ✅ 验证数据有效性（0 条数据会报错退出）
4. ✅ 生成 PM 深度分析报告
5. ✅ 自动校验报告完整性

**输出文件**：`output/monthly_report_2026_01.html`

---

---

## 🚀 Windows 用户

```powershell
# 步骤 1: 进入项目目录
cd peripheral-monitor-skill

# 步骤 2: 一键安装（或手动执行下面命令）
scripts\install.bat

# ===== 手动安装步骤（如果不用安装脚本）=====

# 2.1 安装依赖
pip install -r requirements.txt

# 2.2 创建配置文件
copy .env.example .env

# 2.3 编辑 .env 文件，填入 API Key
notepad .env
# 修改以下内容：
# LLM_API_KEY=sk-your-api-key-here
# LLM_API_BASE=https://api.deepseek.com/v1
# LLM_MODEL=deepseek-chat

# ===== 手动安装步骤结束 =====

# 步骤 3: 准备输入数据（二选一）

# 方式 A: 使用示例数据
copy examples\input_example.json output\report_data_2026_01.json

# 方式 B: 使用爬虫采集（需要等待）
python spider.py

# 步骤 4: 生成报告
python etl_pipeline.py --template pm_deep

# 步骤 5: 查看报告
start output\monthly_report_2026_01.html
```

---

## 🐧 Linux / macOS 用户

```bash
# 步骤 1: 进入项目目录
cd peripheral-monitor-skill

# 步骤 2: 一键安装（或手动执行下面命令）
bash scripts/install.sh

# ===== 手动安装步骤（如果不用安装脚本）=====

# 2.1 安装依赖
pip3 install -r requirements.txt

# 2.2 创建配置文件
cp .env.example .env

# 2.3 编辑 .env 文件，填入 API Key
nano .env
# 修改以下内容：
# LLM_API_KEY=sk-your-api-key-here
# LLM_API_BASE=https://api.deepseek.com/v1
# LLM_MODEL=deepseek-chat

# ===== 手动安装步骤结束 =====

# 步骤 3: 准备输入数据（二选一）

# 方式 A: 使用示例数据
cp examples/input_example.json output/report_data_2026_01.json

# 方式 B: 使用爬虫采集（需要等待）
python3 spider.py

# 步骤 4: 生成报告
python3 etl_pipeline.py --template pm_deep

# 步骤 5: 查看报告
# macOS
open output/monthly_report_2026_01.html
# Linux
xdg-open output/monthly_report_2026_01.html
```

---

## ⚡ 一键完整命令（复制粘贴版）

### Windows PowerShell

```powershell
# 1. 安装依赖
pip install -r requirements.txt

# 2. 创建配置
copy .env.example .env
# 然后手动编辑 .env 文件填入 API Key

# 3. 准备数据
copy examples\input_example.json output\report_data_2026_01.json

# 4. 生成报告
python etl_pipeline.py --template pm_deep

# 5. 查看报告
start output\monthly_report_2026_01.html
```

### Linux / macOS (bash)

```bash
# 1. 安装依赖
pip3 install -r requirements.txt

# 2. 创建配置
cp .env.example .env
# 然后手动编辑 .env 文件填入 API Key
# nano .env 或 vim .env

# 3. 准备数据
cp examples/input_example.json output/report_data_2026_01.json

# 4. 生成报告
python3 etl_pipeline.py --template pm_deep

# 5. 查看报告
open output/monthly_report_2026_01.html 2>/dev/null || xdg-open output/monthly_report_2026_01.html
```

---

## 🎯 不同场景命令

### 场景 1: 使用一键命令（爬取 + 生成）

```bash
# 一键完成爬取和生成报告
python etl_pipeline.py --month 2026-01 --fetch --template pm_deep
```

等价于执行以下步骤：
```bash
# 步骤 1: 修改 config.py 中的目标年月
# TARGET_YEAR = 2026
# TARGET_MONTH = 1

# 步骤 2: 运行爬虫（自动备份旧数据）
python spider.py

# 步骤 3: 确认数据已生成（自动验证）
ls -lh output/report_data_2026_01.json

# 步骤 4: 生成报告
python etl_pipeline.py --template pm_deep

# 步骤 5: 校验报告（自动执行）
python scripts/validate_report.py output/monthly_report_2026_01.html
```

### 场景 2: 仅校验已有报告

```bash
# 不重新生成，仅校验完整性
python etl_pipeline.py --validate-only --report-path output/monthly_report_2026_01.html

# 或使用独立校验脚本
python scripts/validate_report.py output/monthly_report_2026_01.html --strict
```

### 场景 3: 生成简化版报告

```bash
python etl_pipeline.py --template simple
```

### 场景 4: 处理其他年月的数据

```bash
# 方式 1: 环境变量
export TARGET_YEAR=2026
export TARGET_MONTH=2
python etl_pipeline.py

# 方式 2: 修改 config.py
# 然后运行
python etl_pipeline.py
```

---

## 🔍 故障排查命令

### 检查依赖

```bash
pip list | grep -E "requests|pandas|beautifulsoup4"
```

### 检查 API 连接

```bash
# DeepSeek 官方 API
curl https://api.deepseek.com/v1/models \
  -H "Authorization: Bearer YOUR_API_KEY"

# 公司内部 API
curl http://192.168.0.250:7777/v1/models \
  -H "Authorization: Bearer YOUR_API_KEY"
```

### 启用调试模式

```bash
# 方式 1: 环境变量
export DEBUG=true
export LOG_LEVEL=DEBUG
python etl_pipeline.py

# 方式 2: 修改 config.py
# LOG_LEVEL = 'DEBUG'
```

### 测试示例数据

```bash
# 使用示例数据快速测试
cp examples/input_example.json output/report_data_2026_01.json
python etl_pipeline.py --template pm_deep
```

---

## 📊 预期输出验证

### 1. 检查文件是否生成

```bash
# 应该看到以下文件
ls -lh output/
# - monthly_report_2026_01.html  (主报告)
# - processed_products.json      (处理后的数据)
# - report_data_2026_01.json      (原始输入数据)
```

### 2. 检查控制台输出

```
[OK] 产品合并: 2 -> 2 (-0 重复)
[OK] HTML 报告已生成: output\monthly_report_2026_01.html
[OK] 所有关键组件校验通过:
  ✓ nav-bar: 导航栏（包含快速跳转和搜索框）
  ✓ searchInput: 搜索输入框
  ...
```

### 3. 检查报告内容

打开 `output/monthly_report_2026_01.html`，应该看到：

- ✅ 深色极客风主题
- ✅ 顶部导航栏（带搜索框）
- ✅ 产品卡片（三栏布局）
- ✅ PM 深度洞察（竞品对比、目标用户等）
- ✅ 数据图表（传感器分布、价格区间等）

---

## 🎓 进阶使用

### 批量处理多个月份

```bash
# 创建批处理脚本
cat > batch_process.sh << 'EOF'
#!/bin/bash
for month in {1..12}; do
    echo "处理 2026 年 ${month} 月..."
    export TARGET_MONTH=$month
    python spider.py
    python etl_pipeline.py --template pm_deep
done
EOF

chmod +x batch_process.sh
./batch_process.sh
```

### 自定义并发数

```bash
# 增加 LLM 并发数（API 性能强时）
export MAX_WORKERS=20
python etl_pipeline.py

# 减少并发数（内存有限时）
export MAX_WORKERS=5
python etl_pipeline.py
```

### 仅运行特定步骤

```python
# 修改 etl_pipeline.py 中的 main() 函数
# 注释掉不需要的步骤

# 例如：仅运行数据预处理，不调用 LLM
def main():
    # ... 加载数据
    products = preprocessor.process(raw_data)

    # 注释掉 LLM 分析
    # extractor = LLMExtractor(LLM_CONFIG)
    # extracted = extractor.extract_batch(products)

    # 直接保存
    save_products(products, 'output/preprocessed.json')
```

---

## 📞 获取帮助

```bash
# 查看完整命令行参数
python etl_pipeline.py --help

# 查看校验脚本帮助
python scripts/validate_report.py --help

# 查看示例
cat examples/QUICKSTART.md
```
