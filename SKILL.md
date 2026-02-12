---
name: peripheral-monitor-skill
description: 一键生成专业级外设新品 PM 深度分析 HTML 报告。从 in外设、外设天下等平台爬取键鼠新品资讯，使用 LLM 进行产品参数提取和深度分析，生成包含交互式图表的深色主题 HTML 报告。
version: 1.0.0
author: Peripheral Monitor Team
license: MIT
tags: [peripherals, spider, llm, product-analysis, report-generator]
requirements:
  - python>=3.9,<3.14
  - requests
  - beautifulsoup4
  - pandas
  - openai
environment:
  - LLM_API_KEY
  - LLM_API_BASE
  - LLM_MODEL
---

# 外设新品监控报告生成系统 - 技术规范

> 版本: v1.0.0
> 最后更新: 2026-02-10

---

## 📋 目录

1. [端到端流程](#端到端流程)
2. [数据 Schema 定义](#数据-schema-定义)
3. [UI 模板契约](#ui-模板契约)
4. [校验规则](#校验规则)
5. [扩展点](#扩展点)
6. [故障排查](#故障排查)
7. [性能优化](#性能优化)

---

## 1. 端到端流程

### 1.1 流程图

```
┌─────────────────┐
│   数据采集      │  spider.py
│  (spider.py)    │  → output/report_data_YYYY_MM.json
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   数据预处理    │  etl_pipeline.py: DataPreprocessor
│  清洗/去重      │  → 过滤非键鼠内容
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  LLM 深度分析   │  LLMExtractor.extract_product_info()
│  (PM 视角)      │  → 提取 Top 15 Schema + PM 洞察
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   产品合并      │  ProductMerger.merge_products()
│  (去重)         │  → 合并相同产品的多条报道
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   HTML 渲染     │  HTMLReportGenerator.generate()
│  (PM 深度分析版) │  → output/monthly_report_YYYY_MM.html
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   报告校验      │  validate_html_report()
│  (完整性检查)   │  → 失败则退出并报错
└─────────────────┘
```

### 1.2 详细步骤说明

#### 步骤 1: 数据采集 (spider.py)

**输入**：
- 目标网站 URL (in外设、外设天下)
- 目标年月 (TARGET_YEAR, TARGET_MONTH)

**处理**：
- 发起 HTTP 请求获取文章列表
- 解析文章内容（标题、正文、图片、发布日期）
- 保存为 JSON/Excel 格式

**输出**：
```json
// output/report_data_2026_01.json
[
  {
    "title": "罗技G Pro X Superlight 2 发布",
    "source": "in外设",
    "url": "https://www.example.com/article-123",
    "publish_date": "2026-01-15",
    "content_text": "罗技今日发布了G Pro X Superlight 2...",
    "images": ["https://example.com/image.jpg"]
  }
]
```

**关键规则**：
- 仅采集目标年月的文章
- 过滤掉非键鼠产品（通过关键词匹配）
- 图片 URL 可选，允许为空

---

#### 步骤 2: 数据预处理 (DataPreprocessor)

**输入**：
- `output/report_data_YYYY_MM.json`

**处理**：
```python
# 伪代码
def preprocess(raw_data):
    # 1. 过滤非键鼠内容
    filtered = [item for item in raw_data
                if contains_keyboard_mouse_keywords(item)]

    # 2. 提取产品名称
    for item in filtered:
        item['product_name'] = extract_product_name(item['title'])

    # 3. 合并内容字段
    for item in filtered:
        item['combined_content'] = combine_title_and_content(item)

    return filtered
```

**输出**：
```json
[
  {
    "product_name": "罗技G Pro X Superlight 2",
    "combined_content": "标题 + 正文内容...",
    "category": null,  // 待 LLM 分类
    "images": [...],
    "source": "in外设",
    "url": "..."
  }
]
```

**关键规则**：
- 必须包含 `product_name` 字段
- `combined_content` 长度限制在 10000 字符以内
- 丢弃长度小于 100 字符的记录

---

#### 步骤 3: LLM 深度分析 (LLMExtractor)

**输入**：
- 预处理后的产品列表

**处理**：
```python
# 并发调用 LLM API（max_workers=10）
with ThreadPoolExecutor(max_workers=10) as executor:
    futures = [executor.submit(llm.extract_product_info, product)
               for product in products]

    results = [future.result() for future in futures]
```

**LLM Prompt 结构**：
```
你是一位资深的外设产品经理和硬件评测师，擅长从产品新闻稿中提取关键信息并进行深度竞品分析。

请阅读以下产品文档，提取核心参数并进行深度分析。

文本内容：{combined_content}

请严格按照以下 JSON 格式返回：
{
  "product_name": "标准化产品全名",
  "category": "鼠标" 或 "键盘" 或 "其他",
  "specs": { ... Top 15 Schema 字段 ... },
  "analysis": {
    "market_position": "产品定位",
    "competitors": "竞品对比（必须提及2-3个具体型号）",
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

**输出**：
```json
{
  "product_name": "罗技G Pro X Superlight 2",
  "category": "鼠标",
  "specs": {
    "sensor_solution": "Hero 2 传感器（32000 DPI）",
    "product_pricing": "159美元",
    "weight_center": "60g",
    ...
  },
  "analysis": {
    "market_position": "高端轻量化无线游戏鼠标",
    "competitors": "雷蛇毒蝰V3 Pro（159美元/55g）、罗技GPX 2（159美元/63g）",
    "target_audience": "追求极致轻量化的FPS/MOBA职业玩家",
    ...
  }
}
```

**关键规则**：
- LLM 失败时：跳过该产品，记录错误日志
- `specs` 字段允许为空字典，但不允许缺失
- `analysis` 字段不允许为空，必须包含所有子字段
- 超时时间：120 秒/请求

---

#### 步骤 4: 产品合并 (ProductMerger)

**输入**：
- LLM 分析后的产品列表

**处理**：
```python
def merge_products(products):
    # 1. 按产品名称分组
    groups = group_by_name(products)

    # 2. 计算相似度（SequenceMatcher）
    for group in groups:
        for p1, p2 in combinations(group, 2):
            similarity = SequenceMatcher(None, p1['name'], p2['name']).ratio()
            if similarity > 0.7:  # 相似度阈值
                merge_products(p1, p2)

    # 3. 合并策略
    # - 保留最完整的 specs
    # - 合并 source_links（去重）
    # - 合并 images（去重）

    return merged_products
```

**输出**：
```json
[
  {
    "product_name": "罗技G Pro X Superlight 2",
    "sources": ["in外设", "外设天下"],  // 多来源
    "source_links": ["url1", "url2"],
    "specs": { ... },  // 最完整的 specs
    "analysis": { ... }
  }
]
```

**关键规则**：
- 相似度阈值：0.7
- 优先保留 LLM 分析结果更完整的产品
- `source_links` 必须包含所有来源 URL

---

#### 步骤 5: HTML 渲染 (HTMLReportGenerator)

**输入**：
- 合并后的产品列表

**处理**：
```python
def generate(products, template_mode="pm_deep"):
    # 1. 初始化市场分析器
    analyzer = MarketAnalyzer(products)
    chart_data = analyzer.get_chart_data()

    # 2. 构建 HTML 结构
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>{TARGET_YEAR}年{TARGET_MONTH}月外设新品监控报告</title>
        <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
        <style>...</style>
    </head>
    <body>
        <!-- 导航栏 -->
        <div id="nav-bar">...</div>

        <!-- 产品卡片列表 -->
        {render_products(products)}

        <!-- 图表 -->
        {render_charts(chart_data)}
    </body>
    </html>
    """

    return html
```

**输出**：
- `output/monthly_report_YYYY_MM.html`

**关键规则**：
- 必须包含所有 PM 深度分析版必需组件
- 图表数据必须准确反映实际分布
- 图片加载失败时使用占位图

---

#### 步骤 6: 报告校验 (validate_html_report)

**输入**：
- HTML 报告文件路径

**处理**：
```python
def validate_html_report(html_path):
    required_components = {
        'nav-bar': '导航栏',
        'searchInput': '搜索输入框',
        'product-overview': '产品概览模块',
        'product-specs': '硬核参数模块',
        'product-analysis': 'PM深度洞察模块',
        'PM 深度洞察': 'PM洞察标题'
    }

    html_content = read_file(html_path)

    missing = []
    for component, description in required_components.items():
        if component not in html_content:
            missing.append(f"  ✗ {component}: {description}")

    if missing:
        print("[FAIL] HTML报告校验失败！缺少以下关键组件:")
        for m in missing:
            print(m)
        sys.exit(1)  # 直接失败

    print("[OK] 所有关键组件校验通过")
    return True
```

**输出**：
- 校验通过：继续执行
- 校验失败：打印缺失组件，退出码 1

**关键规则**：
- 缺失任何关键组件直接失败
- 不允许降级到简化模板
- 退出码：0=成功，1=失败

---

## 2. 数据 Schema 定义

### 2.1 processed_products.json

#### 完整 Schema

```json
{
  "产品基本信息": {
    "product_name": "string (必需) - 标准化产品全名",
    "category": "string (必需) - 鼠标 | 键盘 | 其他",
    "main_image": "string (可选) - 产品主图URL",
    "release_price": "string (可选) - 发布价格",
    "innovation_tags": "array (可选) - 创新标签列表",
    "publish_date": "string (可选) - 发布日期 YYYY-MM-DD"
  },
  "来源信息": {
    "sources": "array (必需) - 来源平台列表",
    "source_links": "array (必需) - 文章URL列表"
  },
  "specs": {
    "鼠标 Top 15 Schema": {
      "product_pricing": "string - 产品与定价",
      "mold_lineage": "string - 模具血统",
      "weight_center": "string - 重量与重心",
      "sensor_solution": "string - 传感器方案",
      "mcu_chip": "string - 主控芯片",
      "polling_rate": "string - 回报率配置",
      "end_to_end_latency": "string - 全链路延迟",
      "switch_features": "string - 微动特性",
      "scroll_encoder": "string - 滚轮编码器",
      "coating_process": "string - 涂层工艺",
      "high_refresh_battery": "string - 高刷续航",
      "structure_quality": "string - 结构做工",
      "feet_config": "string - 脚贴配置",
      "wireless_interference": "string - 无线抗干扰",
      "driver_experience": "string - 驱动体验"
    },
    "键盘 Top 15 Schema": {
      "product_layout": "string - 产品与配列",
      "structure_form": "string - 结构形式",
      "tech_route": "string - 技术路线",
      "rt_params": "string - RT参数",
      "sound_dampening": "string - 声音包填充",
      "switch_details": "string - 轴体详解",
      "measured_latency": "string - 实测延迟",
      "keycap_craftsmanship": "string - 键帽工艺",
      "bigkey_tuning": "string - 大键调校",
      "pcb_features": "string - PCB特性",
      "case_craftsmanship": "string - 外壳工艺",
      "front_height": "string - 前高数据",
      "battery_efficiency": "string - 电池效率",
      "connection_storage": "string - 连接与收纳",
      "software_support": "string - 软体支持"
    }
  },
  "analysis": {
    "market_position": "string (必需) - 产品定位",
    "competitors": "string (必需) - 竞品对比",
    "target_audience": "string (必需) - 目标用户",
    "selling_point": "string (必需) - 核心卖点",
    "verdict": {
      "pros": "array (必需) - 优点列表",
      "cons": "array (必需) - 缺点列表"
    },
    "pm_summary": "string (必需) - 购买建议"
  }
}
```

### 2.2 字段缺失处理规则

| 字段类型 | 缺失处理 | 说明 |
|---------|---------|------|
| `product_name` | **不允许缺失** | 必须有值，否则丢弃产品 |
| `category` | **不允许缺失** | 必须是"鼠标"/"键盘"/"其他"之一 |
| `specs` | 允许为空对象 `{}` | LLM 未能提取参数时使用 |
| `specs.sensor_solution` | 允许为空字符串 `""` | 图表统计时归入"未知"桶 |
| `specs.product_pricing` | 允许为空字符串 `""` | 图表统计时归入"未公开"桶 |
| `analysis` | **不允许为空** | 必须包含所有子字段，否则降级失败 |
| `main_image` | 允许缺失 | 渲染时使用占位图 |
| `release_price` | 允许缺失 | 显示为"价格未公开" |

---

## 3. UI 模板契约

### 3.1 PM 深度分析版 (pm_deep) 必需组件

#### 导航区域

```html
<!-- 必需组件 1: nav-bar -->
<div id="nav-bar">
    <nav class="nav-buttons">
        <a href="#overview">总览</a>
        <a href="#products">产品详情</a>
        <a href="#charts">数据分析</a>
    </nav>
    <input type="text" id="searchInput" placeholder="搜索产品...">
</div>
```

**校验规则**：
- 必须包含 `id="nav-bar"`
- 必须包含 `id="searchInput"`

---

#### 产品卡片 - 三栏布局

```html
<div class="product-card">
    <!-- 必需组件 2: product-overview (左栏) -->
    <div class="product-overview">
        <div class="product-image">
            <img src="..." alt="产品图片">
        </div>
        <div class="product-name">产品名称</div>
        <div class="product-price">价格</div>
        <div class="product-date">发布时间</div>
        <div class="source-links">来源链接</div>
    </div>

    <!-- 必需组件 3: product-specs (中栏) -->
    <div class="product-specs">
        <div class="block-title">硬核参数</div>
        <div class="specs-list">
            <div class="spec-item">
                <span class="spec-label">参数名</span>
                <span class="spec-value">参数值</span>
            </div>
            <!-- 更多参数... -->
        </div>
    </div>

    <!-- 必需组件 4: product-analysis (右栏) -->
    <div class="product-analysis">
        <div class="block-title">PM 深度洞察</div>
        <!-- 必需子组件: PM 深度洞察 标题 -->
        <div class="analysis-section">
            <div class="analysis-label">创新标签</div>
            <div class="analysis-text">...</div>
        </div>
        <div class="analysis-section">
            <div class="analysis-label">市场定位</div>
            <div class="analysis-text">...</div>
        </div>
        <!-- 更多分析字段... -->
    </div>
</div>
```

**校验规则**：
- 必须包含 `class="product-overview"`
- 必须包含 `class="product-specs"`
- 必须包含 `class="product-analysis"`
- 必须包含文本 `PM 深度洞察`

---

#### 图表区域

```html
<div id="charts">
    <!-- 传感器分布图 -->
    <canvas id="sensorChart"></canvas>

    <!-- 价格区间分布图 -->
    <canvas id="priceChart"></canvas>

    <!-- 其他图表... -->
</div>
```

**校验规则**：
- 必须包含 `id="sensorChart"`
- 必须包含 `id="priceChart"`

---

### 3.2 模板降级规则

**不允许降级！**

如果 LLM 未能提取 `specs` 或 `analysis` 字段：
1. 记录警告日志
2. 使用占位内容渲染（不跳过该产品）
3. 继续处理其他产品
4. **绝不切换到简化模板**

**示例**：
```python
# 正确处理方式
if not specs or not any(specs.values()):
    logger.warning(f"产品 {product_name} 缺少 specs 参数，使用占位内容")
    specs = {k: "" for k in MOUSE_SCHEMA.keys()}  # 占位
    # 继续渲染，不降级
```

---

## 4. 校验规则

### 4.1 HTML 报告校验

#### 自动校验时机

报告生成后自动执行校验，无需手动调用。

#### 校验项清单

| 组件 ID | 说明 | 检测方式 | 失败处理 |
|---------|------|---------|---------|
| `nav-bar` | 导航栏 | `id="nav-bar" in html` | 退出并报错 |
| `searchInput` | 搜索框 | `id="searchInput" in html` | 退出并报错 |
| `product-overview` | 产品概览 | `class="product-overview" in html` | 退出并报错 |
| `product-specs` | 硬核参数 | `class="product-specs" in html` | 退出并报错 |
| `product-analysis` | PM洞察 | `class="product-analysis" in html` | 退出并报错 |
| `PM 深度洞察` | 标题文本 | `"PM 深度洞察" in html` | 退出并报错 |

#### 校验脚本

```bash
# 手动校验
python scripts/validate_report.py output/monthly_report_2026_01.html

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

### 4.2 数据完整性校验

#### 必需字段检查

```python
def validate_product(product):
    required_fields = {
        'product_name': str,
        'category': str,
        'specs': dict,
        'analysis': dict
    }

    for field, field_type in required_fields.items():
        if field not in product:
            return False, f"缺少必需字段: {field}"
        if not isinstance(product[field], field_type):
            return False, f"字段类型错误: {field}"

    # 检查 analysis 子字段
    analysis = product['analysis']
    required_analysis = ['market_position', 'competitors',
                        'target_audience', 'selling_point',
                        'verdict', 'pm_summary']

    for sub_field in required_analysis:
        if sub_field not in analysis:
            return False, f"analysis 缺少子字段: {sub_field}"

    return True, "校验通过"
```

---

## 5. 扩展点

### 5.1 自定义 LLM Provider

```python
# 在 etl_pipeline.py 中修改 LLM_CONFIG
LLM_CONFIG = {
    "provider": "custom",  # 自定义 provider
    "api_key": "your_api_key",
    "model": "your_model_name",
    "base_url": "https://your-api-endpoint.com/v1"
}
```

### 5.2 自定义数据源

```python
# 继承 Spider 基类
class CustomSpider(Spider):
    def fetch_articles(self, year, month):
        # 实现自定义采集逻辑
        pass

    def parse_article(self, html):
        # 实现自定义解析逻辑
        pass
```

### 5.3 自定义模板

```python
# 继承 HTMLReportGenerator
class CustomReportGenerator(HTMLReportGenerator):
    def _build_html(self):
        # 实现自定义 HTML 结构
        pass
```

### 5.4 添加新的 Schema 字段

```python
# 在 etl_pipeline.py 中扩展 MOUSE_SCHEMA
MOUSE_SCHEMA = {
    **MOUSE_SCHEMA,  # 保留原有字段
    'custom_field': '自定义字段名称'
}
```

---

## 6. 故障排查

### 6.1 抽取失败

#### 症状
```
[ERROR] LLM服务连接失败: 504 Server Error
```

#### 定位步骤
1. 检查 API 配置
```bash
curl http://192.168.0.250:7777/v1/models
```

2. 检查 API Key
```bash
echo $LLM_API_KEY
```

3. 查看详细日志
```python
# 在 etl_pipeline.py 中启用 DEBUG 模式
logging.basicConfig(level=logging.DEBUG)
```

#### 解决方案
- 确认 API 服务可访问
- 检查 API Key 是否有效
- 增加超时时间：`timeout=180`

---

### 6.2 字段映射错误

#### 症状
```
[DEBUG-CHART] sensor_solution字段值: ''
所有传感器显示为"未知"
```

#### 定位步骤
1. 检查 LLM 返回的原始字段
```python
# 查看 [DEBUG-LLM] 日志
# 确认 LLM 返回的是 'sensor_solution' 而非 'sensor'
```

2. 检查字段映射逻辑
```python
# MarketAnalyzer._get_chart_data() 中
sensor = mouse.get('specs', {}).get('sensor_solution', '')
# 确保使用正确的字段名
```

#### 解决方案
- 使用 Top 15 Schema 标准字段名
- 添加字段别名映射

---

### 6.3 图表异常

#### 症状
```
Chart.js 加载失败
图表数据显示为 0
```

#### 定位步骤
1. 检查 CDN 连接
```html
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
```

2. 检查数据格式
```javascript
console.log(chart_data);
// 确保数据格式正确
```

3. 查看浏览器控制台错误
```javascript
F12 → Console → 查看错误信息
```

#### 解决方案
- 确保网络可访问 CDN
- 检查数据格式是否正确
- 添加容错处理

---

### 6.4 资源加载失败

#### 症状
```
产品图片显示为占位图
CSS 样式未生效
```

#### 定位步骤
1. 检查图片 URL
```python
# 打印所有图片 URL
for product in products:
    print(product.get('main_image', 'MISSING'))
```

2. 检查 CSS 加载
```html
<!-- 确认 style 标签存在 -->
<style>...</style>
```

#### 解决方案
- 图片 URL 无效时使用占位图
- CSS 内联到 HTML 中
- 添加 onerror 容错

---

## 7. 性能优化

### 7.1 并发优化

```python
# 当前配置
max_workers=10  # 并发 LLM 请求数

# 调优建议
# - API 性能强：增加到 20
# - 内存有限：减少到 5
```

### 7.2 内存优化

```python
# 流式处理大文件
def process_large_json(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:  # 逐行读取
            product = json.loads(line)
            yield product
```

### 7.3 缓存优化

```python
# 缓存 LLM 结果
import functools

@functools.lru_cache(maxsize=100)
def extract_with_cache(content_hash):
    return llm.extract_product_info(content)
```

---

## 附录 A: 错误代码表

| 错误代码 | 说明 | 处理建议 |
|---------|------|---------|
| E001 | 输入文件不存在 | 检查文件路径 |
| E002 | JSON 解析失败 | 检查 JSON 格式 |
| E003 | LLM API 连接失败 | 检查网络和 API 配置 |
| E004 | LLM 超时 | 增加超时时间 |
| E005 | HTML 校验失败 | 检查模板必需组件 |
| E006 | 字段映射错误 | 检查 Schema 字段名 |

---

## 附录 B: 版本历史

| 版本 | 日期 | 变更说明 |
|------|------|---------|
| v1.0.0 | 2026-02-10 | 初始版本 |
