# 外设新品监控报告生成系统 - 技术规范与工作流

> **版本**: v1.1 (严谨修订版) | **更新日期**: 2026-02-10
>
> 本文档定义系统的核心工作流、数据口径、配置规范，用于代码审查、故障排查和功能扩展。

---

## 📋 目录

1. [系统架构概览](#系统架构概览)
2. [核心工作流](#核心工作流)
3. [数据口径与缺失值处理](#数据口径与缺失值处理)
4. [去重与合并策略](#去重与合并策略)
5. [LLM 错误处理与降级](#llm-错误处理与降级)
6. [报告校验规范](#报告校验规范)
7. [配置与扩展](#配置与扩展)
8. [隐私与安全](#隐私与安全)
9. [站点合规与反爬策略](#站点合规与反爬策略)

---

## 系统架构概览

```
┌─────────────────────────────────────────────────────────────────┐
│                        输入数据源                                 │
│  - Spider 爬虫: output/report_data_YYYY_MM.json                  │
│  - 用户上传: 任意 JSON/Excel 文件                                 │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  Phase 1: 数据清洗层 (DataCleaner)                                │
│  - 关键词白名单筛选 (KEYWORDS)                                    │
│  - 黑名单过滤 (BLACKLIST)                                         │
│  - 智能去重 (SequenceMatcher, 阈值=0.6)                           │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  Phase 2: LLM 智能分析层 (LLMExtractor V2)                        │
│  - 并发处理 (ThreadPoolExecutor, batch_size=5)                   │
│  - 单次调用提取: product_name + specs (Top 15) + analysis         │
│  - 价格标准化 (外币转换 + 正则提取)                                │
│  - 完整性验证 (必需字段检查)                                       │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  Phase 3: 产品合并层 (ProductMerger)                              │
│  - 名称归一化 (normalize_product_name)                           │
│  - 相似度计算 (SequenceMatcher, 阈值=0.85)                        │
│  - 防误合并硬规则 (类别必须相同)                                   │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  Phase 4: 报告生成层 (HTMLReportGenerator)                        │
│  - 市场分析 (品类占比、传感器分布、价格区间)                        │
│  - 文本生成 (技术趋势、价格洞察、PM 启示)                           │
│  - HTML 构建 (深色极客风 + 交互式图表)                             │
│  - 四向一致性校验 (DOM + 数据口径验证)                              │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                        输出交付物                                 │
│  - monthly_report_YYYY_MM.html (主报告)                           │
│  - monthly_report_YYYY_MM.html.bak (备份)                         │
│  - processed_products.json (结构化数据)                           │
│  - logs/failed_items_*.json (失败项日志)                           │
└─────────────────────────────────────────────────────────────────┘
```

---

## 核心工作流

### 主入口: `etl_pipeline.py::main()`

```python
def main(template_mode="pm_deep", input_file=None, target_year=None, target_month=None):
    """
    参数:
        template_mode: "pm_deep" (默认) | "simple"
        input_file: 输入文件路径，默认为 output/report_data_YYYY_MM.json
        target_year: 目标年份，默认为 TARGET_YEAR
        target_month: 目标月份，默认为 TARGET_MONTH

    返回:
        None (生成 HTML 报告和 JSON 数据)
    """
```

### 数据流转示例 (2026-01 运行实例)

> **注意**: 以下数字为某次实际运行示例，实际数值会根据输入数据动态变化。

```
[原始输入] 64 条文章记录
    ↓ 关键词筛选 (包含 KEYWORDS 任一关键词)
[阶段1输出] 60 条 (移除 4 条无关内容)
    ↓ 黑名单过滤 (排除包含 BLACKLIST 关键词)
[阶段2输出] 58 条 (移除 2 条配件记录)
    ↓ 智能去重 (SequenceMatcher > 0.6)
[阶段3输出] 37 款产品 (合并 21 条重复记录)
    ↓ LLM 分析 (batch_size=5, 失败重试3次)
[阶段4输出] 31 款有效产品 (6 款因 completeness < 60% 被丢弃)
    ↓ 优先级排序 + 产品合并 (SequenceMatcher > 0.85)
[阶段5输出] 24 款最终产品 (合并 7 款重复产品)
    ↓ 报告生成 + 四向一致性校验
[最终交付] HTML 报告 (197 KB) + JSON 数据
```

**变量口径说明**:
- `原始输入数`: 读取的 JSON/Excel 文件记录总数
- `关键词筛选后`: 包含 KEYWORDS 列表中任意关键词的记录数
- `黑名单过滤后`: 排除包含 BLACKLIST 关键词的记录数
- `智能去重后`: 基于 SequenceMatcher > 0.6 合并后的产品数
- `LLM 分析后`: 通过完整性验证的产品数 (completeness >= 60%)
- `优先级排序后`: 按 `_priority_score` 降序排列的产品数
- `产品合并后`: 基于 SequenceMatcher > 0.85 合并后的最终产品数

---

## 数据口径与缺失值处理

### 缺失值 Taxonomy (严谨标准)

| 标记值 | 含义 | 产生场景 | 示例 | 图表桶 | Coverage | 提示文案 |
|--------|------|----------|------|--------|----------|----------|
| **未提及** | 原文完全没有该信息 | 文章未提及该参数 | "发布日期未定" | ❌ 不计入桶 | ❌ 不计入分子 | "原文未提及" |
| **未公开** | 原文明确说明未公布 | 厂商未公开价格/参数 | "价格暂未公布" | ✅ "未公开"桶 | ❌ 不计入分子 | "厂商未公开" |
| **提取失败** | LLM 未能成功提取 | 原文可能有但抽取失败 | JSON parse 失败 | ❌ 不计入桶 | ❌ 不计入分子 | "提取失败" |
| **无法判断** | LLM 无法推断来源 | 信息模糊或矛盾 | "部分型号未知" | ❌ 不计入桶 | ❌ 不计入分子 | "无法判断" |
| **待实测** | 新品未上市需实测 | 概念/预发布产品 | "参数待后续实测" | ✅ "待实测"桶 | ❌ 不计入分子 | "待官方实测" |
| **概念产品** | 仅概念/渲染图 | 无实物参数 | "仅发布渲染图" | ✅ "概念"桶 | ❌ 不计入分子 | "概念产品" |
| **未知** (废弃) | ~~LLM 无法推断~~ | ~~已替换为"提取失败"~~ | - | - | - | - |

### 字段有效性判断

```python
# 有效值判断 (etl_pipeline.py:4289)
INVALID_VALUES = ['未知', '未公开', 'N/A', '', 'null', 'none', 'unknown']

# ⚠️ 重要区分:
# 1. "未公开" → 有效值 (单独统计为独立桶)
# 2. "未提及" / "提取失败" / "无法判断" → 无效值 (不计入 coverage)
# 3. "待实测" → 有效值 (单独统计为独立桶，但不计入 coverage)
# 4. "概念产品" → 产品级别标记 (innovation_tags)

# 判断逻辑:
def is_valid_value(value: str) -> bool:
    """判断字段值是否有效"""
    if not value or not str(value).strip():
        return False
    value_str = str(value).strip()
    if value_str in ['未知', 'unknown', 'null', 'none', 'N/A', '']:
        return False
    # "未公开"、"待实测" 等描述性值被视为有效
    return True
```

### 价格处理规则

#### 1. 价格提取优先级

```python
# 优先级 (从高到低):
# 1. specs.product_pricing (LLM 提取的结构化价格)
# 2. release_price (LLM 提取的价格字段)
# 3. 正则表达式从原文提取 (回退机制)

# 提取逻辑:
price = (
    product.get('specs', {}).get('product_pricing', '') or
    product.get('release_price', '') or
    extract_price_from_content(product['content_text'])  # 正则回退
)
```

#### 2. 价格标准化 (`_standardize_price()`)

```python
# 支持格式:
# - "299元" → "299元"
# - "99-299元" → "299元" (取上限，当前实现)
# - "$49.99" → "360元" (汇率转换: 1 USD = 7.2 CNY)
# - "未公开" → "价格未公开"
# - "待定" → "价格未公开"

# ⚠️ 均价计算口径:
# 当前: 取价格区间上限用于计算
# 示例: "99-299元" 按 299 元计入均价
# 建议: 未来应解析为 {min: 99, max: 299, mid: 199, currency: 'CNY'}
#       均价使用 mid 值更准确

# 汇率配置 (2025 年参考):
EXCHANGE_RATES = {
    'USD': 7.2,    # 1美元 = 7.2人民币
    '$': 7.2,
    'JPY': 0.048,  # 1日元 = 0.048人民币
    'EUR': 7.8,    # 1欧元 = 7.8人民币
}
```

#### 3. 价格区间划分 (图表统计)

```python
PRICE_RANGES = {
    '0-199元':    0 <= price_num < 200,
    '200-499元':  200 <= price_num < 500,
    '500-999元':  500 <= price_num < 1000,
    '1000元+':    price_num >= 1000,
    '未公开':     无法解析价格或标记为"未公开"/"待定"
}

# ⚠️ "未公开"桶包含:
# 1. 原文明确"未公开"
# 2. 无法解析为数字的任何值
# 3. 空字符串或 None
```

#### 4. 均价计算口径

```python
# analyze_pricing_insights() 均价计算:
def calculate_average_price(products: List[Dict]) -> int:
    """
    均价 = 有效价格总和 / 有效价格数量

    有效价格: 可解析为数字的 price 值
    未公开: 不计入分母和分子

    示例:
        5款鼠标: [99, 199, 299, 未公开, 未公开]
        均价 = (99 + 199 + 299) / 3 = 199 元

        含区间: [99-299, 199-399, 未公开]
        当前: (299 + 399) / 2 = 349 元 (取上限)
        建议: (199 + 299) / 2 = 249 元 (取中值)
    """
    valid_prices = []
    for product in products:
        price = extract_price_number(product)
        if price is not None:  # 可解析为数字
            valid_prices.append(price)

    if not valid_prices:
        return 0

    return sum(valid_prices) // len(valid_prices)
```

### Coverage 定义 (严谨口径)

**Coverage = 有有效值的产品数 / 统计对象产品总数**

#### 核心概念区分

| 概念 | 定义 | 使用场景 | 计算公式 |
|------|------|----------|----------|
| **Coverage** | 某字段有有效值的占比 | 宏观数据质量评估 | 有值产品数 / 总产品数 |
| **Completeness** | 单产品 specs 字段完整度 | 产品级质量过滤 | 非空字段数 / Schema 总字段数 |

#### 传感器覆盖率

```python
# 统计对象: 所有鼠标产品 (self.mice)
# 有效值判断: specs.sensor_solution 非空且不在 INVALID_VALUES 中
#            排除: "未提及"、"提取失败"、"无法判断"
#            包含: "未公开" (单独统计桶)

def calculate_sensor_coverage(products: List[Dict]) -> float:
    """
    传感器覆盖率计算

    统计对象: 所有 category == '鼠标' 的产品
    有效值: specs.sensor_solution 满足以下条件:
        1. 非空字符串
        2. 不在 INVALID_VALUES 中 (排除 '未知', 'unknown', '')
        3. 不为 '未提及', '提取失败', '无法判断'

    示例:
        8 款鼠标:
        - PAW3395, PAW3950, Hero (有效) → 3
        - 未提及, 未提及, 未提及, 未提及, 未提及 (无效) → 5
        coverage = 3 / 8 = 37.5%
    """
    mice = [p for p in products if p.get('category') == '鼠标']
    total = len(mice)

    if total == 0:
        return 0.0

    valid_count = 0
    invalid_markers = ['未提及', '提取失败', '无法判断', '']

    for mouse in mice:
        sensor = mouse.get('specs', {}).get('sensor_solution', '')
        if sensor and sensor not in invalid_markers:
            valid_count += 1

    return valid_count / total
```

#### 价格覆盖率

```python
# 统计对象: 所有产品 (self.products)
# 有效值判断: product_pricing 或 release_price 可解析为数字
#            排除: "未公开"、"待定"

def calculate_price_coverage(products: List[Dict]) -> float:
    """
    价格覆盖率计算

    统计对象: 所有产品 (鼠标 + 键盘 + 其他)
    有效值: 满足以下条件之一:
        1. specs.product_pricing 可解析为数字
        2. release_price 可解析为数字

    无效值:
        - "未公开"、"待定"、"暂无价格"
        - 无法解析的任何字符串

    示例:
        24 款产品:
        - 15 款有价格 (有效)
        - 9 款未公开 (无效)
        coverage = 15 / 24 = 62.5%
    """
    total = len(products)

    if total == 0:
        return 0.0

    valid_count = 0
    for product in products:
        price = (
            product.get('specs', {}).get('product_pricing', '') or
            product.get('release_price', '')
        )
        # 尝试解析为数字
        price_num = extract_price_number(price)
        if price_num is not None:
            valid_count += 1

    return valid_count / total
```

#### Coverage 告警阈值

```python
# 警告规则:
def check_coverage_quality(coverage_stats: Dict) -> List[str]:
    """
    Coverage 质量检查

    告警阈值:
        - coverage == 0: 完全缺失，严重告警
        - coverage < 0.2: 极低，告警
        - coverage < 0.5: 较低，警告
        - coverage >= 0.5: 可接受
    """
    warnings = []

    sensor_cov = coverage_stats['sensor']['coverage']
    price_cov = coverage_stats['price']['coverage']

    if sensor_cov == 0:
        warnings.append("⚠️  传感器数据完全缺失 (0%)，所有鼠标产品的传感器信息无效")
    elif sensor_cov < 0.2:
        warnings.append(f"⚠️  传感器覆盖率极低 ({sensor_cov:.1%}) < 20%")
    elif sensor_cov < 0.5:
        warnings.append(f"⚠️  传感器覆盖率较低 ({sensor_cov:.1%}) < 50%，建议检查数据质量")

    if price_cov == 0:
        warnings.append("⚠️  价格数据完全缺失 (0%)，所有产品的价格信息无效")
    elif price_cov < 0.2:
        warnings.append(f"⚠️  价格覆盖率极低 ({price_cov:.1%}) < 20%")
    elif price_cov < 0.5:
        warnings.append(f"⚠️  价格覆盖率较低 ({price_cov:.1%}) < 50%，建议检查数据质量")

    return warnings
```

---

## 去重与合并策略

### 两级去重架构

#### Level 1: 文章级别去重 (DataCleaner.smart_deduplicate)

**目的**: 合并多篇关于同一产品的不同报道

**流程**:
```python
# 1. 按发布时间排序 (最新的在前)
df = df.sort_values('publish_date', ascending=False)

# 2. 逐条比对相似度
for i, row_i in df.iterrows():
    for j, row_j in df.iterrows():
        if j <= i: continue

        similarity = SequenceMatcher(None, row_i['title'], row_j['title']).ratio()

        # 阈值: 0.6 (见下方"阈值说明")
        if similarity > 0.6:
            # 合并记录
            merged_product['records'].extend([row_i, row_j])
            merged_product['sources'] = list(set([row_i['source'], row_j['source']]))
            merged_product['combined_content'] = join_content(row_i, row_j)
```

**输出**:
```python
{
    'product_name': '标准化产品全名',
    'records': [...],        # 原始文章列表
    'sources': ['in外设', '外设天下'],
    'images': ['url1', 'url2'],
    'combined_content': '合并后的正文...'
}
```

#### Level 2: 产品级别去重 (ProductMerger.merge_products)

**目的**: 合并 LLM 分析后的重复产品

**流程**:
```python
# 1. 按类别分组
by_category = groupby(products, key='category')

# 2. 名称归一化
def normalize_product_name(name: str) -> str:
    # 移除空格 (处理 "G304 X" vs "G304X")
    normalized = re.sub(r'\s+', '', name)
    # 统一大小写
    normalized = normalized.lower()
    # 移除品牌后缀 (避免 "Logitech G304" vs "G304" 无法匹配)
    normalized = re.sub(r'(lightspeed|wireless|gaming|rgb|pro|ultra|max|heroc|版|无线|有线)', '', normalized)
    # 移除特殊字符
    normalized = re.sub(r'[^a-z0-9\u4e00-\u9fff]', '', normalized)
    return normalized

# 3. 相似度计算
similarity = SequenceMatcher(
    None,
    normalize_product_name(name1),
    normalize_product_name(name2)
).ratio()

# 4. 防误合并硬规则
if category_i != category_j:
    return False  # 不同类别，不合并 (硬规则)

# 5. 合并判断
if similarity > 0.85:  # 阈值: 0.85 (见下方"阈值说明")
    # 合并 specs: 取并集 (非空字段优先)
    # 合并 analysis: 保留更完整的版本
    # 合并价格: 优先使用有价格的
    # 记录 merged_from_count
```

### 阈值配置与调参指南

```python
# etl_pipeline.py (建议提取为配置)
DEDUPLICATE_CONFIG = {
    'article_level': {
        'similarity_threshold': 0.6,      # 文章标题相似度
        'sort_by': 'publish_date',         # 排序字段
        'ascending': False                 # 降序 (最新的在前)
    },
    'product_level': {
        'similarity_threshold': 0.85,     # 产品名称相似度
        'category_must_match': True,       # 类别必须相同
        'priority_field': '_priority_score' # 优先级字段
    }
}
```

#### 阈值设计说明

| 阈值 | 设定值 | 原因 | 典型案例 |
|------|--------|------|----------|
| **文章级 0.6** | 0.6 | 宽松策略，避免遗漏同一产品的不同报道 | ✅ "罗技G Pro X Superlight" vs "罗技GPW新品" → 0.65 → 合并<br>❌ "罗技G304" vs "罗技G304 X" → 0.55 → 不合并 |
| **产品级 0.85** | 0.85 | 严格策略，避免误合并不同型号 | ✅ "VGN蜻蜓F1 Max" vs "VGN蜻蜓F1 MOBA" → 0.88 → 合并<br>❌ "VGN蜻蜓F1" vs "VGN蜻蜓F2" → 0.75 → 不合并 |

#### 调参指南

**何时调整文章级阈值 (0.6)**:

| 场景 | 建议值 | 理由 |
|------|--------|------|
| 网站标题格式统一 | 0.7 - 0.8 | 提高精确度，减少误合并 |
| 网站标题格式混乱 | 0.5 - 0.6 | 降低阈值，避免遗漏 |
| 标题包含大量修饰词 | 0.5 | 需要更宽松的匹配 |

**何时调整产品级阈值 (0.85)**:

| 场景 | 建议值 | 理由 |
|------|--------|------|
| 同系列产品多 (如 VGN 蜻蜓 F1/F2/F3) | 0.90 - 0.95 | 避免误合并不同型号 |
| 产品名称高度标准化 | 0.85 | 保持当前值 |
| 存在大量 OEM/ODM 同贴牌 | 0.80 | 允许合并同模具产品 |

**调参验证方法**:

```bash
# 1. 运行去重
python etl_pipeline.py --month 2026-01

# 2. 检查 merged_from_count 字段
cat output/processed_products.json | jq '.[].merged_from_count'

# 3. 人工抽查合并是否正确
# 如果 merged_from_count > 3，可能阈值过低，需要调高
# 如果存在明显重复产品未合并，需要调低阈值
```

### 防误合并硬规则

| 规则 | 说明 | 当前实现 | 优先级 |
|------|------|----------|--------|
| **类别一致性** | 不同类别的产品不合并 | ✅ 已实现 | P0 |
| **品牌差异保护** | 不同品牌的相似产品不合并 | ❌ 待实现 | P1 |
| **型号区分** | 同系列不同型号不合并 (如 F1 vs F2) | ⚠️ 部分实现 (依赖阈值) | P1 |
| **价格差异告警** | 价格差异 >50% 发出告警 | ❌ 待实现 | P2 |

**建议增强**:

```python
# 品牌差异保护 (P1)
BRANDS = ['罗技', '雷蛇', 'VGN', 'ATK', 'ZAOKEN', ...]

def extract_brand(product_name: str) -> Optional[str]:
    """提取产品品牌"""
    for brand in BRANDS:
        if brand in product_name:
            return brand
    return None

# 在合并前检查
if extract_brand(name1) != extract_brand(name2):
    return False  # 不同品牌，不合并
```

---

## LLM 错误处理与降级

### 非 JSON 响应处理

```python
# 流程 (extract_product_info_v2):
def extract_product_info_v2(self, context: Dict) -> Dict:
    try:
        # 1. 尝试直接解析 JSON
        extracted_data = json.loads(llm_response)
    except JSONDecodeError:
        # 2. 清理 markdown 代码块标记
        if llm_response.startswith('```'):
            llm_response = llm_response.split('```')[1]
            if llm_response.startswith('json'):
                llm_response = llm_response[4:]
        # 3. 再次尝试解析
        try:
            extracted_data = json.loads(llm_response)
        except JSONDecodeError:
            # 4. 记录失败并返回降级数据
            return {
                'error': 'JSON parse failed',
                'raw_response': llm_response[:500],  # 保留前 500 字符用于调试
                'product_name': context.get('title', 'Unknown')
            }
```

### Schema 校验

```python
# 必需字段检查
REQUIRED_FIELDS = ['product_name', 'category', 'specs', 'analysis']

for field in REQUIRED_FIELDS:
    if field not in extracted_data:
        raise ValueError(f"Missing required field: {field}")

# specs 子字段完整性 (completeness)
if category == '鼠标':
    critical_fields = MOUSE_SCHEMA.keys()
elif category == '键盘':
    critical_fields = KEYBOARD_SCHEMA.keys()

complete_fields = sum(1 for f in critical_fields if extracted_data['specs'].get(f))
completeness = complete_fields / len(critical_fields)

if completeness < 0.6:
    # 标记为 dropped (注意: 这里用 completeness，不是 coverage)
    return {
        'dropped': True,
        'reason': f'Completeness {completeness:.1%} < 60%',
        'completeness': completeness
    }
```

### 失败项降级策略

```python
# 策略 1: 重试机制
max_retries = 3
for attempt in range(max_retries):
    try:
        result = call_llm_api(prompt)
        break
    except Exception as e:
        if attempt == max_retries - 1:
            # 记录失败项
            failed_items.append({
                'index': idx,
                'reason': str(e),
                'product_name': product['product_name'],
                'attempt': max_retries
            })
            dropped_count += 1

# 策略 2: 保留原始数据
# 即使 LLM 分析失败，保留原始文章内容到 processed_products.json
# 便于后续人工补录或二次处理
```

### 错误日志格式

```json
// logs/failed_items_20260210_172540.json
[
  {
    "index": 3,
    "reason": "API调用失败，已达最大重试次数: 429 Client Error: Too Many Requests",
    "product_name": "某产品名",
    "attempt": 3,
    "timestamp": "2026-02-10T17:25:40"
  },
  {
    "index": 7,
    "reason": "Completeness 40% < 60%",
    "product_name": "另一产品名",
    "completeness": 0.4,
    "completeness_detail": {
      "total_fields": 15,
      "complete_fields": 6,
      "category": "鼠标"
    }
  }
]
```

---

## 报告校验规范

### DOM 结构校验 (当前实现)

```python
def _validate_html_structure(html_content: str) -> bool:
    """
    校验必需 DOM 元素的存在性

    必需组件:
        - nav-bar: 导航栏
        - searchInput: 搜索框
        - product-overview: 产品概览模块 (左栏)
        - product-specs: 硬核参数模块 (中栏)
        - product-analysis: PM 深度洞察模块 (右栏)
        - PM 深度洞察: PM 标题文本
    """
    required_components = {
        'nav-bar': r'<nav[^>]*id="nav-bar"',
        'searchInput': r'<input[^>]*id="searchInput"',
        'product-overview': r'<div[^>]*id="product-overview"',
        'product-specs': r'<div[^>]*id="product-specs"',
        'product-analysis': r'<div[^>]*id="product-analysis"',
        'PM 深度洞察': r'PM\s*深度洞察'
    }

    for name, pattern in required_components.items():
        if not re.search(pattern, html_content):
            raise AssertionError(f"[FAIL] 缺少必需组件: {name}")

    return True
```

### 四向一致性校验 (严谨实现)

```python
def validate_four_way_consistency(generator: HTMLReportGenerator) -> Dict[str, Any]:
    """
    四向一致性校验:

    1. nav_counts (导航栏统计) == section_counts (分区标题数)
    2. section_counts == chart_counts (品类图表数据)
    3. chart_counts == card_counts (产品卡片数)
    4. 每个图表: sum(data) == 统计对象数量

    不一致时:
        - 抛出 AssertionError (不是 warning)
        - 输出定位信息 (缺失/多算的产品 id 列表)
        - 阻止报告生成
    """
    issues = []

    # 提取各向数据
    nav_stats = _extract_nav_stats(generator.html)
    section_stats = _extract_section_stats(generator.html)
    chart_data = generator.market_analyzer.get_chart_data()
    card_count = len(generator.products)

    # 1. 导航栏 vs 分区标题
    if nav_stats != section_stats:
        diff = _diff_dict(nav_stats, section_stats)
        issues.append(f"导航栏与分区标题不一致: {diff}")

    # 2. 分区标题 vs 图表数据
    category_chart = {
        cat: count
        for cat, count in zip(chart_data['category_data']['labels'], chart_data['category_data']['data'])
    }

    if section_stats != category_chart:
        diff = _diff_dict(section_stats, category_chart)
        issues.append(f"分区标题与图表数据不一致: {diff}")

    # 3. 图表数据 vs 产品卡片
    total_chart = sum(chart_data['category_data']['data'])
    if total_chart != card_count:
        # 定位差异产品
        card_ids = set(p.get('id', p['product_name']) for p in generator.products)
        chart_ids = _extract_chart_product_ids(generator.html)
        missing = card_ids - chart_ids
        extra = chart_ids - card_ids
        issues.append(
            f"图表总数({total_chart}) != 卡片数({card_count})\n"
            f"  缺失产品: {list(missing)[:5]}\n"
            f"  多算产品: {list(extra)[:5]}"
        )

    # 4. 各图表内部一致性
    # 传感器图表: sum(data) == len(mice)
    sensor_chart_sum = sum(chart_data['sensor_dist'].values())
    mice_count = len(generator.mice)
    if sensor_chart_sum != mice_count:
        issues.append(f"传感器图表总和({sensor_chart_sum}) != 鼠标数({mice_count})")

    # 价格图表: sum(data) == len(products)
    price_chart_sum = sum(chart_data['price_ranges'].values())
    if price_chart_sum != card_count:
        issues.append(f"价格图表总和({price_chart_sum}) != 产品数({card_count})")

    # 判断是否通过
    if issues:
        error_msg = "[FAIL] 四向一致性校验失败:\n" + "\n".join(issues)
        raise AssertionError(error_msg)

    return {
        'passed': True,
        'nav_stats': nav_stats,
        'section_stats': section_stats,
        'chart_data': chart_data,
        'card_count': card_count
    }


def _diff_dict(d1: Dict, d2: Dict) -> Dict:
    """对比两个字典的差异"""
    diff = {}
    all_keys = set(d1.keys()) | set(d2.keys())
    for key in all_keys:
        v1 = d1.get(key, 0)
        v2 = d2.get(key, 0)
        if v1 != v2:
            diff[key] = {'d1': v1, 'd2': v2}
    return diff


def _extract_nav_stats(html: str) -> Dict:
    """从导航栏提取统计信息"""
    # 正则匹配: <a href="#mice">鼠标 (8)</a>
    pattern = r'<a href="#(\w+)">\w+\s*\((\d+)\)</a>'
    matches = re.findall(pattern, html)
    return {cat: int(count) for cat, count in matches}


def _extract_section_stats(html: str) -> Dict:
    """从分区标题提取统计信息"""
    # 正则匹配: <h2>鼠标新品 (8款)</h2>
    pattern = r'<h2>\w+新品\s*\((\d+)款\)</h2>'
    # 根据类别分组
    sections = re.findall(r'<h2>(\w+)新品\s*\((\d+)款\)</h2>', html)
    return {cat: int(count) for cat, count in sections}


def _extract_chart_product_ids(html: str) -> Set:
    """从图表中提取产品 id"""
    # 正则匹配产品卡片的 id 属性
    pattern = r'<div[^>]*id="product-card-([^"]+)"'
    return set(re.findall(pattern, html))
```

### 内容质量校验 (P2 可选)

```python
def validate_content_quality(generator: HTMLReportGenerator) -> Dict[str, Any]:
    """
    内容质量校验:
        - 失败项占比阈值
        - specs 完整性分布 (completeness)
        - coverage 统计
    """
    total = len(generator.products)
    failed = load_failed_items_count()

    if failed / total > 0.2:
        issues.append(f"⚠️  失败项占比过高: {failed}/{total} ({failed/total:.1%})")

    # completeness 分布 (单产品级别)
    completeness_distribution = {
        'high (>80%)': 0,
        'medium (50-80%)': 0,
        'low (<50%)': 0
    }

    for product in generator.products:
        completeness = calculate_specs_completeness(product['specs'])
        if completeness > 0.8:
            completeness_distribution['high (>80%)'] += 1
        elif completeness >= 0.5:
            completeness_distribution['medium (50-80%)'] += 1
        else:
            completeness_distribution['low (<50%)'] += 1

    # coverage 统计 (宏观数据)
    coverage = generator.market_analyzer.get_coverage_stats()

    return {
        'completeness_distribution': completeness_distribution,
        'coverage': coverage,
        'failed_ratio': failed / total
    }
```

---

## 配置与扩展

### 白名单/黑名单配置

```python
# etl_pipeline.py (lines 115-126)

# 白名单关键词 (包含任一关键词即保留)
KEYWORDS = [
    "鼠标", "键盘", "键鼠", "客制化", "轴体",
    "机械键盘", "磁轴",
    # "手柄"  # 默认注释，可通过 INCLUDE_GAMEPAD=True 启用
]

# 黑名单关键词 (包含任一关键词即排除)
BLACKLIST = [
    # 配件类
    "鼠标垫", "桌垫", "线材", "收纳包", "耳机架",
    "理线器", "脚贴", "防滑贴", "手托", "腕托",
    # 音频类
    "耳机", "音箱", "扬声器", "麦克风",
    # 其他外设
    "摄像头", "显示器", "支架", "hub", "集线器", "扩展坞"
]

# 手柄开关 (配置化)
INCLUDE_GAMEPAD = False  # 设为 True 以包含游戏手柄
if INCLUDE_GAMEPAD:
    KEYWORDS.append("手柄")
```

### Schema 定义

#### 鼠标 Top 15 参数 (MOUSE_SCHEMA)

```python
MOUSE_SCHEMA = {
    # 必填字段 (用于 completeness 评分)
    'product_pricing': '产品与定价',
    'mold_lineage': '模具血统',
    'weight_center': '重量与重心',
    'sensor_solution': '传感器方案',  # 用于图表统计
    'polling_rate': '回报率配置',
    # 可选字段
    'mcu_chip': '主控芯片',
    'end_to_end_latency': '全链路延迟',
    'switch_features': '微动特性',
    'scroll_encoder': '滚轮编码器',
    'coating_process': '涂层工艺',
    'high_refresh_battery': '高刷续航',
    'structure_quality': '结构做工',
    'feet_config': '脚贴配置',
    'wireless_interference': '无线抗干扰',
    'driver_experience': '驱动体验'
}
```

#### 键盘 Top 15 参数 (KEYBOARD_SCHEMA)

```python
KEYBOARD_SCHEMA = {
    # 必填字段
    'product_layout': '产品与配列',
    'structure_form': '结构形式',
    'switch_details': '轴体详解',  # 用于磁轴统计
    'tech_route': '技术路线',
    # 可选字段
    'rt_params': 'RT参数',
    'sound_dampening': '声音包填充',
    'measured_latency': '实测延迟',
    'keycap_craftsmanship': '键帽工艺',
    'bigkey_tuning': '大键调校',
    'pcb_features': 'PCB特性',
    'case_craftsmanship': '外壳工艺',
    'front_height': '前高数据',
    'battery_efficiency': '电池效率',
    'connection_storage': '连接与收纳',
    'software_support': '软体支持'
}
```

### 并发配置

```python
# etl_pipeline.py (lines 4787-4789)
CONCURRENT_CONFIG = {
    'batch_size': 5,          # 并发数
    'max_retries': 3,         # 失败重试次数
    'timeout': 120,           # 单次请求超时 (秒)
    'temperature': 0.1,       # LLM 温度参数
    'max_tokens': 3500        # LLM 最大 tokens
}

# 性能优化建议:
# - API 性能强时: batch_size=10
# - 内存有限时: batch_size=3
# - 高稳定性: batch_size=1 (串行)
```

### LLM API 配置

```python
# .env 文件配置
LLM_API_KEY=sk-your-api-key-here
LLM_API_BASE=http://192.168.0.250:7777  # 或 https://api.deepseek.com/v1
LLM_MODEL=xdeepseekv3                   # 或 deepseek-chat

# 支持 OpenAI 兼容格式的任何 API
```

---

## 隐私与安全

### 数据隐私保护

| 数据类型 | 存储位置 | 访问控制 | 保留期限 | 外发风险 |
|----------|----------|----------|----------|----------|
| 原始文章数据 | `output/report_data_YYYY_MM.json` | 本地文件系统 | 永久 | ❌ 无 |
| LLM 分析结果 | `output/processed_products.json` | 本地文件系统 | 永久 | ❌ 无 |
| 失败项日志 | `logs/failed_items_*.json` | 本地文件系统 | 永久 | ⚠️ 可能包含 snippet |
| 备份报告 | `output/*.html.bak` | 本地文件系统 | 永久 | ❌ 无 |

**隐私原则**:
- 所有数据存储在本地，不上传至云端 (除 LLM API 调用外)
- **LLM API 调用**: 会向 `LLM_API_BASE` 发送文章正文 (`content_text`) 用于分析
- 报告为静态 HTML，无用户追踪代码
- 日志不包含 API 密钥 (见下文)

### API 密钥管理

```bash
# .env 文件 (不提交到 Git)
LLM_API_KEY=sk-your-api-key-here

# 环境变量 (优先级更高)
export LLM_API_KEY=sk-your-api-key-here
```

**安全要求**:
- ✅ 使用 `.gitignore` 排除 `.env` 文件
- ✅ 定期轮换 API 密钥
- ✅ 使用内部 API 端点 (如 http://192.168.0.250:7777)
- ✅ 日志中不落密钥 (任何 print/logger 不得输出 LLM_API_KEY)
- ❌ 不要在代码中硬编码 API 密钥
- ❌ 不要将 `.env.example` 中的真实密钥提交到 Git

**日志脱敏示例**:

```python
import os

def log_llm_config(config: Dict):
    """安全地记录 LLM 配置"""
    api_key = config.get('api_key', '')
    # 脱敏: 只显示前 4 和后 4 字符
    masked_key = f"{api_key[:4]}...{api_key[-4:]}" if len(api_key) > 8 else "***"

    log_msg = f"LLM Config: model={config.get('model')}, base={config.get('base_url')}, key={masked_key}"
    print(log_msg)  # 安全输出
```

### 敏感内容过滤

```python
# 当前未实现，建议新增 (P1):
SENSITIVE_PATTERNS = [
    (r'\d{15,18}', '[身份证号]'),      # 身份证号
    (r'1[3-9]\d{9}', '[手机号]'),     # 手机号
    (r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', '[邮箱]'),  # 邮箱
    (r'password["\']?\s*[:=]\s*["\']?[^\s"\']+', '[密码]'),  # 密码字段
]

def sanitize_content(content: str) -> str:
    """
    过滤敏感内容

    用途:
        1. LLM 发送前脱敏 (防止敏感信息发送到 API)
        2. HTML 报告生成时脱敏 (防止报告泄露敏感信息)
    """
    for pattern, replacement in SENSITIVE_PATTERNS:
        content = re.sub(pattern, replacement, content, flags=re.IGNORECASE)
    return content

# 使用示例:
# LLM 发送前
sanitized_content = sanitize_content(product['content_text'])
llm_response = call_llm_api(sanitized_content)
```

### LLM API 数据外发声明

```
⚠️ 重要隐私提示:

本系统使用 LLM API 进行产品分析，以下数据会发送到 LLM_API_BASE:

  - 文章标题 (title)
  - 文章正文 (content_text)
  - 文章来源 (source)

不会发送:
  - 用户身份信息
  - API 密钥
  - 本地文件路径

如需启用敏感内容过滤，请在 config.py 中设置:
    SANITIZE_CONTENT = True
```

---

## 站点合规与反爬策略

### 爬虫行为规范

```python
# spider.py 配置
SPIDER_CONFIG = {
    'max_pages': 20,           # 每个站点最大爬取页数
    'request_delay': 2,        # 请求间隔 (秒) - 与 .env 保持一致
    'delay_jitter': 1.0,       # 随机抖动范围 (±1秒)
    'timeout': 30,             # 请求超时 (秒)
    'user_agent': 'Mozilla/5.0 ...',  # 固定真实浏览器 UA
    'respect_robots_txt': True # 遵守 robots.txt (建议新增)
}
```

### 速率限制

```python
# .env 配置 (与 SPIDER_CONFIG 保持一致)
SPIDER_DELAY_SECONDS=2       # 基础延迟 (推荐 2-4 秒)
SPIDER_DELAY_JITTER=1.0      # 随机抖动 (±1 秒)

# 当前实现 (隐式):
# - 单线程顺序爬取
# - 无显式 sleep (依赖网络延迟)

# 建议实现 (P0 优先级):
import time
import random

request_delay = float(os.getenv('SPIDER_DELAY_SECONDS', 2))
delay_jitter = float(os.getenv('SPIDER_DELAY_JITTER', 1.0))

for url in urls:
    response = fetch(url)
    time.sleep(request_delay + random.uniform(-delay_jitter, delay_jitter))
```

**抖动间隔推荐值**:

| Profile | 基础延迟 | 抖动范围 | 适用场景 |
|---------|----------|----------|----------|
| Conservative | 4s | ±2s (2-6s) | 严格反爬站点 |
| Standard | 2s | ±1s (1-3s) | 默认推荐 |
| Aggressive | 1s | ±0.5s (0.5-1.5s) | 本地测试 |

### User-Agent 策略

```python
# 当前: 固定真实 UA
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

# 建议配置化 (P1 优先级):
# .env 配置
SPIDER_UA_ROTATE=false  # false=固定真实UA, true=轮换UA
SPIDER_UA_LIST='Mozilla/5.0 ...;Chrome/119.0.0.0 ...;Safari/17.0 ...'

USER_AGENTS = os.getenv('SPIDER_UA_LIST', USER_AGENT).split(';')

def get_user_agent() -> str:
    """获取 User-Agent"""
    if os.getenv('SPIDER_UA_ROTATE', 'false').lower() == 'true':
        return random.choice(USER_AGENTS)
    return USER_AGENTS[0]  # 默认固定第一个

# ⚠️ 重要: UA "轮换"表述不准确，实际应为"可配置/真实固定"
# - 固定真实 UA: 模拟真实浏览器，避免被识别为爬虫
# - 轮换真实 UA: 在多个真实 UA 间切换，降低封禁风险
# - 不建议: 使用伪造/明显错误的 UA
```

### robots.txt 遵守 (P0 优先级)

```python
# 当前未实现，建议新增:
from urllib.robotparser import RobotFileParser

ROBOT_PARSER_CACHE = {}  # 缓存 robots.txt 解析结果

def can_fetch(url: str, user_agent: str = '*') -> bool:
    """
    检查是否允许爬取该 URL

    遵守 robots.txt 规则:
        - User-agent: * 适用于所有爬虫
        - Disallow: /admin  禁止爬取 /admin 路径
        - Allow: /public  允许爬取 /public 路径
    """
    from urllib.parse import urlparse

    parsed = urlparse(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"

    if base_url not in ROBOT_PARSER_CACHE:
        rp = RobotFileParser()
        rp.set_url(f"{base_url}/robots.txt")
        try:
            rp.read()
            ROBOT_PARSER_CACHE[base_url] = rp
        except Exception as e:
            print(f"[WARNING] 无法读取 robots.txt: {base_url}, {e}")
            return True  # 无法读取时默认允许

    rp = ROBOT_PARSER_CACHE[base_url]
    return rp.can_fetch(user_agent, parsed.path)

# 使用示例:
for url in urls:
    if not can_fetch(url):
        print(f"[SKIP] robots.txt 禁止爬取: {url}")
        continue
    response = fetch(url)
```

### 站点友好策略

| 策略 | 当前实现 | 建议优先级 | 推荐配置 |
|------|----------|------------|----------|
| 请求间隔 | 隐式 (网络延迟) | P0: 显式 sleep | 2s ± 1s jitter |
| User-Agent | 固定 | P1: 可配置 | 固定真实 UA |
| robots.txt | ❌ 未遵守 | P0: 添加检查 | 遵守 Disallow 规则 |
| 并发限制 | 单线程 | P2: 可配置并发 | 默认单线程 |
| 错误重试 | 无 | P1: 指数退避 | 2^attempt 秒延迟 |
| 最大页数 | 20 页/站点 | P1: 可配置 | 20-50 页 |

### 法律合规

**数据使用规范**:
- ✅ 仅用于个人/公司内部分析
- ✅ 不用于商业竞争或恶意用途
- ✅ 注明数据来源 (如 "数据来源: in外设")
- ❌ 不转售或公开发布爬取的数据
- ❌ 不用于训练竞品模型

**建议添加免责声明**:
```html
<!-- 在 HTML 报告底部添加 -->
<footer>
  <p>数据来源: in外设、外设天下 | 仅供内部参考，严禁外传</p>
  <p>本报告由 AI 自动生成，部分数据可能存在误差，请以官方信息为准</p>
  <p>生成时间: 2026-02-10 | 系统版本: v1.0</p>
</footer>
```

---

## 故障排查手册

### 常见问题

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| `KeyError: '未知'` | 传感器分布字典中'未知'桶不存在 | ✅ 已修复: 使用 `.get('未知', 0)` |
| `AssertionError: 统计口径不一致` | 导航栏/图表/卡片数量不一致 | 检查四向一致性校验 |
| `JSONDecodeError` | LLM 返回非 JSON 格式 | 检查 `extract_product_info_v2()` 解析逻辑 |
| `429 Too Many Requests` | API 速率限制 | 降低 `batch_size` 或增加 `SPIDER_DELAY_SECONDS` |
| `UnicodeEncodeError` | Windows 控制台编码问题 | 功能正常，可忽略或使用 UTF-8 终端 |
| `Coverage < 50%` | 数据质量差，大量字段未提取 | 检查 LLM Prompt 和输入数据质量 |

### 调试模式

```python
# 启用调试输出
DEBUG = True
LOG_LEVEL = 'DEBUG'

# 查看调试信息:
# [DEBUG-CHART] 传感器分布结果: {...}
# [DEBUG-LLM] specs非空字段: [...]
```

### 日志文件

```
logs/
├── failed_items_20260210_172540.json  # 失败项详情
└── spider.log                         # 爬虫日志 (可选)
```

---

## 变更点摘要 (v1.0 → v1.1)

### 1. 缺失值 Taxonomy 修正

```diff
@@ v1.0 缺失值定义 @@
- | 未知 | LLM 无法推断的参数 (已废弃) | 统一替换为"未提及" |

@@ v1.1 严谨定义 @@
+ | 标记值 | 产生场景 | 图表桶 | Coverage |
+ |--------|----------|--------|----------|
+ | 未提及 | 原文完全没有该信息 | ❌ 不计入 | ❌ 不计入 |
+ | 未公开 | 原文明确说明未公布 | ✅ 独立桶 | ❌ 不计入 |
+ | 提取失败 | LLM 未能成功提取 | ❌ 不计入 | ❌ 不计入 |
+ | 无法判断 | LLM 无法推断来源 | ❌ 不计入 | ❌ 不计入 |
+ | 待实测 | 新品未上市需实测 | ✅ 独立桶 | ❌ 不计入 |
+ | 概念产品 | 仅概念/渲染图 | ✅ 独立桶 | ❌ 不计入 |
+ | 未知 | 已废弃 → 替换为"提取失败" | - | - |
```

### 2. Coverage 公式改写

```diff
@@ v1.0 Coverage 定义 @@
- Coverage = 有效字段数量 / 总样本数量

@@ v1.1 严谨口径 @@
+ Coverage = 有有效值的产品数 / 统计对象产品总数
+
+ 概念区分:
+ - Coverage: 某字段有有效值的占比 (宏观数据质量)
+ - Completeness: 单产品 specs 字段完整度 (产品级质量)
+
+ 逐字段定义:
+ - 传感器覆盖率: 统计对象 = 所有鼠标产品
+ - 价格覆盖率: 统计对象 = 所有产品 (鼠标+键盘+其他)
```

### 3. 一致性校验增强

```diff
@@ v1.0 一致性校验 @@
- 三向一致性校验 (建议):
- 1. 导航栏统计 == 产品卡片
- 2. 分区标题 == 品类图表
- 3. 图表数据 == HTML 卡片

@@ v1.1 四向一致性 + 失败定位 @@
+ 四向一致性校验 (严谨实现):
+ 1. nav_counts == section_counts
+ 2. section_counts == chart_counts
+ 3. chart_counts == card_counts
+ 4. 每个图表: sum(data) == 统计对象数量
+
+ 不一致时:
+ - 抛出 AssertionError (FAIL 而非 WARNING)
+ - 输出定位信息 (缺失/多算的产品 id 列表)
+ - 阻止报告生成
```

### 4. 站点合规表述更一致

```diff
@@ v1.0 抖动间隔 @@
- request_delay = 2  # 基础延迟
- jitter = random.uniform(0.5, 1.5)  # 随机抖动

@@ v1.1 与 .env 保持一致 @@
+ # .env 配置
+ SPIDER_DELAY_SECONDS=2       # 推荐值: 2-4秒
+ SPIDER_DELAY_JITTER=1.0      # 抖动范围: ±1秒
+
+ request_delay = float(os.getenv('SPIDER_DELAY_SECONDS', 2))
+ jitter = float(os.getenv('SPIDER_DELAY_JITTER', 1.0))

@@ v1.0 UA 轮换 @@
- User-Agent 轮换

@@ v1.1 准确表述 @@
+ User-Agent 策略:
+ - 固定真实 UA (默认): 模拟真实浏览器
+ - 可配置真实 UA: 在多个真实 UA 间切换
+ - 不建议使用伪造/错误 UA
```

### 5. 隐私与安全表述更准确

```diff
@@ v1.0 数据隐私 @@
- 所有数据存储在本地，不上传至云端 (除 LLM API 调用外)

@@ v1.1 明确外发范围 +
+ LLM API 调用会发送:
+ - 文章标题 (title)
+ - 文章正文 (content_text)
+ - 文章来源 (source)
+
+ 不会发送:
+ - 用户身份信息
+ - API 密钥
+ - 本地文件路径
+
+ 脱敏建议:
+ - 日志不落密钥: 使用脱敏格式 sk-xxx...xxxx
+ - 敏感内容过滤: 身份证号/手机号/邮箱/密码
```

### 6. 去重阈值补充说明

```diff
@@ v1.0 阈值配置 @@
- 'similarity_threshold': 0.6,  # 文章标题相似度
- 'similarity_threshold': 0.85, # 产品名称相似度

@@ v1.1 为何这么设 + 如何调参 +
+ | 阈值 | 设定值 | 原因 | 典型案例 |
+ |------|--------|------|----------|
+ | 文章级 0.6 | 0.6 | 宽松策略，避免遗漏 | "罗技G Pro X" vs "罗技GPW新品" → 0.65 → 合并 |
+ | 产品级 0.85 | 0.85 | 严格策略，避免误合并 | "VGN蜻蜓F1" vs "VGN蜻蜓F2" → 0.75 → 不合并 |
+
+ 调参指南:
+ - 网站标题统一: 0.7-0.8
+ - 同系列产品多: 0.90-0.95
+ - 调参验证: 检查 merged_from_count 字段
```

---

## 📞 技术支持

如有问题或建议，请提交 GitHub Issue。

**文档版本**: v1.1 (严谨修订版)
**最后更新**: 2026-02-10
**维护者**: Claude Code Assistant
