"""
外设新品监控报告生成系统 (Phase 4 最终优化版)
功能：数据清洗、LLM PM视角深度分析、深色极客风 HTML 报告生成
"""

import pandas as pd
import json
import re
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from difflib import SequenceMatcher
import requests
from typing import Dict, List, Optional, Any
from itertools import combinations

# ==================== 配置区 ====================

# 目标年月配置
TARGET_YEAR = 2026
TARGET_MONTH = 1

# LLM API 配置（公司内部 DeepSeek V3）
LLM_CONFIG = {
    "provider": "deepseek",
    "api_key": "sk-xxx",  # 公司内部 API Key
    "model": "xdeepseekv3",  # 内部模型名称
    "base_url": "http://192.168.0.250:7777"  # 内部 API 地址
}

# ==================== Top 15 标准化数据 Schema（中文版）====================

# 🖱️ 鼠标 Top 15 参数定义（中文版）
MOUSE_SCHEMA = {
    # 产品与定价
    'product_pricing': '产品与定价',
    # 模具血统
    'mold_lineage': '模具血统',
    # 重量与重心
    'weight_center': '重量与重心',
    # 传感器方案
    'sensor_solution': '传感器方案',
    # 主控芯片
    'mcu_chip': '主控芯片',
    # 回报率配置
    'polling_rate': '回报率配置',
    # 全链路延迟
    'end_to_end_latency': '全链路延迟',
    # 微动特性
    'switch_features': '微动特性',
    # 滚轮编码器
    'scroll_encoder': '滚轮编码器',
    # 涂层工艺
    'coating_process': '涂层工艺',
    # 高刷续航
    'high_refresh_battery': '高刷续航',
    # 结构做工
    'structure_quality': '结构做工',
    # 脚贴配置
    'feet_config': '脚贴配置',
    # 无线抗干扰
    'wireless_interference': '无线抗干扰',
    # 驱动体验
    'driver_experience': '驱动体验'
}

# ⌨️ 键盘 Top 15 参数定义（中文版）
KEYBOARD_SCHEMA = {
    # 产品与配列
    'product_layout': '产品与配列',
    # 结构形式
    'structure_form': '结构形式',
    # 技术路线
    'tech_route': '技术路线',
    # RT参数
    'rt_params': 'RT参数',
    # 声音包填充
    'sound_dampening': '声音包填充',
    # 轴体详解
    'switch_details': '轴体详解',
    # 实测延迟
    'measured_latency': '实测延迟',
    # 键帽工艺
    'keycap_craftsmanship': '键帽工艺',
    # 大键调校
    'bigkey_tuning': '大键调校',
    # PCB特性
    'pcb_features': 'PCB特性',
    # 外壳工艺
    'case_craftsmanship': '外壳工艺',
    # 前高数据
    'front_height': '前高数据',
    # 电池效率
    'battery_efficiency': '电池效率',
    # 连接与收纳
    'connection_storage': '连接与收纳',
    # 软体支持
    'software_support': '软体支持'
}

# 关键字段定义（用于检查完整性）
MOUSE_CRITICAL_FIELDS = ['product_pricing', 'mold_lineage', 'weight_center', 'sensor_solution', 'polling_rate']
KEYBOARD_CRITICAL_FIELDS = ['product_layout', 'structure_form', 'switch_details', 'tech_route']

# Schema 映射（用于快速访问）
CATEGORY_SCHEMAS = {
    '鼠标': MOUSE_SCHEMA,
    '键盘': KEYBOARD_SCHEMA
}

# 关键词列表（白名单）
KEYWORDS = [
    "鼠标", "键盘", "键鼠", "客制化", "轴体",
    "机械键盘", "磁轴", "手柄"
]

# 黑名单关键词（直接过滤掉 - 仅保留键盘和鼠标）
BLACKLIST = [
    "鼠标垫", "桌垫", "线材", "收纳包", "耳机架", "耳机架",
    "理线器", "脚贴", "防滑贴", "手托", "腕托",
    "耳机", "耳机", "音箱", "扬声器", "麦克风", "摄像头",
    "显示器", "支架", "hub", "集线器", "扩展坞"
]

# ==================== 字段值判定标准 (口径-实现一致性) ====================
"""
总原则: 展示有效 vs 统计有效

- 展示有效: 用于前端图表显示，包括"未公开"、"待实测"等描述性值
- 统计有效: 用于 coverage 计算，仅包括有实际内容的值

三种判定函数:
1. is_coverage_value(): 统计有效 → 用于 coverage 计算的分子
2. bucket_value(): 展示有效 → 用于图表分桶
3. is_display_value(): 前端显示 → 用于前端展示（过滤"未提及"等）
"""

# 完全无效值 (不计入任何统计)
INVALID_VALUES = ['', 'null', 'none', 'unknown', 'N/A', '未知']

# 统计无效但展示有效的值 (不计入 coverage 分子，但计入图表桶)
BUCKET_ONLY_VALUES = ['未公开', '待定', '待实测', '暂无', 'TBD']

# 统计有效值 (计入 coverage 分子)
# 包括: 任何具体的参数值 (如 "PAW3395", "99元", "有线" 等)

# 价格分桶专用: "未公开"桶只接受这些明确标记
PRICE_UNDISCLOSED_MARKERS = ['未公开', '待定', '暂无', 'TBD', '待公布']

# 汇率配置 (默认不跨币种换算)
ENABLE_CURRENCY_CONVERSION = False
DEFAULT_CURRENCY = 'CNY'

EXCHANGE_RATES = {
    'USD': 7.2, '$': 7.2,
    'JPY': 0.048, '¥': 0.048,
    'EUR': 7.8,
    'CNY': 1.0, '¥': 1.0, '元': 1.0
}

# ==================== 二次补全配置 (Phase 3 - 必经流程) ====================
# [FIX E] 二次补全改为必经流程，不再支持开关关闭
# 以下配置仅用于"上限控制/成本限制"，不影响是否执行

# 兼容性检查：检测用户是否设置了已废弃的开关
_LEGACY_ENABLED_ENV = os.getenv('SECOND_ROUND_ENABLED', '').lower()
_LEGACY_COMPLETION_ENABLED_ENV = os.getenv('SECOND_ROUND_COMPLETION_ENABLED', '').lower()
_HAS_LEGACY_DISABLE_FLAG = (_LEGACY_ENABLED_ENV == 'false' or _LEGACY_COMPLETION_ENABLED_ENV == 'false')

# 二次补全模式：local 为必跑模式
SECOND_ROUND_MODE = os.getenv('SECOND_ROUND_MODE', 'local')  # local|search|both
# 注：local 模式始终执行；search/both 作为增强模式叠加

# 上限控制配置
SECOND_ROUND_MAX_ITEMS = int(os.getenv('SECOND_ROUND_MAX_ITEMS', '10'))
SECOND_ROUND_MAX_FIELDS_PER_ITEM = int(os.getenv('SECOND_ROUND_MAX_FIELDS_PER_ITEM', '6'))
SECOND_ROUND_MAX_SEARCH_PER_PRODUCT = int(os.getenv('SECOND_ROUND_MAX_SEARCH_PER_PRODUCT', '2'))

# 关键字段定义（用于二次补全优先级排序）
MOUSE_KEY_FIELDS_PRIORITY = ['sensor_solution', 'weight_center', 'polling_rate', 'connection_storage']
KEYBOARD_KEY_FIELDS_PRIORITY = ['switch_details', 'connection_storage', 'battery_efficiency', 'product_layout']

# 口径保护：inferred 是否计入 coverage（默认 false）
COUNT_INFERRED_IN_COVERAGE = os.getenv('COUNT_INFERRED_IN_COVERAGE', 'false').lower() == 'true'

# ==================== 字段判定函数 ====================

def is_coverage_value(value: Any) -> bool:
    """
    判断值是否统计有效 (用于 coverage 计算)

    规则:
        - 非空、非纯空白
        - 不在 INVALID_VALUES 中
        - 不在 BUCKET_ONLY_VALUES 中 (如"未公开"、"待实测")
        - 不为 "未提及"、"提取失败"、"无法判断"

    用途:
        - 计算覆盖率: coverage = 统计有效数 / 总数
        - 过滤出有实际内容的值用于质量评估

    Args:
        value: 待判断的值

    Returns:
        bool: True 表示统计有效

    示例:
        >>> is_coverage_value("PAW3395")
        True
        >>> is_coverage_value("未公开")
        False  # "未公开"不计入 coverage 分子
        >>> is_coverage_value("待实测")
        False  # "待实测"不计入 coverage 分子
        >>> is_coverage_value("")
        False
    """
    if value is None:
        return False

    if not isinstance(value, (str, int, float, bool)):
        return False

    value_str = str(value).strip()

    # 空值
    if not value_str:
        return False

    # 完全无效值
    if value_str.lower() in [v.lower() for v in INVALID_VALUES]:
        return False

    # 展示有效但统计无效的值
    if value_str in BUCKET_ONLY_VALUES:
        return False

    # 明确的"无效描述"
    if value_str in ['未提及', '提取失败', '无法判断']:
        return False

    # 其他任何字符串都视为统计有效
    return True


def bucket_value(value: Any) -> Optional[str]:
    """
    获取用于图表分桶的值 (展示有效)

    规则:
        - 完全无效值 → None (不计入图表)
        - "未公开"类值 → "未公开" (单独桶)
        - "待实测"类值 → "待实测" (单独桶)
        - 其他值 → 原值

    用途:
        - 图表分桶 (如价格区间、传感器分布)
        - 前端展示

    Args:
        value: 待判断的值

    Returns:
        Optional[str]: 分桶值，None 表示不计入图表

    示例:
        >>> bucket_value("PAW3395")
        'PAW3395'
        >>> bucket_value("未公开")
        '未公开'
        >>> bucket_value("")
        None  # 空值不计入图表
        >>> bucket_value("未提及")
        None  # "未提及"不计入图表
    """
    if value is None:
        return None

    value_str = str(value).strip()

    # 空值
    if not value_str or value_str.lower() in [v.lower() for v in INVALID_VALUES]:
        return None

    # 统计无效但展示有效的值 (归入单独桶)
    if value_str in BUCKET_ONLY_VALUES:
        return value_str

    # 明确的"无效描述"不计入图表
    if value_str in ['未提及', '提取失败', '无法判断']:
        return None

    return value_str


def is_display_value(value: Any) -> bool:
    """
    判断值是否前端显示有效

    规则:
        - 非空
        - 不在 INVALID_VALUES 中
        - 不为 "未提及"、"提取失败"、"无法判断"
        - "未公开"、"待实测" 等可以显示

    用途:
        - 前端展示时过滤无效值
        - 生成 HTML 时判断是否显示该字段

    Args:
        value: 待判断的值

    Returns:
        bool: True 表示前端显示有效

    示例:
        >>> is_display_value("PAW3395")
        True
        >>> is_display_value("未公开")
        True  # "未公开"可以显示
        >>> is_display_value("未提及")
        False  # "未提及"不显示
        >>> is_display_value("")
        False
    """
    if value is None:
        return False

    value_str = str(value).strip()

    # 空值
    if not value_str:
        return False

    # 完全无效值
    if value_str.lower() in [v.lower() for v in INVALID_VALUES]:
        return False

    # 明确的"无效描述"不显示
    if value_str in ['未提及', '提取失败', '无法判断']:
        return False

    # 其他任何字符串都显示 (包括"未公开"、"待实测")
    return True


def normalize_innovation_tags(tags: List[str]) -> List[str]:
    """
    归一化创新标签

    规则:
        1. 去掉 # 前缀
        2. 全半角统一 (# ＃ → #)
        3. 去重
        4. 过滤空标签

    Args:
        tags: 原始标签列表

    Returns:
        List[str]: 归一化后的标签列表

    示例:
        >>> normalize_innovation_tags(["#卷王", "＃磁轴", "磁轴"])
        ['卷王', '磁轴']
    """
    if not tags:
        return []

    normalized = []
    seen = set()

    for tag in tags:
        if not isinstance(tag, str):
            continue

        # 去掉 # 前缀
        tag = tag.lstrip('#')

        # 全半角统一 (＃ → #, 全角空格 → 半角空格)
        tag = tag.replace('＃', '#').replace('　', ' ').replace('，', ',').strip()

        # 去重
        if tag and tag not in seen:
            seen.add(tag)
            normalized.append(tag)

    return normalized


# ==================== 二次补全框架 (Phase 3 - 可用功能) ====================
# [FIX D] 二次补全框架 - 检测缺失字段 + 同源补全 + 跨源补全(可选)

def detect_missing_fields(products: List[Dict]) -> List[Dict]:
    """
    [FIX B] 检测产品中缺失的关键字段，输出补全计划

    Args:
        products: 产品列表

    Returns:
        List[Dict]: 补全计划，每个元素包含:
            - product_id: 产品索引
            - product_name: 产品名称
            - category: 品类
            - missing_fields: 缺失字段列表
            - reason_map: 字段->缺失原因映射
    """
    missing_plan = []

    for idx, product in enumerate(products):
        category = product.get('category', '')
        specs = product.get('specs', {})

        # 根据品类确定关键字段
        if category == '鼠标':
            critical_fields = MOUSE_CRITICAL_FIELDS
        elif category == '键盘':
            critical_fields = KEYBOARD_CRITICAL_FIELDS
        else:
            continue

        missing = []
        reason_map = {}

        for field in critical_fields:
            value = specs.get(field, '')
            value_str = str(value).lower().strip() if value else ''

            # [FIX B.1] 判定字段状态
            if not value or not value_str:
                # 空值 → 需要补全
                missing.append(field)
                reason_map[field] = 'missing'
            elif any(marker in value_str for marker in [
                '未提及', '原文未提及', '未提供', '提取失败', '无法判断'
            ]):
                # 缺失状态 → 需要补全
                missing.append(field)
                reason_map[field] = 'extract_failed'
            elif any(marker in value_str for marker in [
                '未公开', 'tbd', '待公布'
            ]):
                # 未公开 → 不需要补全（厂商确实没公布）
                reason_map[field] = 'undisclosed'
            elif any(marker in value_str for marker in [
                '待实测', '预估', '推断', '推测'
            ]):
                # 待实测/预估 → 暂不需要补全
                reason_map[field] = 'pending'
            # else: 有明确值，不需要处理

        if missing:
            # [FIX B.3] 按优先级排序缺失字段
            priority_fields = MOUSE_KEY_FIELDS_PRIORITY if category == '鼠标' else KEYBOARD_KEY_FIELDS_PRIORITY
            missing.sort(key=lambda f: priority_fields.index(f) if f in priority_fields else 999)

            missing_plan.append({
                'product_id': idx,
                'product_name': product.get('product_name', 'Unknown')[:50],
                'category': category,
                'missing_fields': missing,
                'reason_map': reason_map
            })

    return missing_plan


def _extract_from_html_or_text(text: str, field: str, category: str) -> Dict:
    """
    [FIX C.2] 从文章内容中提取字段值（规则/正则优先）

    Args:
        text: 文章内容
        field: 目标字段名
        category: 品类

    Returns:
        Dict: {value, evidence_snippet, confidence, source}
    """
    if not text:
        return {'value': None, 'evidence_snippet': '', 'confidence': None, 'source': 'local'}

    text_lower = text.lower()

    # 定义字段提取规则（正则表达式）
    extraction_rules = {
        # 鼠标字段
        'sensor_solution': [
            (r'(?:PAW|paw)(\d{4})', 'PAW传感器'),
            (r'(?:HERO|Hero)(?:\s*)(\d+[kK]?)', 'Hero系列'),
            (r'(?:PMW|pmw)(\d{4})', 'PMW传感器'),
            (r'(?:原相|pixart)[^。]{0,30}?(\d{4})', '原相传感器'),
        ],
        'weight_center': [
            (r'重量[：:]\s*(\d+(?:\.\d+)?)\s*[gg克]', '重量'),
            (r'(\d+(?:\.\d+)?)\s*[gg克](?:\s*重量)', '重量'),
            (r'裸重[：:]\s*(\d+(?:\.\d+)?)\s*[gg克]', '裸重'),
        ],
        'polling_rate': [
            (r'(?:回报率|刷新率)[：:]\s*(1000|2000|4000|8000)\s*[hH][zZ]', '回报率'),
            (r'(1000|2000|4000|8000)\s*[hH][zZ](?:\s*(?:回报率|刷新率))', '回报率'),
        ],
        'connection_storage': [
            (r'(?:连接|支持)[^。]{0,50}?((?:有线|无线|蓝牙|2\.4G)[^。]{0,30})', '连接方式'),
            (r'(?:三模|双模)(?:连接)?[^。]{0,30}', '连接方式'),
        ],
        # 键盘字段
        'switch_details': [
            (r'(?:轴体)[：:][^。]{1,50}?((?:佳隆|凯华|TTC|cherry)[^。]{0,30})', '轴体'),
            (r'(?:磁轴|机械轴|静电容|光轴)[^。]{0,30}', '轴体类型'),
        ],
        'product_layout': [
            (r'(?:配列|布局)[：:]\s*(\d+[%％]?配列|全尺寸|75%|80%|87%|60%|40%|96%)', '配列'),
            (r'(?:全尺寸|75%|80%|87%|60%|40%|96%)(?:\s*(?:配列|布局|键盘))', '配列'),
        ],
        'battery_efficiency': [
            (r'(?:电池|续航)[：:][^。]{0,50}?(\d+(?:\.\d+)?\s*[mM][aA][hH])', '电池容量'),
            (r'(?:续航)[：:]\s*(\d+(?:\.\d+)?\s*[小时h]+)', '续航时间'),
        ],
    }

    # 获取该字段的提取规则
    rules = extraction_rules.get(field, [])

    for pattern, desc in rules:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            value = match.group(1) if match.groups() else match.group(0)

            # 提取证据片段（匹配位置前后各30字符）
            start, end = match.span()
            snippet_start = max(0, start - 30)
            snippet_end = min(len(text), end + 30)
            evidence = text[snippet_start:snippet_end].replace('\n', ' ').strip()

            return {
                'value': value,
                'evidence_snippet': evidence,
                'confidence': 'explicit',
                'source': 'local',
                'method': 'regex'
            }

    # 规则未命中，返回 None（需要 LLM 提取）
    return {'value': None, 'evidence_snippet': '', 'confidence': None, 'source': 'local'}


def _extract_with_llm(text: str, field: str, category: str) -> Dict:
    """
    [FIX C.2] 使用 LLM 从证据片段中提取字段值

    [FIX E] 强约束验证：
        - 输出必须含 confidence（inferred/missing）与 evidence_snippet
        - evidence_snippet 不包含明确线索时必须返回 missing（禁止猜测）

    Args:
        text: 文章内容
        field: 目标字段名
        category: 品类

    Returns:
        Dict: {value, evidence_snippet, confidence, source, method}
    """
    # 截取包含关键词的上下文（3-8句话）
    field_keywords = {
        'sensor_solution': ['传感器', '感光', '主控', 'PAW', 'PMW', 'Hero'],
        'weight_center': ['重量', '克', 'g', 'g±'],
        'polling_rate': ['回报率', 'Hz', '刷新', '1000', '2000', '4000', '8000'],
        'connection_storage': ['连接', '无线', '蓝牙', '有线', '三模', '双模', '2.4G'],
        'switch_details': ['轴体', '轴', '开关', '佳隆', '凯华', 'TTC', 'cherry', '磁轴'],
        'product_layout': ['配列', '布局', '尺寸', '键数', '75%', '80%', '87%', '60%', '96%'],
        'battery_efficiency': ['电池', '续航', 'mAh', '小时', '天'],
    }

    keywords = field_keywords.get(field, [field])

    # 查找包含关键词的句子
    sentences = re.split(r'[。！？\n]', text)
    evidence_sentences = []
    for sentence in sentences:
        if any(kw in sentence for kw in keywords):  # 不使用 lower() 保留中文关键词
            evidence_sentences.append(sentence.strip())
            if len(evidence_sentences) >= 3:
                break

    if not evidence_sentences:
        return {'value': None, 'evidence_snippet': '', 'confidence': 'missing', 'source': 'local'}

    evidence_text = '。'.join(evidence_sentences[:5])  # 最多5句

    # 构造 LLM 提示（强调严格提取）
    prompt = f"""从以下文章片段中提取"{field}"字段的值。

【重要约束】：
1. 只从提供的片段中提取，如果片段中没有明确信息则返回 null
2. 严禁猜测或推断，不确定时返回 null
3. 必须返回具体的数值或型号，不能是模糊描述

品类: {category}
目标字段: {field}

文章片段:
{evidence_text}

请以 JSON 格式输出：
{{
  "value": "提取的具体值（如果片段中没有明确信息则返回 null）",
  "evidence_snippet": "支持该值的原文片段（直接引用）"
}}
"""

    try:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {LLM_CONFIG['api_key']}"
        }
        data = {
            "model": LLM_CONFIG["model"],
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.0,  # 降低随机性，更严格
            "max_tokens": 500
        }
        base_url = LLM_CONFIG["base_url"].rstrip('/')
        url = f"{base_url}/v1/chat/completions"

        response = requests.post(url, headers=headers, json=data, timeout=30)
        response.raise_for_status()
        result = response.json()

        content = result["choices"][0]["message"]["content"]

        # 解析 JSON 响应
        json_match = re.search(r'\{[^}]+\}', content, re.DOTALL)
        if json_match:
            extracted = json.loads(json_match.group(0))
            value = extracted.get('value')
            snippet = extracted.get('evidence_snippet', '')

            # [FIX E] 强约束验证：必须有明确的线索
            if value and value.lower() not in ['null', 'none', '未知', '未提及', 'n/a', '']:
                # 验证 evidence_snippet 是否包含相关关键词
                snippet_lower = snippet.lower()
                has_keyword = any(kw.lower() in snippet_lower for kw in keywords)

                # 验证值本身是否包含具体信息（不是模糊描述）
                value_lower = str(value).lower()
                is_vague = any(marker in value_lower for marker in [
                    '未知', '未提及', '未公开', '暂无', '待定', 'tbd', '不详',
                    '可能', '或许', '应该', '估计'
                ])

                if has_keyword and not is_vague:
                    # 通过验证：返回 inferred 结果
                    return {
                        'value': value,
                        'evidence_snippet': snippet[:200] if snippet else evidence_text[:100],
                        'confidence': 'inferred',
                        'source': 'local',
                        'method': 'llm'
                    }
                else:
                    # 未通过验证：证据不足，返回 missing
                    print(f"      [LLM验证失败] {field}: 证据不足（无明确关键词或值模糊）")
                    return {'value': None, 'evidence_snippet': '', 'confidence': 'missing', 'source': 'local'}
            else:
                # LLM 返回 null 或无效值
                return {'value': None, 'evidence_snippet': '', 'confidence': 'missing', 'source': 'local'}

    except Exception as e:
        print(f"      [LLM提取失败] {field}: {str(e)[:50]}")

    return {'value': None, 'evidence_snippet': '', 'confidence': 'missing', 'source': 'local'}


def enrich_missing_fields_local(products: List[Dict], missing_plan: List[Dict]) -> tuple:
    """
    [FIX C] P0 同源补全 - 从已抓取文章内容中提取字段值

    [FIX E] 改为必经流程，始终执行

    Args:
        products: 产品列表
        missing_plan: 缺失字段计划

    Returns:
        tuple: (enriched_products, stats)
            - enriched_products: 补全后的产品列表
            - stats: 统计信息 {total_enriched, fields_by_method}
    """
    # [FIX E] 移除开关检查，始终执行
    # 仅在 search 模式下跳过 local 补全（但 search 模式尚未实现）
    if SECOND_ROUND_MODE == 'search':
        print("\n[二次补全-同源] 跳过（search 模式仅执行跨源补全，功能预留中）")
        return products, {'total_enriched': 0, 'fields_by_method': {}}

    print(f"\n[二次补全-同源] 开始处理 {len(missing_plan)} 个产品的缺失字段...")

    enriched_products = products.copy()
    stats = {
        'total_enriched': 0,
        'fields_by_method': {'regex': 0, 'llm': 0},
        'products_enriched': 0
    }

    max_items = min(len(missing_plan), SECOND_ROUND_MAX_ITEMS)

    for item in missing_plan[:max_items]:
        product_id = item['product_id']
        product = enriched_products[product_id]
        missing_fields = item['missing_fields'][:SECOND_ROUND_MAX_FIELDS_PER_ITEM]

        # 获取文章内容
        content_text = product.get('combined_content', '') or product.get('content_text', '')

        if not content_text:
            continue

        enriched_count = 0
        product_enrichment = product.get('enrichment', {})

        # 初始化 enrichment 结构
        if 'evidence' not in product_enrichment:
            product_enrichment['evidence'] = {}
        if 'field_status' not in product_enrichment:
            product_enrichment['field_status'] = {}

        for field in missing_fields:
            # [FIX C.2] 规则/正则优先
            result = _extract_from_html_or_text(content_text, field, item['category'])

            if result['value']:
                # 回填字段值
                if 'specs' not in product:
                    product['specs'] = {}
                product['specs'][field] = result['value']

                # 记录证据
                product_enrichment['evidence'][field] = {
                    'source': 'local',
                    'snippet': result['evidence_snippet'],
                    'confidence': result['confidence'],
                    'method': result.get('method', 'unknown')
                }
                product_enrichment['field_status'][field] = 'enriched'

                stats['fields_by_method'][result.get('method', 'regex')] = \
                    stats['fields_by_method'].get(result.get('method', 'regex'), 0) + 1

                enriched_count += 1
                print(f"  ✓ [{product.get('product_name', 'Unknown')[:25]}] {field}: {result['value']}")
            else:
                # [FIX C.2] 规则未命中，尝试 LLM 提取
                llm_result = _extract_with_llm(content_text, field, item['category'])

                if llm_result['value']:
                    product['specs'][field] = llm_result['value']
                    product_enrichment['evidence'][field] = {
                        'source': 'local',
                        'snippet': llm_result['evidence_snippet'],
                        'confidence': llm_result['confidence'],
                        'method': 'llm'
                    }
                    product_enrichment['field_status'][field] = 'inferred'

                    stats['fields_by_method']['llm'] = stats['fields_by_method'].get('llm', 0) + 1

                    enriched_count += 1
                    print(f"  ~ [{product.get('product_name', 'Unknown')[:25]}] {field}: {llm_result['value']} (LLM推断)")

        if enriched_count > 0:
            product['enrichment'] = product_enrichment
            stats['products_enriched'] += 1
            stats['total_enriched'] += enriched_count

    print(f"[二次补全-同源] 完成: {stats['products_enriched']} 个产品补全了 {stats['total_enriched']} 个字段")
    print(f"  - 正则提取: {stats['fields_by_method'].get('regex', 0)} 个")
    print(f"  - LLM推断: {stats['fields_by_method'].get('llm', 0)} 个")

    return enriched_products, stats


def enrich_missing_fields(products: List[Dict]) -> List[Dict]:
    """
    [FIX E] 二次补全主入口 - 必经流程（不再支持开关关闭）

    二次补全始终执行，local 模式为默认必跑模式。
    search/both 作为增强模式叠加。

    Args:
        products: 产品列表

    Returns:
        List[Dict]: 补全后的产品列表
    """
    # [FIX E] 兼容性检查：检测用户是否设置了已废弃的关闭开关
    if _HAS_LEGACY_DISABLE_FLAG:
        print(f"\n[WARNING] 检测到已废弃的配置项：SECOND_ROUND_ENABLED=false")
        print(f"[WARNING] 二次补全现为必经流程，该配置不再生效")
        print(f"[WARNING] 建议从 .env 中删除 SECOND_ROUND_ENABLED 配置项")
        print(f"{'-'*60}")

    print(f"\n{'='*60}")
    print(f"二次补全（必经流程）- 模式: {SECOND_ROUND_MODE}")
    print(f"{'='*60}")

    # [FIX B] 检测缺失字段
    missing_plan = detect_missing_fields(products)

    if not missing_plan:
        print("[二次补全] 未发现需要补全的缺失字段（0 items enriched）")
        print("[二次补全] 所有关键字段已完整")
        return products

    print(f"[二次补全] 发现 {len(missing_plan)} 个产品存在关键字段缺失")

    # [FIX C] P0 同源补全（必跑模式）
    if SECOND_ROUND_MODE in ['local', 'both']:
        products, local_stats = enrich_missing_fields_local(products, missing_plan)

    # [FIX D] P1 跨源补全（预留接口，需要 MCP/搜索服务）
    if SECOND_ROUND_MODE in ['search', 'both']:
        print(f"\n[二次补全-跨源] 功能预留（需要 MCP/搜索服务支持）")
        # TODO: 实现 enrich_missing_fields_search()
        pass

    return products


def print_enrichment_summary(products: List[Dict], products_before: List[Dict] = None) -> Dict:
    """
    [FIX E] 打印二次补全统计摘要

    Args:
        products: 补全后的产品列表
        products_before: 补全前的产品列表（用于计算覆盖率变化）

    Returns:
        Dict: 统计信息字典
    """
    total_products = len(products)

    # 统计补全字段状态
    stats = {
        'explicit': 0,      # 原始明确值
        'enriched': 0,      # 规则补全
        'inferred': 0,      # LLM 推断
        'still_missing': 0, # 仍然缺失
        'total_fields': 0,
    }

    # 触发补全的产品数
    triggered_products = 0

    # 关键字段列表（用于覆盖率计算）
    key_fields = {
        'mouse': MOUSE_KEY_FIELDS_PRIORITY + MOUSE_CRITICAL_FIELDS,
        'keyboard': KEYBOARD_KEY_FIELDS_PRIORITY + KEYBOARD_CRITICAL_FIELDS,
    }
    # 去重
    for cat in key_fields:
        key_fields[cat] = list(set(key_fields[cat]))

    # 按品类统计
    category_stats = {
        '鼠标': {'explicit': 0, 'enriched': 0, 'inferred': 0, 'still_missing': 0, 'total_fields': 0},
        '键盘': {'explicit': 0, 'enriched': 0, 'inferred': 0, 'still_missing': 0, 'total_fields': 0},
    }

    for product in products:
        category = product.get('category', '')
        if category not in ['鼠标', '键盘']:
            continue

        specs = product.get('specs', {})
        enrichment = product.get('enrichment', {})
        field_status = enrichment.get('field_status', {})

        has_enrichment = bool(field_status)
        if has_enrichment:
            triggered_products += 1

        # 统计关键字段状态
        cat_key_fields = key_fields.get('mouse' if category == '鼠标' else 'keyboard', [])

        for field in cat_key_fields:
            value = specs.get(field, '')
            value_str = str(value).lower().strip() if value else ''

            # 判定字段状态
            status = field_status.get(field, '')

            if status == 'enriched':
                stats['enriched'] += 1
                if category in category_stats:
                    category_stats[category]['enriched'] += 1
            elif status == 'inferred':
                stats['inferred'] += 1
                if category in category_stats:
                    category_stats[category]['inferred'] += 1
            elif value_str and not any(marker in value_str for marker in [
                '未提及', '原文未提及', '未提供', '未公开', 'tbd', '待实测', '预估', '推断',
                '提取失败', '无法判断', 'unknown', 'none', 'null'
            ]):
                stats['explicit'] += 1
                if category in category_stats:
                    category_stats[category]['explicit'] += 1
            else:
                stats['still_missing'] += 1
                if category in category_stats:
                    category_stats[category]['still_missing'] += 1

            stats['total_fields'] += 1
            if category in category_stats:
                category_stats[category]['total_fields'] += 1

    # 计算覆盖率（补全前后）
    coverage_stats = {}

    def calc_coverage(products_list):
        """计算关键字段覆盖率"""
        if not products_list:
            return {}

        coverage = {}
        for category, fields_key in [('鼠标', 'mouse'), ('键盘', 'keyboard')]:
            cat_products = [p for p in products_list if p.get('category') == category]
            if not cat_products:
                coverage[category] = {'coverage': 0, 'total': 0, 'known': 0}
                continue

            # 使用该品类的关键字段
            critical_fields = MOUSE_CRITICAL_FIELDS if category == '鼠标' else KEYBOARD_CRITICAL_FIELDS
            total = len(cat_products) * len(critical_fields)
            known = 0

            for product in cat_products:
                specs = product.get('specs', {})
                enrichment = product.get('enrichment', {})
                field_status = enrichment.get('field_status', {})

                for field in critical_fields:
                    value = specs.get(field, '')
                    value_str = str(value).lower().strip() if value else ''

                    # 统计有效：明确值 + 补全值（可选 inferred）
                    is_valid = False

                    if value_str and not any(marker in value_str for marker in [
                        '未提及', '原文未提及', '未提供', '未公开', 'tbd', '待实测', '预估', '推断',
                        '提取失败', '无法判断'
                    ]):
                        is_valid = True

                    # 补全的值
                    if field in field_status:
                        if field_status[field] == 'enriched':
                            is_valid = True
                        elif field_status[field] == 'inferred' and COUNT_INFERRED_IN_COVERAGE:
                            is_valid = True

                    if is_valid:
                        known += 1

            coverage[category] = {
                'coverage': round(known / total * 100, 1) if total > 0 else 0,
                'total': total,
                'known': known
            }

        return coverage

    # 补全后覆盖率
    coverage_after = calc_coverage(products)

    # 补全前覆盖率（如果提供了原始数据）
    coverage_before = {}
    if products_before:
        coverage_before = calc_coverage(products_before)

    # 打印统计摘要
    print(f"\n{'='*60}")
    print("二次补全统计摘要")
    print(f"{'='*60}")

    print(f"\n[产品统计]")
    print(f"  总产品数: {total_products}")
    print(f"  触发补全的产品数: {triggered_products}")
    print(f"  补全率: {triggered_products / total_products * 100:.1f}%")

    print(f"\n[字段状态统计]")
    print(f"  explicit (原始明确值):  {stats['explicit']}")
    print(f"  enriched (规则补全):     {stats['enriched']}")
    print(f"  inferred (LLM推断):     {stats['inferred']}")
    print(f"  still_missing (仍缺失):  {stats['still_missing']}")
    print(f"  总字段数: {stats['total_fields']}")

    # 按品类统计
    for category, cat_stat in category_stats.items():
        if cat_stat['total_fields'] > 0:
            print(f"\n[{category}]")
            print(f"  explicit:  {cat_stat['explicit']}")
            print(f"  enriched:  {cat_stat['enriched']}")
            print(f"  inferred:  {cat_stat['inferred']}")
            print(f"  missing:   {cat_stat['still_missing']}")
            print(f"  总字段:    {cat_stat['total_fields']}")

    # 覆盖率对比
    print(f"\n[关键字段覆盖率]")
    print(f"  (inferred {'计入' if COUNT_INFERRED_IN_COVERAGE else '不计入'} coverage)")

    for category in ['鼠标', '键盘']:
        if category in coverage_after:
            after = coverage_after[category]
            if category in coverage_before:
                before = coverage_before[category]
                delta = after['coverage'] - before['coverage']
                delta_str = f"+{delta:.1f}%" if delta >= 0 else f"{delta:.1f}%"
                print(f"  {category}: {before['coverage']:.1f}% → {after['coverage']:.1f}% ({delta_str})")
                print(f"    (known: {before['known']}/{before['total']} → {after['known']}/{after['total']})")
            else:
                print(f"  {category}: {after['coverage']:.1f}% ({after['known']}/{after['total']})")

    print(f"{'='*60}\n")

    return {
        'products': {
            'total': total_products,
            'triggered': triggered_products,
        },
        'fields': stats,
        'category_fields': category_stats,
        'coverage': {
            'before': coverage_before,
            'after': coverage_after,
        },
        'config': {
            'count_inferred': COUNT_INFERRED_IN_COVERAGE,
        }
    }


def validate_enrichment_summary(json_path: str = None) -> Dict:
    """
    [FIX E] 从 processed_products.json 读取并打印 enrichment summary

    用于 validate-only 模式下验收二次补全结果

    Args:
        json_path: processed_products.json 路径（默认使用 PROCESSED_JSON）

    Returns:
        Dict: 统计信息字典
    """
    import json

    if json_path is None:
        json_path = PROCESSED_JSON

    json_path = Path(json_path)

    if not json_path.exists():
        print(f"\n[ERROR] 文件不存在: {json_path}")
        print("请先生成报告，或指定正确的 JSON 路径")
        return {}

    print(f"\n[校验] 读取 enrichment 数据: {json_path}")

    with open(json_path, 'r', encoding='utf-8') as f:
        products = json.load(f)

    return print_enrichment_summary(products)


# 默认科技感占位图（在线 URL）
DEFAULT_IMAGE_URL = "https://images.unsplash.com/photo-1550009158-9ebf69173e03?w=800&h=600&fit=crop"

# 输出文件配置
OUTPUT_DIR = Path("output")
PROCESSED_JSON = OUTPUT_DIR / "processed_products.json"
HTML_REPORT = OUTPUT_DIR / "monthly_report_2026_01.html"

# ==================== 模板配置 ====================
TEMPLATE_MODE = "pm_deep"  # 默认模板: pm_deep (PM深度分析版)
AVAILABLE_TEMPLATES = {
    "pm_deep": "PM深度分析版（完整三栏布局 + nav-bar + 搜索）",
    "simple": "简化版（仅基本信息）"
}

# ==================== 爬虫数据获取函数 ====================

def fetch_data(year: int, month: int, output_dir: Path = OUTPUT_DIR) -> str:
    """
    运行爬虫采集数据

    Args:
        year: 目标年份
        month: 目标月份
        output_dir: 输出目录

    Returns:
        str: 输出的 JSON 文件路径

    Raises:
        SystemExit: 如果爬取失败或没有数据
    """
    import json

    target_json = output_dir / f'report_data_{year}_{month:02d}.json'

    # 备份旧文件（如果存在）
    if target_json.exists():
        backup_path = output_dir / f'report_data_{year}_{month:02d}.json.bak'
        shutil.copy2(target_json, backup_path)
        print(f"[BACKUP] 已备份旧文件: {backup_path}")

    print(f"\n{'='*60}")
    print(f"开始爬取数据: {year}-{month:02d}")
    print(f"{'='*60}\n")

    # 方式1：尝试作为模块导入 spider（更优雅）
    try:
        import spider

        # 临时修改 config 的年月
        import config
        original_year = config.TARGET_YEAR
        original_month = config.TARGET_MONTH

        # 运行爬虫
        all_articles = spider.run_spider_all(target_year=year, target_month=month, max_pages=20)

        # 恢复原始配置
        config.TARGET_YEAR = original_year
        config.TARGET_MONTH = original_month

        # 验证数据
        if not all_articles:
            print(f"\n{'='*60}")
            print(f"[ERROR] 爬虫未采集到任何数据！")
            print(f"[ERROR] 请检查：")
            print(f"  1. 目标月份 {year}-{month:02d} 是否有新品发布")
            print(f"  2. 网络连接是否正常")
            print(f"  3. 目标网站是否可访问")
            print(f"{'='*60}\n")
            raise SystemExit(1)

        # 导出数据
        exporter = spider.DataExporter()
        exporter.export_to_json(all_articles, filename=f'report_data_{year}_{month:02d}.json')
        exporter.export_to_excel(all_articles, filename=f'report_data_{year}_{month:02d}.xlsx')

        print(f"\n{'='*60}")
        print(f"✓ 爬取完成！共采集 {len(all_articles)} 条数据")
        print(f"✓ 数据已保存: {target_json}")
        print(f"{'='*60}\n")

        return str(target_json)

    except ImportError as e:
        # 方式2：作为子进程调用（备用方案）
        print(f"[WARN] 无法导入 spider 模块，使用子进程调用: {e}")

        # 设置环境变量传递年月
        env = os.environ.copy()
        env['TARGET_YEAR'] = str(year)
        env['TARGET_MONTH'] = str(month)

        # 运行 spider.py
        result = subprocess.run(
            [sys.executable, 'spider.py'],
            env=env,
            capture_output=True,
            text=True
        )

        # 输出爬虫日志
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)

        # 检查是否生成文件
        if not target_json.exists():
            print(f"\n{'='*60}")
            print(f"[ERROR] 爬虫执行失败，未生成数据文件！")
            print(f"{'='*60}\n")
            raise SystemExit(1)

        # 验证数据
        with open(target_json, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if not data or len(data) == 0:
            print(f"\n{'='*60}")
            print(f"[ERROR] 爬虫采集到 0 条数据！")
            print(f"[ERROR] 请检查目标月份 {year}-{month:02d} 是否有新品发布")
            print(f"{'='*60}\n")
            raise SystemExit(1)

        print(f"\n{'='*60}")
        print(f"✓ 爬取完成！共采集 {len(data)} 条数据")
        print(f"{'='*60}\n")

        return str(target_json)


# ==================== 任务一：数据预处理与清洗 ====================

class DataCleaner:
    """数据清洗器 - Phase 4 增强版"""

    def __init__(self, file_path: str):
        # 自动检测文件格式并读取
        if file_path.endswith('.json'):
            self.df = pd.read_json(file_path)
        elif file_path.endswith(('.xlsx', '.xls')):
            self.df = pd.read_excel(file_path, engine='openpyxl' if file_path.endswith('.xlsx') else 'xlrd')
        else:
            # 默认尝试 Excel
            self.df = pd.read_excel(file_path, engine='openpyxl')
        print(f"[OK] 加载原始数据: {len(self.df)} 条记录")

    def filter_by_keywords(self) -> pd.DataFrame:
        """关键词筛选（白名单）"""
        def contains_keyword(text: str) -> bool:
            if pd.isna(text):
                return False
            text = str(text).lower()
            return any(kw in text for kw in KEYWORDS)

        # 筛选标题或正文包含关键词的记录
        mask = self.df['title'].apply(contains_keyword) | \
               self.df['content_text'].apply(contains_keyword)

        filtered_df = self.df[mask].copy()
        print(f"[OK] 关键词筛选后: {len(filtered_df)} 条记录")

        return filtered_df

    def filter_by_blacklist(self, df: pd.DataFrame) -> pd.DataFrame:
        """黑名单过滤 - 过滤掉鼠标垫、线材等配件"""
        def contains_blacklist(text: str) -> bool:
            if pd.isna(text):
                return False
            text = str(text).lower()
            return any(kw in text for kw in BLACKLIST)

        # 过滤标题包含黑名单关键词的记录
        mask = ~df['title'].apply(contains_blacklist)

        filtered_df = df[mask].copy()
        dropped_count = len(df) - len(filtered_df)

        if dropped_count > 0:
            print(f"[OK] 黑名单过滤: 剔除 {dropped_count} 条配件记录")

        return filtered_df

    def smart_deduplicate(self, df: pd.DataFrame) -> List[Dict]:
        """智能去重并合并"""
        products = []

        # 按发布时间排序（最新的在前）
        df = df.sort_values('publish_date', ascending=False)

        used_indices = set()

        for i, row in df.iterrows():
            if i in used_indices:
                continue

            # 当前产品
            current_title = row['title']
            sources = [row['source']]
            records = [row.to_dict()]

            current_product = {
                'product_name': current_title,
                'records': records,
                'images': self._parse_images(row['images']),
                'sources': sources
            }

            # 查找相似产品
            for j, compare_row in df.iterrows():
                if j <= i or j in used_indices:
                    continue

                similarity = SequenceMatcher(
                    None,
                    current_title,
                    compare_row['title']
                ).ratio()

                # 相似度阈值 0.6
                if similarity > 0.6:
                    # 合并记录
                    current_product['records'].append(compare_row.to_dict())
                    current_product['images'].extend(
                        self._parse_images(compare_row['images'])
                    )
                    if compare_row['source'] not in current_product['sources']:
                        current_product['sources'].append(compare_row['source'])

                    used_indices.add(j)

            # 提取第一张图片（智能选择最佳图片）
            first_image = self._select_best_image(current_product, row)

            # 只保存第一张图片
            current_product['images'] = [first_image] if first_image else []

            # 合并所有正文内容
            combined_content = '\n\n---\n\n'.join([
                f"来源: {r['source']}\n标题: {r['title']}\n{r['content_text']}"
                for r in current_product['records']
            ])
            current_product['combined_content'] = combined_content

            products.append(current_product)
            used_indices.add(i)

        print(f"[OK] 智能去重后: {len(products)} 款产品")

        return products

    @staticmethod
    def _parse_images(images_str: str) -> List[str]:
        """解析图片字符串"""
        if pd.isna(images_str):
            return []

        # 处理列表格式的字符串
        images_str = str(images_str).strip()
        if not images_str or images_str == '[]':
            return []

        try:
            # 尝试解析为 Python 列表
            images = eval(images_str)
            if isinstance(images, list):
                return images
        except:
            pass

        return []

    @staticmethod
    def _clean_image_paths(images: List[str], sources: List[str]) -> List[str]:
        """清洗图片路径，根据来源补全域名"""
        cleaned = []

        # 判断来源
        has_inwaishe = 'in外设' in sources
        has_wstx = '外设天下' in sources

        for img in images:
            if not img or not isinstance(img, str):
                continue

            img = img.strip()

            # 跳过 data URL
            if img.startswith('data:'):
                continue

            # 已经是完整 URL
            if img.startswith('http://') or img.startswith('https://'):
                cleaned.append(img)
                continue

            # in外设：data/attachment 开头
            if img.startswith('data/attachment'):
                img = f'http://www.inwaishe.com/{img}'
                cleaned.append(img)
                continue

            # 外设天下：相对路径
            if img.startswith('/'):
                # 如果有外设天下的来源，优先使用 wstx.com
                if has_wstx:
                    img = f'https://www.wstx.com{img}'
                else:
                    img = f'http://www.inwaishe.com{img}'
                cleaned.append(img)
                continue

            # 其他情况尝试作为相对路径处理
            if has_wstx:
                cleaned.append(f'https://www.wstx.com/{img}')
            elif has_inwaishe:
                cleaned.append(f'http://www.inwaishe.com/{img}')

        return cleaned

    @staticmethod
    def _select_best_image(product: Dict, current_row: pd.Series) -> Optional[str]:
        """
        智能选择最佳产品图片

        优先级：
        1. 优先选择包含"产品实拍"、"渲染图"等关键词的图片（从content_text判断）
        2. 避免选择logo、banner等非产品图
        3. 优先选择当前记录的图片，其次是相似记录的图片
        """
        all_images = []

        # 收集当前记录的图片
        current_imgs = DataCleaner._parse_images(current_row['images'])
        for idx, img in enumerate(current_imgs):
            all_images.append({
                'url': img,
                'is_current': True,
                'index': idx
            })

        # 收集其他相似记录的图片
        for record in product.get('records', []):
            if isinstance(record, dict):
                record_imgs = DataCleaner._parse_images(record.get('images', []))
                for idx, img in enumerate(record_imgs):
                    all_images.append({
                        'url': img,
                        'is_current': False,
                        'index': idx
                    })

        # 清洗图片路径
        sources = product.get('sources', [])
        for img_dict in all_images:
            cleaned = DataCleaner._clean_image_paths([img_dict['url']], sources)
            if cleaned:
                img_dict['cleaned_url'] = cleaned[0]
            else:
                img_dict['cleaned_url'] = None

        # 过滤掉无效图片
        valid_images = [img for img in all_images if img.get('cleaned_url')]

        if not valid_images:
            return None

        # 优先级1: 优先选择当前记录的图片
        current_images = [img for img in valid_images if img['is_current']]
        if current_images:
            return current_images[0]['cleaned_url']

        # 优先级2: 返回第一个有效图片
        return valid_images[0]['cleaned_url']


# ==================== 任务二：LLM PM视角深度分析 ====================

# 内网搜索API配置
SEARCH_API_CONFIG = {
    "base_url": "http://192.168.0.250:7891",
    "api_key": "cr_efee6bd8725c8ab63fe98cb355d0c8569ef10fb89f7a386a84954a2feeeeee42",  # 内网API认证token
    "timeout": 10
}


class ParameterCompleter:
    """参数自动补全器 - 通过搜索补全缺失的产品参数"""

    def __init__(self, search_config: Dict = None, search_func=None, llm_config: Dict = None):
        """
        初始化参数补全器

        Args:
            search_config: 搜索API配置（兼容旧版本）
            search_func: 自定义搜索函数，签名为 (query: str) -> Optional[str]
                        如果为 None，则使用内部的 MCP 搜索方式
            llm_config: LLM配置，用于从搜索结果中提取参数
        """
        self.search_config = search_config or SEARCH_API_CONFIG
        self.search_enabled = True  # 可以通过配置开关搜索功能
        self.custom_search_func = search_func  # 外部传入的搜索函数
        self.llm_config = llm_config or LLM_CONFIG  # 使用全局 LLM 配置

        # 定义需要检查的关键字段
        self.mice_critical_fields = ['weight', 'sensor', 'polling_rate']
        self.keyboard_critical_fields = ['structure', 'connection', 'switch']

        # 字段中文名映射（用于 LLM 提示）
        self.field_names_cn = {
            # 鼠标字段
            'weight': '重量',
            'sensor': '传感器型号',
            'polling_rate': '回报率',
            'dimensions': '尺寸',
            'dpi': '最高DPI',
            'connection': '连接方式',
            'buttons': '按键数量',
            'switch': '微动开关',
            'battery': '电池续航',
            # 键盘字段
            'layout': '配列',
            'structure': '结构',
            'keycap': '键帽材质',
            'hot_swappable': '热插拔',
            'switch': '轴体类型',
        }

    def check_completeness(self, product: Dict) -> Dict[str, list]:
        """
        检查产品参数完整性

        Returns:
            Dict with 'missing' (缺失字段列表) and 'search_queries' (需要执行的搜索查询)
        """
        category = product.get('category', '')
        specs = product.get('specs', {})

        missing_fields = []
        search_queries = []

        if category == '鼠标':
            critical_fields = self.mice_critical_fields
            field_names = {
                'weight': '重量',
                'sensor': '传感器型号',
                'polling_rate': '回报率'
            }
        elif category == '键盘':
            critical_fields = self.keyboard_critical_fields
            field_names = {
                'structure': '结构',
                'connection': '连接方式',
                'switch': '轴体'
            }
        else:
            return {'missing': [], 'search_queries': []}

        # 检查每个关键字段
        for field in critical_fields:
            value = specs.get(field, '')
            if not value or str(value).lower() in ['unknown', 'null', '', '未提及', '未知']:
                missing_fields.append(field)
                # 构造搜索查询
                query = f"{product.get('product_name', '')} {field_names[field]} 参数"
                search_queries.append({
                    'field': field,
                    'field_name': field_names[field],
                    'query': query
                })

        return {
            'missing': missing_fields,
            'search_queries': search_queries
        }

    def search_and_complete(self, product: Dict) -> Dict:
        """
        搜索并补全缺失的参数

        Args:
            product: 产品数据字典

        Returns:
            更新后的产品字典（补全了参数）
        """
        if not self.search_enabled:
            return product

        completeness = self.check_completeness(product)

        if not completeness['missing']:
            return product  # 无需补全

        print(f"      [参数补全] 检测到 {len(completeness['missing'])} 个缺失字段，开始搜索...")

        # 补全每个缺失的字段
        specs = product.get('specs', {}).copy()

        for search_item in completeness['search_queries']:
            field = search_item['field']
            query = search_item['query']

            try:
                # 优先使用自定义搜索函数（如 MCP 工具）
                if self.custom_search_func:
                    search_result = self.custom_search_func(query)
                else:
                    # 回退到原有的 API 调用方式
                    search_result = self._call_search_api_fallback(query)

                if search_result:
                    # 从搜索结果中提取参数值
                    extracted_value = self._extract_param_from_search(
                        search_result,
                        field,
                        product.get('category', '')
                    )

                    if extracted_value:
                        old_value = specs.get(field, '')
                        specs[field] = extracted_value
                        print(f"      [参数补全] [OK] {search_item['field_name']}: {old_value} -> {extracted_value} (搜)")
                    else:
                        print(f"      [参数补全] [X] {search_item['field_name']}: 未找到相关信息")

            except Exception as e:
                print(f"      [参数补全] [X] 搜索失败 ({search_item['field_name']}): {str(e)[:50]}")

        # 更新产品数据
        product['specs'] = specs
        return product

    def _call_search_api(self, query: str) -> Optional[str]:
        """
        使用 MCP web-search-prime 工具进行搜索

        Args:
            query: 搜索查询

        Returns:
            搜索结果摘要文本（合并前3个结果的content字段）
        """
        try:
            # 直接使用 MCP 工具（通过环境变量或全局访问）
            # 注意：这个方法会在实际运行时被调用，MCP工具已预配置
            import subprocess
            import json

            # 构造 claude 命令行调用
            # 由于我们在 claude code 环境中，直接通过调用函数的方式
            # 这里使用一个简化的方法：通过 subprocess 调用 claude mcp 命令
            # 但更直接的方式是：让调用者直接使用 MCP 工具

            # 实际上，最好的方式是直接返回查询字符串，
            # 让调用者在外部使用 MCP 工具
            print(f"        [搜索API] 准备搜索: {query}")

            # 由于无法直接在 Python 代码中调用 MCP 工具，
            # 我们返回一个特殊标记，让上层函数处理
            return f"MCP_SEARCH_REQUIRED:{query}"

        except Exception as e:
            print(f"        [搜索API] 初始化失败: {str(e)[:100]}")
            return None

    def _extract_param_from_search(self, search_text: str, field: str, category: str) -> Optional[str]:
        """
        从搜索结果中提取参数值（使用 LLM）

        Args:
            search_text: 搜索结果文本（JSON字符串或纯文本）
            field: 字段名（如 'weight', 'sensor'）
            category: 产品类别（如 '鼠标', '键盘'）

        Returns:
            提取的参数值
        """
        if not search_text:
            return None

        # 解析搜索结果（如果是JSON格式）
        extracted_content = self._parse_search_result(search_text)

        if not extracted_content:
            return None

        # 使用 LLM 提取参数
        field_name_cn = self.field_names_cn.get(field, field)
        extracted_value = self._extract_with_llm(extracted_content, field_name_cn, category)

        return extracted_value

    def _parse_search_result(self, search_text: str) -> str:
        """
        解析搜索结果，提取纯文本内容

        Args:
            search_text: MCP返回的JSON字符串

        Returns:
            合并后的纯文本内容
        """
        import json

        # 尝试解析为JSON
        try:
            results = json.loads(search_text)
            if isinstance(results, list) and len(results) > 0:
                # 提取所有结果的 content 字段
                content_texts = []
                for result in results[:3]:  # 只取前3个结果
                    content = result.get('content', '')
                    if content:
                        content_texts.append(content)

                if content_texts:
                    return '\n\n'.join(content_texts)
        except json.JSONDecodeError:
            # 不是JSON格式，直接使用原文本
            pass

        return search_text

    def _extract_with_llm(self, content: str, field_name_cn: str, category: str) -> Optional[str]:
        """
        使用 LLM 从文本中提取参数值

        Args:
            content: 搜索结果的纯文本内容
            field_name_cn: 字段中文名（如 '重量', '传感器型号'）
            category: 产品类别

        Returns:
            提取的参数值
        """
        import requests

        # 构造 LLM 提示
        prompt = f"""你是一个专业的外设参数提取助手。

请从以下产品搜索结果中提取【{field_name_cn}】的值。

产品类别：{category}

搜索结果：
{content}

要求：
1. 只输出参数值，不要任何其他文字
2. 如果搜索结果中没有提到{field_name_cn}，输出 "NOT_FOUND"
3. 提取示例：
   - 重量：50g、约50克、50克左右 → 提取 "50g"
   - 传感器：PAW3395传感器、搭载PAW3395 → 提取 "PAW3395"
   - 回报率：8K回报率、支持8000Hz → 提取 "8000Hz"
   - 结构：Gasket结构、采用Gasket设计 → 提取 "Gasket"
   - 轴体：TTC金茶轴、搭载佳达隆 → 提取 "TTC金茶轴"

请提取{field_name_cn}的值："""

        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.llm_config.get('api_key', '')}"
            }

            data = {
                "model": self.llm_config.get("model", ""),
                "messages": [
                    {
                        "role": "system",
                        "content": "你是一个专业的外设参数提取助手，擅长从产品描述中提取准确的参数值。只输出参数值，不要其他内容。"
                    },
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.1,  # 降低温度，提高准确性
                "max_tokens": 100,
                "stream": False
            }

            base_url = self.llm_config.get("base_url", "").rstrip('/')
            url = f"{base_url}/v1/chat/completions"

            response = requests.post(url, headers=headers, json=data, timeout=30)
            response.raise_for_status()

            result = response.json()
            extracted_text = result["choices"][0]["message"]["content"].strip()

            # 检查是否未找到
            if 'NOT_FOUND' in extracted_text or '未提及' in extracted_text or '未找到' in extracted_text:
                return None

            # 清理提取的值（移除多余的引号、空格等）
            extracted_text = extracted_text.strip('"\'').strip()

            # 限制长度
            if len(extracted_text) > 100:
                extracted_text = extracted_text[:100]

            return extracted_text

        except Exception as e:
            print(f"        [LLM提取] 失败: {str(e)[:50]}")
            # LLM 失败时，回退到正则表达式
            return self._extract_with_regex(content, field_name_cn)

    def _extract_with_regex(self, content: str, field_name_cn: str) -> Optional[str]:
        """
        正则表达式提取（备用方案）

        Args:
            content: 文本内容
            field_name_cn: 字段中文名

        Returns:
            提取的参数值
        """
        # 简化的正则模式作为备用
        if '重量' in field_name_cn or 'weight' in field_name_cn.lower():
            match = re.search(r'(\d+(?:\.\d+)?)\s*[g克]', content, re.IGNORECASE)
            if match:
                return f"{match.group(1)}g"

        elif '传感器' in field_name_cn or 'sensor' in field_name_cn.lower():
            match = re.search(r'(PAW\d+[A-Z]*|Hero\s*\d*[A-Z]*|AIM\d+)', content, re.IGNORECASE)
            if match:
                return match.group(1)

        elif '回报率' in field_name_cn or 'polling' in field_name_cn.lower():
            match = re.search(r'(\d+)\s*[kK]?[hH][zZ]', content, re.IGNORECASE)
            if match:
                return f"{match.group(1)}Hz"

        return None

    def extract_from_article(self, product: Dict) -> Dict:
        """
        从原文章内容中提取参数（第一步）

        Args:
            product: 产品数据字典，必须包含 'content_text' 字段

        Returns:
            更新后的产品字典（包含从文章提取的参数）
        """
        article_content = product.get('content_text', '')

        if not article_content:
            return product

        print(f"      [文章提取] 从原文章中提取参数...")

        # 初始化 specs（如果不存在）
        if 'specs' not in product:
            product['specs'] = {}

        # 使用 LLM 从文章中提取所有相关参数
        extracted_params = self._extract_all_params_with_llm(article_content, product.get('category', ''))

        # 回填参数
        filled_count = 0
        for field, value in extracted_params.items():
            if value and value != '未知':
                old_value = product['specs'].get(field, '')
                if not old_value or old_value == '未知':
                    product['specs'][field] = value
                    filled_count += 1
                    field_name_cn = self.field_names_cn.get(field, field)
                    print(f"      [文章提取] [OK] {field_name_cn}: {value}")

        if filled_count > 0:
            print(f"      [文章提取] 成功提取 {filled_count} 个参数")
        else:
            print(f"      [文章提取] 未找到参数信息")

        return product

    def _extract_all_params_with_llm(self, content: str, category: str) -> Dict[str, str]:
        """
        使用 LLM 从文本中提取所有相关参数

        Args:
            content: 文本内容
            category: 产品类别

        Returns:
            参数字典 {field: value}
        """
        import requests

        # 根据类别定义要提取的字段
        if category == '鼠标':
            fields_definition = """
            - weight (重量): 单位用g，如"50g"
            - sensor (传感器型号): 如"PAW3395"、"Hero 25K"
            - polling_rate (回报率): 单位用Hz，如"1000Hz"、"8000Hz"
            - dpi (最高DPI): 如"26000"
            - connection (连接方式): 如"三模"、"2.4G+蓝牙+有线"
            - buttons (按键数量): 如"5键"、"6键"
            - battery (电池续航): 如"100小时"
            """
        elif category == '键盘':
            fields_definition = """
            - layout (配列): 如"75配列"、"98配列"、"全尺寸"
            - structure (结构): 如"Gasket"、"PC定位板"
            - connection (连接方式): 如"三模"、"2.4G+蓝牙+有线"
            - switch (轴体类型): 如"TTC金茶轴"、"佳达隆G黄Pro"
            - keycap (键帽材质): 如"PBT"、"ABS"
            - hot_swappable (热插拔): 如"支持"、"不支持"
            - polling_rate (回报率): 如"1000Hz"
            """
        else:
            return {}

        prompt = f"""你是一个专业的外设参数提取助手。

请从以下产品文章中提取所有可用的参数信息。

产品类别：{category}

需要提取的字段：
{fields_definition}

文章内容：
{content[:2000]}

要求：
1. 仔细阅读文章，提取所有提到的参数
2. 只输出JSON格式，不要其他文字
3. 如果某个参数在文章中没有提到，设为 null
4. 输出格式示例：
{{
  "weight": "50g",
  "sensor": "PAW3395",
  "polling_rate": "1000Hz",
  "connection": "三模"
}}

请输出JSON："""

        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.llm_config.get('api_key', '')}"
            }

            data = {
                "model": self.llm_config.get("model", ""),
                "messages": [
                    {
                        "role": "system",
                        "content": "你是一个专业的外设参数提取助手。只输出JSON格式的参数数据，不要其他内容。"
                    },
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.1,
                "max_tokens": 500,
                "stream": False
            }

            base_url = self.llm_config.get("base_url", "").rstrip('/')
            url = f"{base_url}/v1/chat/completions"

            response = requests.post(url, headers=headers, json=data, timeout=30)
            response.raise_for_status()

            result = response.json()
            extracted_text = result["choices"][0]["message"]["content"].strip()

            # 解析 JSON
            import json
            # 清理可能的 markdown 代码块标记
            if extracted_text.startswith('```'):
                extracted_text = extracted_text.split('```')[1]
                if extracted_text.startswith('json'):
                    extracted_text = extracted_text[4:]

            extracted_params = json.loads(extracted_text)

            # 过滤掉 null 值
            return {k: v for k, v in extracted_params.items() if v and v != '未知' and v != '未提及'}

        except Exception as e:
            print(f"        [LLM文章提取] 失败: {str(e)[:50]}")
            return {}

    def complete_parameters(self, product: Dict, search_func=None) -> Dict:
        """
        完整的参数补全流程

        流程：
        1. 从原文章内容中提取参数
        2. 检查缺失字段
        3. 对缺失字段进行 MCP 搜索
        4. 用 LLM 从搜索结果中提取参数
        5. 回填数据
        6. 补充额外发现的参数

        Args:
            product: 产品数据字典
            search_func: MCP 搜索函数 (query: str) -> str

        Returns:
            更新后的产品字典
        """
        # 步骤1: 从原文章中提取参数
        print(f"    [参数补全] 开始处理: {product.get('product_name', 'Unknown')[:40]}")

        product = self.extract_from_article(product)

        # 步骤2: 检查缺失字段
        completeness = self.check_completeness(product)

        if not completeness['missing']:
            print(f"    [参数补全] 所有参数完整，无需搜索")
            return product

        print(f"    [参数补全] 检测到 {len(completeness['missing'])} 个缺失字段")

        # 步骤3-5: 批量 MCP 搜索 + LLM 提取
        if search_func or self.custom_search_func:
            search_function = search_func or self.custom_search_func

            for search_item in completeness['search_queries']:
                field = search_item['field']
                query = search_item['query']

                try:
                    # MCP 搜索
                    print(f"      [搜索] {search_item['field_name']}: {query}")
                    search_result = search_function(query)

                    if search_result:
                        # LLM 提取（同时提取目标参数和额外参数）
                        extracted = self._extract_with_extra_params(
                            search_result,
                            field,
                            product.get('category', '')
                        )

                        if extracted.get('target_value'):
                            # 回填目标参数
                            old_value = product['specs'].get(field, '')
                            product['specs'][field] = extracted['target_value']
                            print(f"      [补全] [OK] {search_item['field_name']}: {extracted['target_value']} (MCP+LLM)")

                        # 补充额外发现的参数
                        if extracted.get('extra_params'):
                            for extra_field, extra_value in extracted['extra_params'].items():
                                if extra_field not in product['specs'] or not product['specs'][extra_field]:
                                    field_name_cn = self.field_names_cn.get(extra_field, extra_field)
                                    product['specs'][extra_field] = extra_value
                                    print(f"      [补充] [+] {field_name_cn}: {extra_value} (额外发现)")
                    else:
                        print(f"      [搜索] [X] {search_item['field_name']}: 搜索无结果")

                except Exception as e:
                    print(f"      [搜索] [X] 失败: {str(e)[:50]}")
        else:
            print(f"    [参数补全] 未提供搜索函数，跳过 MCP 搜索")

        # 步骤6: 标记未知参数
        for field in completeness['missing']:
            if not product['specs'].get(field):
                product['specs'][field] = '未知'

        return product

    def _extract_with_extra_params(self, search_result: str, target_field: str, category: str) -> Dict:
        """
        从搜索结果中提取目标参数，并同时提取其他发现的参数

        Args:
            search_result: MCP 搜索结果（JSON字符串）
            target_field: 目标字段名
            category: 产品类别

        Returns:
            {
                'target_value': '目标字段的值',
                'extra_params': {'其他字段': '值'}  # 额外发现的参数
            }
        """
        # 解析搜索结果
        content = self._parse_search_result(search_result)

        if not content:
            return {'target_value': None, 'extra_params': {}}

        # 定义要提取的所有字段
        if category == '鼠标':
            all_fields = {
                'weight': '重量',
                'sensor': '传感器型号',
                'polling_rate': '回报率',
                'dpi': '最高DPI',
                'connection': '连接方式',
                'buttons': '按键数量',
                'battery': '电池续航'
            }
        elif category == '键盘':
            all_fields = {
                'layout': '配列',
                'structure': '结构',
                'connection': '连接方式',
                'switch': '轴体类型',
                'keycap': '键帽材质',
                'hot_swappable': '热插拔',
                'polling_rate': '回报率'
            }
        else:
            return {'target_value': None, 'extra_params': {}}

        # 使用 LLM 提取所有参数
        target_field_cn = self.field_names_cn.get(target_field, target_field)
        all_extracted = self._extract_all_fields_from_search(content, all_fields, category)

        # 分离目标字段和额外字段
        target_value = all_extracted.get(target_field)
        extra_params = {k: v for k, v in all_extracted.items() if k != target_field and v and v != '未知'}

        return {
            'target_value': target_value,
            'extra_params': extra_params
        }

    def _extract_all_fields_from_search(self, content: str, fields: Dict[str, str], category: str) -> Dict[str, str]:
        """
        从搜索结果中提取所有指定字段

        Args:
            content: 搜索结果文本
            fields: 字段字典 {field: field_name_cn}
            category: 产品类别

        Returns:
            提取的参数字典
        """
        import requests

        # 构造字段说明
        fields_desc = "\n".join([f"  - {field} ({fields[field]}): 参数值" for field in fields])

        prompt = f"""你是一个专业的外设参数提取助手。

请从以下产品搜索结果中提取所有可用的参数。

产品类别：{category}

需要提取的字段：
{fields_desc}

搜索结果：
{content}

要求：
1. 只输出JSON格式
2. 如果某个参数在搜索结果中没有提到，设为 null
3. 提取示例：
   - 重量：50g、约50克 → {{"weight": "50g"}}
   - 传感器：PAW3395传感器 → {{"sensor": "PAW3395"}}
   - 回报率：8K回报率 → {{"polling_rate": "8000Hz"}}

请输出JSON："""

        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.llm_config.get('api_key', '')}"
            }

            data = {
                "model": self.llm_config.get("model", ""),
                "messages": [
                    {
                        "role": "system",
                        "content": "你是一个专业的外设参数提取助手。只输出JSON格式的参数数据。"
                    },
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.1,
                "max_tokens": 500,
                "stream": False
            }

            base_url = self.llm_config.get("base_url", "").rstrip('/')
            url = f"{base_url}/v1/chat/completions"

            response = requests.post(url, headers=headers, json=data, timeout=30)
            response.raise_for_status()

            result = response.json()
            extracted_text = result["choices"][0]["message"]["content"].strip()

            # 解析 JSON
            import json
            if extracted_text.startswith('```'):
                extracted_text = extracted_text.split('```')[1]
                if extracted_text.startswith('json'):
                    extracted_text = extracted_text[4:]

            extracted_params = json.loads(extracted_text)

            return {k: v for k, v in extracted_params.items() if v and v != '未知' and v != '未提及'}

        except Exception as e:
            print(f"        [LLM批量提取] 失败: {str(e)[:50]}")
            # 回退：只提取目标字段
            return {}

    def _call_search_api_fallback(self, query: str) -> Optional[str]:
        """
        回退方案：通过 requests 调用内网搜索 API

        Args:
            query: 搜索查询

        Returns:
            搜索结果摘要文本
        """
        import requests
        import json

        url = f"{self.search_config['base_url']}/mcp_web_search"

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream"
        }

        data = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "webSearchPrime",
                "arguments": {
                    "search_query": query,
                    "content_size": "medium"
                }
            }
        }

        if self.search_config.get('api_key'):
            data["params"]["arguments"]["api_key"] = self.search_config['api_key']
            data["params"]["arguments"]["authorization"] = self.search_config['api_key']

        try:
            response = requests.post(url, headers=headers, json=data, timeout=self.search_config.get('timeout', 10))
            response.raise_for_status()

            content_type = response.headers.get('content-type', '')

            if 'text/event-stream' in content_type:
                lines = response.text.split('\n')
                all_results = []
                for line in lines:
                    line = line.strip()
                    if line.startswith('data:'):
                        json_str = line[5:].strip()
                        if json_str and json_str != '[DONE]':
                            try:
                                data_obj = json.loads(json_str)
                                if 'result' in data_obj and 'content' in data_obj['result']:
                                    for item in data_obj['result']['content']:
                                        if isinstance(item, dict) and 'text' in item:
                                            all_results.append(item['text'])
                            except json.JSONDecodeError:
                                continue

                if all_results:
                    return '\n\n'.join(all_results[:3])
                return None

            return None

        except Exception as e:
            print(f"        [搜索API-Fallback] 调用失败: {str(e)[:100]}")
            return None


class ParameterCompleterV2:
    """
    参数补全器 V2 - 支持 Top 20 Schema 和聚合搜索

    核心改进：
    1. 使用 Top 20 标准化 Schema
    2. 聚合搜索（1次搜索获取所有缺失参数，而非N次）
    3. 数据源追踪
    """

    def __init__(self, llm_config: Dict = None, search_func=None):
        """
        初始化参数补全器

        Args:
            llm_config: LLM 配置
            search_func: MCP 搜索函数 (query: str) -> str
        """
        self.llm_config = llm_config or LLM_CONFIG
        self.search_func = search_func
        self.search_enabled = bool(search_func)  # 是否启用搜索功能

    def complete_parameters(self, product: Dict) -> Dict:
        """
        完整的参数补全流程

        流程：
        1. 从原文章提取 Top 20 参数
        2. 检查缺失字段
        3. 聚合搜索（1次搜索获取所有缺失参数）
        4. LLM 提取补全
        5. 记录数据来源

        Args:
            product: 产品数据，必须包含 category 和 content_text

        Returns:
            更新后的产品数据，包含 specs 和 data_sources
        """
        category = product.get('category', '')
        article_content = product.get('content_text', '')

        # 选择对应的 Schema
        if '鼠标' in category or category == 'mouse' or category == '鼠标':
            schema = MOUSE_SCHEMA
        elif '键盘' in category or category == 'keyboard' or category == '键盘':
            schema = KEYBOARD_SCHEMA
        else:
            return product

        # 初始化 specs 和 data_sources
        if 'specs' not in product:
            product['specs'] = {}
        if 'data_sources' not in product:
            product['data_sources'] = {}

        # 步骤1: 从原文章提取参数
        article_params = self._extract_from_article(article_content, schema)
        for field, value in article_params.items():
            if value and value != '未知':
                product['specs'][field] = value
                product['data_sources'][field] = 'article'

        # 步骤2: 检查缺失字段
        missing_fields = [f for f in schema.keys() if not product['specs'].get(f)]

        if not missing_fields:
            return product

        # 步骤3: 聚合搜索 + LLM 提取
        if self.search_func:
            search_params = self._aggregate_search_and_extract(
                product,
                missing_fields,
                schema
            )

            for field, value in search_params.items():
                if value and value != '未知':
                    product['specs'][field] = value
                    product['data_sources'][field] = 'search'
        else:
            # 标记缺失字段为未知
            for field in missing_fields:
                if not product['specs'].get(field):
                    product['specs'][field] = None
                    product['data_sources'][field] = 'unknown'

        return product

    def _extract_from_article(self, content: str, schema: Dict) -> Dict:
        """从文章内容中提取参数（增强版：知识库补全 + 关键参数优先）"""
        if not content:
            return {}

        import requests
        import json

        # 构造字段说明
        fields_desc = "\n".join([f"  - {field} ({schema[field]})" for field in schema])

        prompt = f"""你是一个专业的外设参数提取助手，拥有丰富的外设产品知识库。

请从以下产品文章中提取所有可用的参数信息。

需要提取的字段（Top 15 标准化 Schema）：
{fields_desc}

文章内容：
{content[:3000]}

**重要要求（P0 优先级）**：

1. **知识库补全（Critical）**：
   - 如果文章未明确提及某些参数，但你可以根据产品型号/品牌推断出常见配置，请利用你的知识库进行补全
   - 例如：罗技G304系列通常用Hero 25K传感器，雷蛇黑寡妇V4通常用Green机械轴
   - 推断的参数请标注 "（推断）" 或 "（常规配置）"

2. **严禁返回 "未知" 或 null**：
   - 对于未提及的参数，优先使用知识库推断
   - 实在无法推断的，标注 "待实测" 或 "未提及"
   - 绝对不要填 "未知" 或留空

3. **关键参数高权重提取**：

   **鼠标 - 必须优先提取**：
   - MCU/主控芯片：关键词包括 Nordic、博通、瑞昱、主控、芯片、MCU、nRF
   - 传感器：Hero、PAW3395、PAW3950、传感器型号
   - 重量：xxg、克、轻盈

   **键盘 - 必须优先提取**：
   - 前高/下沿高度：关键词 "前高"、"下沿"、"高度"、"mm"
   - 实测延迟：关键词 "延迟"、"ms"、"RT"、"回报率"
   - 磁轴特殊参数：死区（0.xx mm）、精度、触发

4. **多版本参数处理**：
   - 如果产品有多个版本（标准版/Pro版/MC版/Max版），请合并为易读格式
   - 例如：不要输出 {{'MC版': 'PAW3311', 'MAX版': 'PAW3395'}}
   - 正确输出：MC版: PAW3311 / MAX版: PAW3395

5. **输出格式**：
   - 只输出JSON格式
   - 数值单位保持原文（如 "50g", "1000Hz"）
   - 不要输出任何解释文字

输出JSON示例：
{{
  "mold_lineage": "经典G304模具，小手对称设计",
  "weight_center": "57g，重心居中",
  "sensor_solution": "Hero 25K光学传感器",
  "mcu_chip": "Nordic nRF52840（推断）",
  "polling_rate": "1000Hz"
}}

请输出JSON："""

        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.llm_config.get('api_key', '')}"
            }

            data = {
                "model": self.llm_config.get("model", ""),
                "messages": [
                    {
                        "role": "system",
                        "content": "你是一个专业的外设参数提取助手，拥有丰富的外设产品知识库。对于未提及的参数，利用知识库进行合理推断，标注（推断）。严禁返回null或未知。"
                    },
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.2,  # 稍微提高温度以允许知识库推断
                "max_tokens": 1500,  # 增加token长度以支持更详细的输出
                "stream": False
            }

            base_url = self.llm_config.get("base_url", "").rstrip('/')
            url = f"{base_url}/v1/chat/completions"

            response = requests.post(url, headers=headers, json=data, timeout=30)
            response.raise_for_status()

            result = response.json()
            extracted_text = result["choices"][0]["message"]["content"].strip()

            # 解析 JSON
            if extracted_text.startswith('```'):
                extracted_text = extracted_text.split('```')[1]
                if extracted_text.startswith('json'):
                    extracted_text = extracted_text[4:]

            extracted_params = json.loads(extracted_text)

            return {k: v for k, v in extracted_params.items() if v and v not in ['未知', 'unknown', 'null', None]}

        except Exception as e:
            # 静默失败
            return {}

    def _aggregate_search_and_extract(
        self,
        product: Dict,
        missing_fields: list,
        schema: Dict
    ) -> Dict:
        """
        聚合搜索并提取所有缺失参数

        关键优化：只执行 1 次搜索，而不是 N 次
        """
        import requests
        import json

        product_name = product.get('product_name', '')
        category = product.get('category', '')

        # 构造聚合搜索查询
        if '鼠标' in category:
            search_query = f'"{product_name}" 详细参数规格 重量 传感器 DPI 回报率 连接方式'
        else:
            search_query = f'"{product_name}" 详细参数规格 配列 结构 轴体 连接方式'

        # 执行搜索
        search_result = self.search_func(search_query)

        if not search_result:
            return {}

        # 解析搜索结果
        content = self._parse_search_result(search_result)

        if not content:
            return {}

        # LLM 一次性提取所有缺失字段
        missing_fields_desc = "\n".join([f"  - {field} ({schema[field]})" for field in missing_fields])

        prompt = f"""你是一个专业的外设参数提取助手。

请从以下产品搜索结果中提取所有可用的参数。

产品名称：{product_name}

需要提取的字段（只提取这些字段）：
{missing_fields_desc}

搜索结果：
{content}

要求：
1. 只输出JSON格式
2. 如果某个参数没有提到，设为 null
3. 输出格式示例：
{{
  "weight": "50g",
  "sensor_model": "PAW3395"
}}

请输出JSON："""

        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.llm_config.get('api_key', '')}"
            }

            data = {
                "model": self.llm_config.get("model", ""),
                "messages": [
                    {
                        "role": "system",
                        "content": "你是一个专业的外设参数提取助手。只输出JSON格式的参数数据。"
                    },
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.1,
                "max_tokens": 1000,
                "stream": False
            }

            base_url = self.llm_config.get("base_url", "").rstrip('/')
            url = f"{base_url}/v1/chat/completions"

            response = requests.post(url, headers=headers, json=data, timeout=30)
            response.raise_for_status()

            result = response.json()
            extracted_text = result["choices"][0]["message"]["content"].strip()

            # 解析 JSON
            if extracted_text.startswith('```'):
                extracted_text = extracted_text.split('```')[1]
                if extracted_text.startswith('json'):
                    extracted_text = extracted_text[4:]

            extracted_params = json.loads(extracted_text)

            return {k: v for k, v in extracted_params.items() if v and v != '未知'}

        except Exception as e:
            # 静默失败
            return {}

    def _parse_search_result(self, search_text: str) -> str:
        """解析搜索结果，提取纯文本内容"""
        import json

        try:
            results = json.loads(search_text)
            if isinstance(results, list) and len(results) > 0:
                content_texts = []
                for result in results[:3]:
                    content = result.get('content', '')
                    if content:
                        content_texts.append(content)

                if content_texts:
                    return '\n\n'.join(content_texts)
        except json.JSONDecodeError:
            pass

        return search_text


class LLMExtractor:
    """LLM 智能提取器 - PM 视角分析"""

    def __init__(self, config: Dict):
        self.config = config
        self.api_key = config.get("api_key", "")

        # 强制使用API模式
        invalid_keys = ["", "sk-your-key-here", "your-api-key", "your-api-key-here"]
        # 注意：sk-xxx 是公司内部的有效Key，不在无效列表中

        if not self.api_key or self.api_key in invalid_keys:
            raise ValueError(
                f"未配置或使用了无效的 API Key（当前: {repr(self.api_key)}）！\n"
                f"请配置有效的API Key后重试。\n"
                f"修改位置: etl_pipeline.py 第22行"
            )

        self.use_mock = False
        print(f"[INFO] 使用真实API模式（API Key: {self.api_key[:15]}...)")

        # 品牌权重配置（用于排序）
        self.brand_weights = {
            '罗技': 100, 'logitech': 100,
            '雷蛇': 95, 'razer': 95,
            'rog': 90, '华硕': 85,
            '赛睿': 85, 'steelseries': 85,
            '海盗船': 80, 'corsair': 80,
            '卓威': 80, 'zowie': 80,
            'vgn': 70, 'vek': 70,
            'atk': 65, '狼蛛': 60,
            '雷柏': 55, 'rapoo': 55,
            '英菲克': 50,
            '魔炼': 45,
            '黑科': 40
        }

    def extract_price_from_content(self, content: str) -> Optional[str]:
        """
        使用正则表达式从正文内容中暴力提取价格

        支持的模式：
        - 售价约XXX元
        - 首发价XXX
        - 到手XXX元
        - 定价XXX元
        """
        if not content:
            return None

        # 多种价格匹配模式
        price_patterns = [
            r'(?:售价|价格|首发|定价|到手|约|约\s*¥|¥|\$)\s*(\d{2,4})\s*(?:元|圆|rmb)?',
            r'(\d{2,4})\s*(?:元|圆|rmb)\s*(?:售价|价格|首发|定价)?',
            r'(?:售价|价格|首发|定价).*?(\d{2,4})\s*(?:元|圆)?',
        ]

        for pattern in price_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                price = match.group(1)
                # 过滤掉明显不是价格的数字（如日期、型号）
                if 29 <= int(price) <= 2999:  # 合理的外设价格范围
                    return f"{price}元（预估）"

        return None

    def calculate_product_priority(self, product: Dict) -> float:
        """
        计算产品优先级分数（用于排序）

        考虑因素：
        1. 品牌权重（罗技/雷蛇/ROG等一线品牌优先）
        2. 文章长度（长文章=深度评测=更值得关注）
        3. 图片数量（多图=更完整的产品展示）

        Returns:
            优先级分数（越高越靠前）
        """
        score = 0.0

        # 1. 品牌权重（0-100分）
        product_name = product.get('product_name', '').lower()
        brand_weight = 0

        for brand, weight in self.brand_weights.items():
            if brand in product_name:
                brand_weight = max(brand_weight, weight)

        score += brand_weight

        # 2. 文章长度权重（0-30分）
        # 文章越长，说明信息越完整
        content = product.get('combined_content', '')
        article_length = len(content)
        length_score = min(30, article_length / 500)  # 每500字符加1分，最高30分
        score += length_score

        # 3. 图片数量权重（0-10分）
        images = product.get('images', [])
        image_count = len(images) if isinstance(images, list) else 0
        image_score = min(10, image_count * 2)  # 每张图2分，最高10分
        score += image_score

        return score

    def extract_product_info(self, product: Dict) -> Dict:
        """提取产品信息 - PM 视角深度分析（强制使用API）"""
        # 强制使用真实的 LLM 调用
        context = product['combined_content'][:10000]  # 增加长度限制以支持 PM 分析

        # 提取主图
        main_image = product.get('images', [''])[0] if product.get('images') else ''

        prompt = f"""你是一位资深的外设产品经理和硬件评测师，擅长从产品新闻稿中提取关键信息并进行深度竞品分析、批判性评估。

请阅读以下产品文档，提取核心参数并进行深度分析。

文本内容：
{context}

请严格按照以下 JSON 格式返回（不要有任何其他文字）：

{{
  "product_name": "标准化产品全名",
  "category": "鼠标" 或 "键盘" 或 "其他",
  "main_image": "{main_image}",
  "release_price": "发布价格（如有）",
  "innovation_tags": ["创新标签1", "创新标签2"],
  "specs": {{
    // 鼠标 Top 15 Schema 字段
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

    // 键盘 Top 15 Schema 字段
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
  }},
  "analysis": {{
    "market_position": "一句话产品定位（含价格段和目标市场）",
    "competitors": "主要竞品对比（必须提及2-3个具体型号，包括相同价位/规格的竞品）",
    "target_audience": "目标用户群体（具体到握姿/手型/使用场景）",
    "selling_point": "核心卖点（明确差异化优势，与竞品的具体区别）",
    "verdict": {{
      "pros": ["优点1", "优点2", "优点3"],
      "cons": ["缺点1", "缺点2", "缺点3（必须指出至少1个缺点，如溢价过高、续航尿崩、质感廉价等）"]
    }},
    "pm_summary": "购买建议（30字以内，直白犀利，结合竞品给出明确建议）"
  }}
}}

**深度分析要求（P0 优先级）**：

1. **竞品对比（Critical）**：
   - 必须提及2-3个具体竞品型号，而非泛泛而谈
   - 对比维度：价格、核心参数（传感器/轴体）、重量、续航、做工质感
   - 明确指出本品在竞品中的位置：领先/持平/落后

2. **目标用户（拒绝套路化）**：
   - **禁止**泛泛而谈："适合追求轻量化的玩家"
   - **要求**具体到：握姿、手型、使用场景、预算段
   - 示例：
     * Bad: "适合追求性能的游戏玩家"
     * Good: "直接对标雷蛇毒蝰V3，但价格仅为一半，适合预算不足但想要模具平替的抓握玩家"
     * Good: "适合小手抓握/指握玩家，重量控制在50g以内，长时间FPS游戏不累"

3. **核心卖点（明确差异化）**：
   - 不要只罗列参数，要说明"为什么"值得买
   - 明确与竞品的差异化优势
   - 示例：
     * Bad: "卖点是轻量化和高性能"
     * Good: "同价位唯一搭载PAW3950的鼠标，比竞品VGN蜻蜓轻10g，但续航提升40%"

4. **创新标签识别**：
   从以下标签中选择适用的（也可自定义）：
   - #卷王价格（同规格最低价）
   - #首发新技术（首次搭载新传感器/新轴体）
   - #IP联名（与动漫/游戏联名）
   - #特殊配列（如98配列、65%配列）
   - #超轻量化（<50g鼠标）
   - #长续航（>100小时）
   - #旗舰做工（金属材质、精细CNC）

5. **缺点批判（必须犀利）**：
   - 必须指出至少1-3个缺点
   - 常见缺点：
     * 电池容量小（如300mAh）→ "续航可能尿崩，重度玩家需每日充电"
     * 价格高于竞品 → "溢价过高缺乏诚意，同配置竞品便宜100元"
     * 做工一般 → "塑料感强，质感廉价，不如上代产品"
     * 功能缺失 → "缺少8K回报率，实用性打折"
     * MCU未知 → "主控方案存疑，需关注实测稳定性"

6. **购买建议（PM Summary）**：
   - 30字以内，直白犀利
   - 必须给出明确的购买建议：值得买/观望/不推荐
   - 结合竞品给出具体理由
   - 示例：
     * "299元买Hero 25K+58g轻量化，闭眼入"
     * "等降价，同价位VGN蜻蜓配置更高"

7. **参数提取**：
   - 尽可能多地提取所有参数，不要留空
   - 尺寸格式：长x宽x高（如：120x65x40mm）
   - 价格格式：数字+单位（如：299元）
   - 特殊功能多个用顿号分隔
"""

        result = self._call_llm(prompt)
        extracted_data = self._parse_json_response(result)

        # [DEBUG] 打印原始响应和数据流
        print(f"      [DEBUG-LLM] 原始响应长度: {len(result)} 字符")
        print(f"      [DEBUG-LLM] 解析后的顶级字段: {list(extracted_data.keys())}")
        if 'specs' in extracted_data:
            print(f"      [DEBUG-LLM] specs子字段: {list(extracted_data['specs'].keys())}")
            print(f"      [DEBUG-LLM] specs非空字段: {[k for k,v in extracted_data['specs'].items() if v and v.strip()]}")

        # 确保 main_image 字段存在
        if 'main_image' not in extracted_data or not extracted_data['main_image']:
            extracted_data['main_image'] = main_image

        # 价格回退机制：如果LLM未提取到价格，使用正则表达式提取
        if not extracted_data.get('release_price') or extracted_data['release_price'] == '价格未公开':
            estimated_price = self.extract_price_from_content(context)
            if estimated_price:
                extracted_data['release_price'] = estimated_price
                print(f"      [价格提取] 正则提取到预估价格: {estimated_price}")

        # 价格标准化：处理外币转换和格式统一
        if extracted_data.get('release_price'):
            original_price = extracted_data['release_price']
            standardized_price = HTMLReportGenerator._standardize_price(original_price)
            if standardized_price != original_price:
                extracted_data['release_price'] = standardized_price
                print(f"      [价格标准化] {original_price} -> {standardized_price}")

        # 确保 innovation_tags 字段存在（如果LLM未返回）
        if 'innovation_tags' not in extracted_data:
            extracted_data['innovation_tags'] = []

        # [FIX 7] innovation_tags 归一化：去 #、全半角统一、去重
        if extracted_data.get('innovation_tags'):
            normalized_tags = normalize_innovation_tags(extracted_data['innovation_tags'])
            if normalized_tags != extracted_data['innovation_tags']:
                print(f"      [标签归一化] {extracted_data['innovation_tags']} -> {normalized_tags}")
            extracted_data['innovation_tags'] = normalized_tags

        return extracted_data

    def _call_llm(self, prompt: str) -> str:
        """调用 LLM API（带重试机制）"""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        data = {
            "model": self.config["model"],
            "messages": [
                {
                    "role": "system",
                    "content": "你是一位资深的外设产品经理，擅长从产品新闻稿中提取关键信息并进行深度市场分析、竞品对比、优缺点评估。"
                },
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3,
            "max_tokens": 3000,
            "stream": False
        }

        # 构建完整的 API URL
        base_url = self.config["base_url"].rstrip('/')
        url = f"{base_url}/v1/chat/completions"

        # 重试机制：最多重试3次，使用指数退避
        max_retries = 3
        base_delay = 2  # 初始延迟2秒

        for attempt in range(max_retries):
            try:
                response = requests.post(url, headers=headers, json=data, timeout=120)
                response.raise_for_status()
                result = response.json()
                return result["choices"][0]["message"]["content"]

            except requests.exceptions.HTTPError as e:
                # 429 Too Many Requests 或 5xx 服务器错误
                if e.response.status_code == 429 or e.response.status_code >= 500:
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)  # 指数退避: 2s, 4s, 8s
                        print(f"      [API错误] {e.response.status_code}，{delay}秒后重试 ({attempt + 1}/{max_retries})...")
                        time.sleep(delay)
                        continue
                    else:
                        raise Exception(f"API调用失败，已达最大重试次数: {e}")
                else:
                    # 其他HTTP错误不重试
                    raise Exception(f"API调用失败: {e}")

            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                # 超时或连接错误
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    print(f"      [网络错误] {type(e).__name__}，{delay}秒后重试 ({attempt + 1}/{max_retries})...")
                    time.sleep(delay)
                    continue
                else:
                    raise Exception(f"网络连接失败，已达最大重试次数: {e}")

            except Exception as e:
                # 其他异常不重试
                raise Exception(f"未知错误: {e}")

    @staticmethod
    def _parse_json_response(response: str) -> Dict:
        """解析 JSON 响应"""
        # 尝试直接解析
        try:
            return json.loads(response)
        except:
            pass

        # 尝试提取 JSON 代码块
        json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except:
                pass

        # 尝试提取大括号内容
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except:
                pass

        raise ValueError("无法解析 LLM 返回的 JSON")


# ==================== 产品合并工具 ====================

class ProductMerger:
    """产品级别去重与合并工具"""

    @staticmethod
    def normalize_product_name(name: str) -> str:
        """标准化产品名称，用于去重比较（改进版）"""
        if not isinstance(name, str):
            return ""

        # 移除所有空格（处理 "G304 X" vs "G304X"）
        normalized = re.sub(r'\s+', '', name)
        # 统一大小写
        normalized = normalized.lower()
        # 移除常见品牌后缀
        normalized = re.sub(r'(lightspeed|wireless|gaming|rgb|pro|ultra|max|heroc|版|无线|有线)', '', normalized)
        # 移除特殊字符（保留字母、数字、中文）
        normalized = re.sub(r'[^a-z0-9\u4e00-\u9fff]', '', normalized)
        return normalized

    @staticmethod
    def calculate_similarity(name1: str, name2: str) -> float:
        """计算两个产品名称的相似度"""
        norm1 = ProductMerger.normalize_product_name(name1)
        norm2 = ProductMerger.normalize_product_name(name2)

        if not norm1 or not norm2:
            return 0.0

        return SequenceMatcher(None, norm1, norm2).ratio()

    @classmethod
    def merge_products(cls, products: List[Dict]) -> List[Dict]:
        """合并重复的产品"""
        if not products:
            return []

        # 按类别分组
        by_category = {}
        for p in products:
            cat = p.get('category', '其他')
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(p)

        merged = []

        for category, cat_products in by_category.items():
            # 对每个类别进行合并
            merged.extend(cls._merge_category_products(cat_products))

        return merged

    @classmethod
    def _merge_category_products(cls, products: List[Dict]) -> List[Dict]:
        """合并同一类别的产品"""
        if len(products) <= 1:
            return products

        merged = []
        used_indices = set()

        for i, product1 in enumerate(products):
            if i in used_indices:
                continue

            # 当前产品作为基础
            base_product = product1.copy()
            matching_indices = [i]

            # 查找相似产品
            for j, product2 in enumerate(products):
                if j <= i or j in used_indices:
                    continue

                similarity = cls.calculate_similarity(
                    base_product.get('product_name', ''),
                    product2.get('product_name', '')
                )

                # 相似度阈值 0.7（较高的阈值确保是同一产品）
                if similarity >= 0.7:
                    matching_indices.append(j)

            # 合并所有匹配的产品
            for idx in matching_indices:
                if idx != i:
                    base_product = cls._merge_two_products(base_product, products[idx])
                used_indices.add(idx)

            merged.append(base_product)

        return merged

    @staticmethod
    def _merge_two_products(base: Dict, other: Dict) -> Dict:
        """合并两个产品数据"""
        # 合并 _raw 中的记录
        base_raw = base.get('_raw', {})
        other_raw = other.get('_raw', {})

        merged_raw = {
            'product_name': base_raw.get('product_name', base.get('product_name', '')),
            'records': [],
            'images': [],
            'sources': [],
            'combined_content': ''
        }

        # 合并 records
        base_records = base_raw.get('records', [])
        other_records = other_raw.get('records', [])

        all_records = base_records + other_records

        # 去重 records（按 URL）
        seen_urls = set()
        unique_records = []
        for record in all_records:
            url = record.get('url', '')
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_records.append(record)

        merged_raw['records'] = unique_records

        # 合并图片
        base_images = base_raw.get('images', [])
        other_images = other_raw.get('images', [])
        all_images = list(set(base_images + other_images))
        merged_raw['images'] = all_images

        # 合并来源
        base_sources = base_raw.get('sources', [])
        other_sources = other_raw.get('sources', [])
        all_sources = list(set(base_sources + other_sources))
        merged_raw['sources'] = all_sources

        # 更新 base 产品
        base['_raw'] = merged_raw

        # 优先使用有 specs 的产品
        if other.get('specs') and any(other.get('specs', {}).values()):
            base['specs'] = other.get('specs', {})

        # 合并价格（优先使用有价格的）
        if other.get('release_price') and other['release_price'] != '价格未公开':
            if not base.get('release_price') or base['release_price'] == '价格未公开':
                base['release_price'] = other['release_price']

        # 优先使用有图片的
        if other.get('main_image') and not base.get('main_image'):
            base['main_image'] = other['main_image']

        # 合并 analysis（优先使用有内容的）
        base_analysis = base.get('analysis', {})
        other_analysis = other.get('analysis', {})

        if other_analysis and any(other_analysis.values()):
            # 如果 base 分析为空，使用 other 的
            if not any(base_analysis.values()):
                base['analysis'] = other_analysis

        return base


# ==================== 市场趋势分析器 ====================

class MarketAnalyzer:
    """市场趋势分析器 - 为PM提供宏观决策辅助"""

    def __init__(self, products: List[Dict]):
        self.products = products
        self.mice = [p for p in products if p.get('category') == '鼠标']
        self.keyboards = [p for p in products if p.get('category') == '键盘']

    def analyze_tech_trends(self) -> str:
        """分析技术趋势"""
        trends = []

        # 1. 分析鼠标传感器趋势
        if self.mice:
            sensor_count = {}
            for mouse in self.mice:
                sensor = mouse.get('specs', {}).get('sensor', '')
                if '3395' in sensor:
                    sensor_count['PAW3395'] = sensor_count.get('PAW3395', 0) + 1
                elif '3950' in sensor:
                    sensor_count['PAW3950'] = sensor_count.get('PAW3950', 0) + 1
                elif 'Hero' in sensor:
                    sensor_count['Hero系列'] = sensor_count.get('Hero系列', 0) + 1

            if sensor_count:
                top_sensor = max(sensor_count, key=sensor_count.get)
                count = sensor_count[top_sensor]
                pct = count * 100 // len(self.mice)
                trends.append(f"🖱️ 鼠标市场：{top_sensor}传感器占主导（{count}款，{pct}%），")

        # 2. 分析键盘轴体趋势
        if self.keyboards:
            switch_count = {'磁轴': 0, '机械轴': 0, '静电容': 0}
            for keyboard in self.keyboards:
                switch = keyboard.get('specs', {}).get('switch', '')
                if '磁轴' in switch:
                    switch_count['磁轴'] += 1
                elif '轴' in switch:
                    switch_count['机械轴'] += 1

            if any(switch_count.values()):
                top_switch = max(switch_count, key=switch_count.get)
                count = switch_count[top_switch]
                if count > 0:
                    pct = count * 100 // len(self.keyboards)
                    trends.append(f"⌨️ 键盘市场：{top_switch}呈井喷态势（{count}款，{pct}%），")

        # 3. 分析价格趋势
        price_ranges = {'0-199': 0, '200-499': 0, '500-999': 0, '1000+': 0}
        for product in self.products:
            price = product.get('specs', {}).get('price', '') or product.get('release_price', '')
            price_match = re.search(r'(\d+)', str(price))
            if price_match:
                price_num = int(price_match.group(1))
                if price_num < 200:
                    price_ranges['0-199'] += 1
                elif price_num < 500:
                    price_ranges['200-499'] += 1
                elif price_num < 1000:
                    price_ranges['500-999'] += 1
                else:
                    price_ranges['1000+'] += 1

        top_range = max(price_ranges, key=price_ranges.get)
        if price_ranges[top_range] > 0:
            trends.append(f"💰 价格段：{top_range}元区间竞争最激烈（{price_ranges[top_range]}款），")

        # 4. 分析创新标签趋势
        innovation_tags = {}
        for product in self.products:
            for tag in product.get('innovation_tags', []):
                innovation_tags[tag] = innovation_tags.get(tag, 0) + 1

        if innovation_tags:
            top_tag = max(innovation_tags, key=innovation_tags.get)
            count = innovation_tags[top_tag]
            trends.append(f"🏷️ 创新标签：{top_tag}最为流行（{count}款）。")

        return ' '.join(trends) if trends else "本月新品数量较少，暂无明显趋势。"

    def analyze_pricing_insights(self) -> str:
        """分析价格行情"""
        insights = []

        # 计算鼠标平均价格
        mouse_prices = []
        for mouse in self.mice:
            price = mouse.get('specs', {}).get('price', '') or mouse.get('release_price', '')
            price_match = re.search(r'(\d+)', str(price))
            if price_match:
                mouse_prices.append(int(price_match.group(1)))

        # 计算键盘平均价格
        keyboard_prices = []
        for keyboard in self.keyboards:
            price = keyboard.get('specs', {}).get('price', '') or keyboard.get('release_price', '')
            price_match = re.search(r'(\d+)', str(price))
            if price_match:
                keyboard_prices.append(int(price_match.group(1)))

        if mouse_prices:
            avg_mouse = sum(mouse_prices) // len(mouse_prices)
            insights.append(f"鼠标市场均价约{avg_mouse}元")

            # 检查价格两极分化
            if min(mouse_prices) < avg_mouse * 0.3 and max(mouse_prices) > avg_mouse * 2:
                insights.append("呈现两极分化态势（百元级卷配置与千元级卷IP并存）")
            else:
                insights.append("价格分布相对均衡")

        if keyboard_prices:
            avg_keyboard = sum(keyboard_prices) // len(keyboard_prices)
            insights.append(f"键盘市场均价约{avg_keyboard}元")

            # 检查价格趋势
            magnetic_keyboards = [k for k in self.keyboards if '磁轴' in k.get('specs', {}).get('switch', '')]
            if magnetic_keyboards:
                mag_prices = []
                for k in magnetic_keyboards:
                    price = k.get('specs', {}).get('price', '') or k.get('release_price', '')
                    price_match = re.search(r'(\d+)', str(price))
                    if price_match:
                        mag_prices.append(int(price_match.group(1)))
                if mag_prices and min(mag_prices) < 400:
                    insights.append("磁轴键盘价格已下探至300元区间，卷王之战加剧")

        # Trim 并确保句子完整
        result = ' '.join(insights) if insights else "暂无足够价格数据"
        return result.strip() + ('。' if not result.endswith(('。', '！', '？')) else '')

    def generate_pm_takeaways(self) -> str:
        """生成PM战略启示"""
        takeaways = []

        # 传感器启示
        sensor_3395_count = sum(1 for m in self.mice if '3395' in m.get('specs', {}).get('sensor_solution', ''))
        sensor_3950_count = sum(1 for m in self.mice if '3950' in m.get('specs', {}).get('sensor_solution', ''))

        if sensor_3395_count > 0:
            if sensor_3950_count > sensor_3395_count:
                takeaways.append("🎯 PAW3950传感器正在快速普及，建议新品优先采用3950以保持竞争力")
            else:
                takeaways.append("🎯 PAW3395传感器仍是主流，但红利期已过，需寻找新差异点（如涂层、模具、8K回报率）")

        # 磁轴键盘启示
        magnetic_count = sum(1 for k in self.keyboards if '磁轴' in k.get('specs', {}).get('switch_type', ''))
        if magnetic_count > len(self.keyboards) * 0.3:
            takeaways.append("🎯 磁轴键盘已成主流，建议跟进磁轴产品线或寻找差异化定位")

        # 价格定位启示
        budget_products = sum(1 for p in self.products if '卷王' in ' '.join(p.get('innovation_tags', [])))
        if budget_products > len(self.products) * 0.3:
            takeaways.append("🎯 性价比市场竞争白热化，建议考虑高端化路线或细分市场定位")

        # 技术特性启示
        high_polling_count = sum(1 for m in self.mice if '8k' in m.get('specs', {}).get('polling_rate', '').lower())
        if high_polling_count > len(self.mice) * 0.3:
            takeaways.append("🎯 8K回报率逐渐成为标配，建议在营销中强化'低延迟'卖点")

        if not takeaways:
            takeaways.append("🎯 建议持续关注市场动态，积累更多数据后再制定战略")

        # 拼接并确保结尾有标点
        result = ' '.join(takeaways)
        return result + ('。' if not result.endswith(('。', '！', '？')) else '')

    def get_chart_data(self) -> Dict:
        """获取图表数据"""
        # 1. 品类占比 - 动态生成，只包含数量>0的分类
        # [FIX] 使用统一数据源：直接使用 self.mice/keyboards/others 的长度
        category_labels = []
        category_data_list = []

        if len(self.mice) > 0:
            category_labels.append('鼠标')
            category_data_list.append(len(self.mice))
        if len(self.keyboards) > 0:
            category_labels.append('键盘')
            category_data_list.append(len(self.keyboards))
        if len(self.others) > 0:
            category_labels.append('其他')
            category_data_list.append(len(self.others))

        # 断言验证：确保数据一致
        assert sum(category_data_list) == len(self.products), \
            f"统计口径不一致！图表数据总和({sum(category_data_list)}) != 产品总数({len(self.products)})"

        category_data = {
            'labels': category_labels,
            'data': category_data_list
        }

        # 2. 传感器分布 - [FIX B] 分桶逻辑重构，明确缺失值 taxonomy
        sensor_dist = {}
        print(f"\n[DEBUG-CHART] 开始统计传感器分布，共 {len(self.mice)} 个鼠标")

        # [FIX B.1] 统一缺失值 taxonomy + 明确分桶
        # 缺失值优先级：未公开 > 未提及 > 待实测 > 预估
        # 只有"明确型号"才计入覆盖率
        temp_sensor_dist = {
            'PAW3395': 0, 'PAW3950': 0, 'Hero系列': 0, 'PMW3335': 0, 'PAW3335': 0, '其他明确型号': 0,
            '未公开': 0, '未提及': 0, '待实测': 0, '预估': 0
        }

        for idx, mouse in enumerate(self.mice):
            sensor = mouse.get('specs', {}).get('sensor_solution', '')
            sensor_lower = sensor.lower() if sensor else ''

            # [DEBUG] 打印前3个鼠标的字段访问情况
            if idx < 3:
                print(f"  [DEBUG-CHART] 鼠标{idx+1}: {mouse.get('product_name', 'Unknown')[:30]}")
                print(f"    - sensor_solution字段值: '{sensor}'")

            # [FIX B.2] 缺失值判定（按优先级）
            if not sensor or sensor.strip() == '':
                temp_sensor_dist['未提及'] += 1
            elif any(marker in sensor_lower for marker in ['未公开', '厂商未公开', 'tbd', '待公布']):
                temp_sensor_dist['未公开'] += 1
            elif any(marker in sensor_lower for marker in ['未提及', '原文未提及', '未提供']):
                temp_sensor_dist['未提及'] += 1
            elif any(marker in sensor_lower for marker in ['待实测', '待官方实测', '实测中']):
                temp_sensor_dist['待实测'] += 1
            elif any(marker in sensor_lower for marker in ['预估', '推断', '推测', '可能']):
                temp_sensor_dist['预估'] += 1
            # [FIX B.3] 明确型号判定（只统计具体型号）
            elif '3395' in sensor:
                temp_sensor_dist['PAW3395'] += 1
            elif '3950' in sensor:
                temp_sensor_dist['PAW3950'] += 1
            elif 'hero' in sensor_lower and any(kw in sensor_lower for kw in ['25k', '26k', '27k', 'hero']):
                temp_sensor_dist['Hero系列'] += 1
            elif any(model in sensor for model in ['PMW3335', 'PAW3335', '3389', '3392']):
                if 'PMW3335' in sensor or '3335' in sensor:
                    temp_sensor_dist['PMW3335'] += 1
                elif 'PAW3335' in sensor:
                    temp_sensor_dist['PAW3335'] += 1
                else:
                    temp_sensor_dist['其他明确型号'] += 1
            elif any(marker in sensor_lower for marker in ['光学', '激光', '蓝牙', '无线', '有线']):
                # 通用传感器类型，也算"明确型号"
                temp_sensor_dist['其他明确型号'] += 1
            else:
                # 无法归类的描述性内容
                temp_sensor_dist['未提及'] += 1

        # 只保留数量>0的桶
        for key, value in temp_sensor_dist.items():
            if value > 0:
                sensor_dist[key] = value

        print(f"[DEBUG-CHART] 传感器分布结果: {sensor_dist}")

        # 3. 价格区间分布 (修正: 使用 bucket_value() 统一口径)
        price_ranges = {'0-199元': 0, '200-499元': 0, '500-999元': 0, '1000元+': 0, '未公开': 0, '待实测': 0}
        print(f"\n[DEBUG-CHART] 开始统计价格区间分布，共 {len(self.products)} 个产品")

        for idx, product in enumerate(self.products):
            # 优先从 specs.product_pricing 获取，然后尝试 release_price
            price = (
                product.get('specs', {}).get('product_pricing', '') or
                product.get('release_price', '')
            )

            # [DEBUG] 打印前3个产品的字段访问情况
            if idx < 3:
                print(f"  [DEBUG-CHART] 产品{idx+1}: {product.get('product_name', 'Unknown')[:30]}")
                print(f"    - product_pricing: '{product.get('specs', {}).get('product_pricing', '')}'")
                print(f"    - release_price: '{product.get('release_price', '')}'")
                print(f"    - 最终价格值: '{price}'")

            # [FIX 2.1] 使用 bucket_value() 获取分桶值
            bucket_val = bucket_value(price)

            if bucket_val is None:
                # 空值/未提及/提取失败 → 不计入图表
                continue

            # 检查是否为明确的"未公开"标记
            if any(marker in bucket_val for marker in PRICE_UNDISCLOSED_MARKERS):
                price_ranges['未公开'] += 1
            elif '待实测' in bucket_val or '概念' in bucket_val:
                price_ranges['待实测'] += 1
            else:
                # 尝试解析数字进行分桶
                price_match = re.search(r'(\d+)', str(bucket_val))
                if price_match:
                    price_num = int(price_match.group(1))
                    if price_num < 200:
                        price_ranges['0-199元'] += 1
                    elif price_num < 500:
                        price_ranges['200-499元'] += 1
                    elif price_num < 1000:
                        price_ranges['500-999元'] += 1
                    else:
                        price_ranges['1000元+'] += 1
                else:
                    # 无法解析但有内容 → 归入"未公开"
                    price_ranges['未公开'] += 1

        print(f"[DEBUG-CHART] 价格区间分布结果: {price_ranges}")

        # 4. 计算覆盖率统计 - [FIX B.4] 覆盖率只统计"明确型号"
        # 定义辅助函数：判断传感器是否为"明确型号"
        def _is_explicit_sensor_model(sensor_value: str) -> bool:
            """判断传感器值是否为明确型号（用于覆盖率计算）"""
            if not sensor_value or not isinstance(sensor_value, str):
                return False
            sensor_lower = sensor_value.lower().strip()

            # 排除缺失值
            if any(marker in sensor_lower for marker in [
                '未公开', '未提及', '待实测', '预估', '推断', '推测', '可能',
                'tbd', 'unknown', 'none', 'null'
            ]):
                return False

            # 判断是否包含明确型号关键词或型号
            explicit_keywords = [
                '3395', '3950', 'hero', 'pmw3335', 'paw3335', '3389', '3392',
                '光学', '激光', '蓝牙', '无线', '有线', 'pixart', '原相'
            ]
            return any(kw in sensor_lower for kw in explicit_keywords)

        total_mice = len(self.mice)
        # [FIX B.4] 传感器覆盖率分子：只统计"明确型号"
        sensor_known = sum(1 for m in self.mice if _is_explicit_sensor_model(m.get('specs', {}).get('sensor_solution', '')))
        sensor_coverage = sensor_known / total_mice if total_mice > 0 else 0

        total_products = len(self.products)
        # 价格覆盖率：使用 is_coverage_value() 统计有效值
        price_known = sum(1 for p in self.products if is_coverage_value(
            p.get('specs', {}).get('product_pricing', '') or p.get('release_price', '')
        ))
        price_coverage = price_known / total_products if total_products > 0 else 0

        coverage_stats = {
            'sensor': {
                'total': total_mice,
                'known': sensor_known,  # 明确型号数量
                'coverage': sensor_coverage
            },
            'price': {
                'total': total_products,
                'known': price_known,
                'coverage': price_coverage
            }
        }

        return {
            'category': category_data,
            'sensor': sensor_dist,
            'price_range': price_ranges,
            'coverage': coverage_stats
        }


# ==================== 任务三：深色极客风 HTML 报告生成 ====================

class HTMLReportGenerator:
    """HTML 报告生成器 - 深色极客风格 Phase 4 优化版"""

    def __init__(self, products: List[Dict]):
        # 先合并重复产品
        self.products = ProductMerger.merge_products(products)

        self.mice = [p for p in self.products if p.get('category') == '鼠标']
        self.keyboards = [p for p in self.products if p.get('category') == '键盘']
        self.others = [p for p in self.products if p.get('category') not in ['鼠标', '键盘']]

        # 初始化市场分析器
        self.market_analyzer = MarketAnalyzer(self.products)

        # 打印合并统计
        original_count = len(products)
        merged_count = len(self.products)
        if original_count > merged_count:
            print(f"[OK] 产品合并: {original_count} -> {merged_count} (-{original_count - merged_count} 重复)")

    def generate(self, output_path: Path):
        """生成 HTML 报告"""
        # 如果文件已存在，先备份
        if output_path.exists():
            backup_path = output_path.with_suffix('.html.bak')
            import shutil
            shutil.copy2(output_path, backup_path)
            print(f"[BACKUP] 已备份旧文件: {backup_path}")

        # 生成 HTML
        html = self._build_html()

        # 使用覆盖模式写入（'w'）
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)

        # 获取绝对路径和生成时间
        from datetime import datetime
        abs_path = output_path.resolve()
        gen_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        print(f"\n{'='*60}")
        print(f"[OK] HTML 报告已生成")
        print(f"  生成时间: {gen_time}")
        print(f"  文件路径: {abs_path}")
        print(f"  请打开该路径文件查看报告（避免打开旧版本）")
        print(f"{'='*60}\n")

        # 数据质量警告
        chart_data = self.market_analyzer.get_chart_data()
        coverage = chart_data['coverage']

        sensor_unknown_ratio = coverage['sensor']['coverage']
        price_unknown_ratio = coverage['price']['coverage']

        warnings = []
        if sensor_unknown_ratio == 0:
            warnings.append("⚠️  传感器数据覆盖率为 0%，所有鼠标产品的传感器信息缺失")
        elif (coverage['sensor']['total'] - coverage['sensor']['known']) / coverage['sensor']['total'] > 0.8:
            warnings.append(f"⚠️  传感器数据质量差：未知占比 >80% ({coverage['sensor']['known']}/{coverage['sensor']['total']})")

        if price_unknown_ratio == 0:
            warnings.append("⚠️  价格数据覆盖率为 0%，所有产品的价格信息缺失")
        elif (coverage['price']['total'] - coverage['price']['known']) / coverage['price']['total'] > 0.8:
            warnings.append(f"⚠️  价格数据质量差：未公开占比 >80% ({coverage['price']['known']}/{coverage['price']['total']})")

        if warnings:
            print("\n" + "="*60)
            print("[WARNING] 数据质量警告:")
            for warning in warnings:
                print(f"  {warning}")
            print("="*60)
            print("建议：请检查输入数据质量，确保关键字段（sensor_solution、product_pricing）正确提取\n")

    def _build_html(self) -> str:
        """构建完整的 HTML"""
        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{TARGET_YEAR}年{TARGET_MONTH}月外设新品监控报告 - PM深度分析版</title>
    <script src="assets/js/chart.umd.min.js" onerror="this.onerror=null; this.src='https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js'; console.warn('[WARNING] 本地 Chart.js 未找到，使用 CDN 版本。运行 scripts/download_assets.sh 下载本地版本以提高加载速度。');"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #e0e0e0;
            padding: 20px;
            line-height: 1.6;
            min-height: 100vh;
        }}

        .container {{
            max-width: 1400px;
            margin: 0 auto;
            padding-bottom: 80px;
        }}

        /* 导航栏 */
        .nav-bar {{
            position: sticky;
            top: 0;
            background: rgba(26, 26, 46, 0.95);
            backdrop-filter: blur(10px);
            padding: 15px 20px;
            border-radius: 12px;
            margin-bottom: 30px;
            z-index: 100;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 15px;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }}

        .nav-buttons {{
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }}

        .nav-btn {{
            padding: 10px 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 8px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s;
            text-decoration: none;
        }}

        .nav-btn:hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
        }}

        /* 搜索框 */
        .search-box {{
            position: relative;
            flex: 1;
            max-width: 400px;
        }}

        .search-input {{
            width: 100%;
            padding: 12px 45px 12px 20px;
            background: rgba(255, 255, 255, 0.1);
            border: 1px solid rgba(102, 126, 234, 0.3);
            border-radius: 25px;
            color: white;
            font-size: 0.95em;
            transition: all 0.3s;
        }}

        .search-input:focus {{
            outline: none;
            background: rgba(255, 255, 255, 0.15);
            border-color: #667eea;
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.2);
        }}

        .search-input::placeholder {{
            color: #a0aec0;
        }}

        .search-icon {{
            position: absolute;
            right: 15px;
            top: 50%;
            transform: translateY(-50%);
            color: #a0aec0;
            font-size: 1.2em;
        }}

        .header {{
            text-align: center;
            padding: 40px 20px;
            background: rgba(37, 47, 78, 0.6);
            border-radius: 16px;
            margin-bottom: 40px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.1);
        }}

        .header h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
            font-weight: 700;
            color: #ffffff;
            text-shadow: 0 2px 10px rgba(102, 126, 234, 0.5);
        }}

        .header .subtitle {{
            font-size: 1.2em;
            color: #a0aec0;
            font-weight: 300;
            margin-bottom: 20px;
        }}

        .stats {{
            display: flex;
            justify-content: center;
            gap: 30px;
            flex-wrap: wrap;
        }}

        .stat-item {{
            background: rgba(102, 126, 234, 0.2);
            padding: 20px 30px;
            border-radius: 12px;
            border: 1px solid rgba(102, 126, 234, 0.3);
            text-align: center;
        }}

        .stat-number {{
            font-size: 2.5em;
            font-weight: 700;
            color: #667eea;
        }}

        .stat-label {{
            font-size: 0.9em;
            color: #a0aec0;
            margin-top: 5px;
        }}

        /* Executive Summary Styles */
        .executive-summary {{
            background: linear-gradient(135deg, rgba(102, 126, 234, 0.15) 0%, rgba(118, 75, 162, 0.15) 100%);
            border-radius: 16px;
            padding: 30px;
            margin-bottom: 40px;
            border: 1px solid rgba(102, 126, 234, 0.3);
            box-shadow: 0 8px 32px rgba(102, 126, 234, 0.2);
        }}

        .summary-title {{
            font-size: 1.8em;
            font-weight: 700;
            color: #ffffff;
            margin-bottom: 25px;
            text-align: center;
            border-bottom: 2px solid rgba(102, 126, 234, 0.5);
            padding-bottom: 15px;
        }}

        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 25px;
            margin-bottom: 30px;
        }}

        .summary-card {{
            background: rgba(0, 0, 0, 0.3);
            border-radius: 12px;
            padding: 20px;
            border: 1px solid rgba(255, 255, 255, 0.1);
            transition: all 0.3s;
        }}

        .summary-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 8px 24px rgba(102, 126, 234, 0.3);
            border-color: rgba(102, 126, 234, 0.5);
        }}

        .summary-card-header {{
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 15px;
        }}

        .summary-card-icon {{
            font-size: 1.5em;
        }}

        .summary-card-title {{
            font-size: 1.2em;
            font-weight: 600;
            color: #667eea;
        }}

        .summary-card-content {{
            color: #e0e0e0;
            line-height: 1.6;
            font-size: 0.95em;
        }}

        /* Charts Section Styles */
        .charts-section {{
            background: rgba(37, 47, 78, 0.6);
            border-radius: 16px;
            padding: 30px;
            margin-bottom: 40px;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }}

        .charts-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 30px;
            margin-top: 25px;
        }}

        .chart-container {{
            background: rgba(0, 0, 0, 0.2);
            border-radius: 12px;
            padding: 20px;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }}

        .chart-title {{
            font-size: 1.1em;
            font-weight: 600;
            color: #667eea;
            margin-bottom: 15px;
            text-align: center;
        }}

        .chart-canvas {{
            max-height: 250px;
        }}

        /* Key Specs Badge Styles */
        .key-specs {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 12px;
        }}

        .key-spec-badge {{
            display: inline-flex;
            align-items: center;
            gap: 5px;
            background: rgba(102, 126, 234, 0.2);
            border: 1px solid rgba(102, 126, 234, 0.4);
            border-radius: 6px;
            padding: 6px 12px;
            font-size: 0.85em;
            font-weight: 600;
            color: #ffffff;
        }}

        .key-spec-badge .spec-icon {{
            font-size: 1.1em;
        }}

        .key-spec-badge .spec-value {{
            color: #667eea;
        }}

        /* [FIX B.4] 缺失值样式 - 区分不同状态 */
        .key-spec-badge.spec-missing {{
            background: rgba(107, 114, 128, 0.2);
            border: 1px solid rgba(107, 114, 128, 0.4);
        }}
        .key-spec-badge.spec-missing .spec-value {{
            color: #9ca3af;
        }}

        .key-spec-badge.spec-undisclosed {{
            background: rgba(139, 92, 246, 0.2);
            border: 1px solid rgba(139, 92, 246, 0.4);
        }}
        .key-spec-badge.spec-undisclosed .spec-value {{
            color: #a78bfa;
        }}

        .key-spec-badge.spec-pending {{
            background: rgba(251, 191, 36, 0.2);
            border: 1px solid rgba(251, 191, 36, 0.4);
        }}
        .key-spec-badge.spec-pending .spec-value {{
            color: #fbbf24;
        }}

        .key-spec-badge.spec-estimated {{
            background: rgba(249, 115, 22, 0.2);
            border: 1px solid rgba(249, 115, 22, 0.4);
        }}
        .key-spec-badge.spec-estimated .spec-value {{
            color: #fb923c;
        }}

        /* [FIX E] 二次补全样式 - 区分补全/推断 */
        .key-spec-badge.spec-enriched {{
            background: rgba(16, 185, 129, 0.2);
            border: 1px solid rgba(16, 185, 129, 0.4);
            position: relative;
        }}
        .key-spec-badge.spec-enriched .spec-value {{
            color: #34d399;
        }}
        .key-spec-badge.spec-enriched::after {{
            content: '✓补全';
            font-size: 0.7em;
            margin-left: 6px;
            padding: 2px 6px;
            background: rgba(16, 185, 129, 0.3);
            border-radius: 3px;
            color: #34d399;
        }}

        .key-spec-badge.spec-inferred {{
            background: rgba(251, 146, 60, 0.2);
            border: 1px solid rgba(251, 146, 60, 0.4);
            position: relative;
        }}
        .key-spec-badge.spec-inferred .spec-value {{
            color: #fb923c;
        }}
        .key-spec-badge.spec-inferred::after {{
            content: '推断';
            font-size: 0.7em;
            margin-left: 6px;
            padding: 2px 6px;
            background: rgba(251, 146, 60, 0.3);
            border-radius: 3px;
            color: #fb923c;
        }}

        /* 证据片段 tooltip */
        .evidence-tooltip {{
            position: relative;
            cursor: help;
        }}
        .evidence-tooltip:hover::before {{
            content: attr(data-evidence);
            position: absolute;
            bottom: 100%;
            left: 50%;
            transform: translateX(-50%);
            background: rgba(30, 41, 59, 0.95);
            border: 1px solid rgba(102, 126, 234, 0.5);
            border-radius: 8px;
            padding: 10px 14px;
            font-size: 0.85em;
            color: #e0e0e0;
            white-space: pre-wrap;
            max-width: 350px;
            z-index: 1000;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
            margin-bottom: 8px;
        }}
        .evidence-tooltip:hover::after {{
            content: '';
            position: absolute;
            bottom: 100%;
            left: 50%;
            transform: translateX(-50%);
            border: 6px solid transparent;
            border-top-color: rgba(30, 41, 59, 0.95);
            border-bottom: none;
            margin-bottom: -4px;
        }}

        /* Price Status Badge */
        .price-status {{
            display: inline-block;
            padding: 4px 10px;
            border-radius: 4px;
            font-size: 0.75em;
            font-weight: 600;
            margin-left: 8px;
            vertical-align: middle;
        }}

        .price-status.missing {{
            background: rgba(107, 114, 128, 0.2);
            border: 1px solid rgba(107, 114, 128, 0.5);
            color: #9ca3af;
        }}

        .price-status.undisclosed {{
            background: rgba(139, 92, 246, 0.2);
            border: 1px solid rgba(139, 92, 246, 0.5);
            color: #a78bfa;
        }}

        .price-status.pending {{
            background: rgba(251, 191, 36, 0.2);
            border: 1px solid rgba(251, 191, 36, 0.5);
            color: #fbbf24;
        }}

        .price-status.estimated {{
            background: rgba(249, 115, 22, 0.2);
            border: 1px solid rgba(249, 115, 22, 0.5);
            color: #fb923c;
        }}

        .price-status.unknown {{
            background: rgba(107, 114, 128, 0.2);
            border: 1px solid rgba(107, 114, 128, 0.5);
            color: #9ca3af;
        }}

        .section {{
            margin-bottom: 50px;
        }}

        .section-title {{
            font-size: 2em;
            margin-bottom: 30px;
            color: #ffffff;
            border-left: 5px solid #667eea;
            padding-left: 15px;
            background: linear-gradient(90deg, rgba(102, 126, 234, 0.2) 0%, transparent 100%);
            padding: 15px;
            border-radius: 0 8px 8px 0;
        }}

        .products-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(900px, 1fr));
            gap: 30px;
            max-width: 100%;
            overflow: hidden;
        }}

        .product-card {{
            background: #252f4e;
            border-radius: 16px;
            overflow: hidden;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
            border: 1px solid rgba(255, 255, 255, 0.1);
            display: grid;
            grid-template-columns: 300px 1fr 1fr;
            transition: transform 0.3s, box-shadow 0.3s;
            position: relative;
        }}

        .product-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 12px 40px rgba(102, 126, 234, 0.3);
            border-color: rgba(102, 126, 234, 0.5);
        }}

        .product-card.hidden {{
            display: none;
        }}

        .no-results {{
            text-align: center;
            padding: 60px 20px;
            color: #718096;
            font-size: 1.2em;
        }}

        /* 来源 Badge */
        .source-badge {{
            position: absolute;
            top: 15px;
            right: 15px;
            padding: 6px 12px;
            border-radius: 20px;
            font-size: 0.75em;
            font-weight: 600;
            z-index: 10;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}

        .source-badge.inwaishe {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            box-shadow: 0 2px 8px rgba(102, 126, 234, 0.4);
        }}

        .source-badge.wstx {{
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            color: white;
            box-shadow: 0 2px 8px rgba(245, 87, 108, 0.4);
        }}

        .source-badge.both {{
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
            color: white;
            box-shadow: 0 2px 8px rgba(79, 172, 254, 0.4);
        }}

        /* 产品概览区块 */
        .product-overview {{
            padding: 25px;
            background: rgba(0, 0, 0, 0.2);
            border-right: 1px solid rgba(255, 255, 255, 0.1);
            position: relative;
        }}

        .product-image {{
            width: 100%;
            height: 200px;
            background: linear-gradient(135deg, rgba(102, 126, 234, 0.1) 0%, rgba(118, 75, 162, 0.1) 100%);
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            margin-bottom: 20px;
            overflow: hidden;
            position: relative;
            cursor: pointer;
        }}

        .product-image img {{
            max-width: 90%;
            max-height: 90%;
            object-fit: contain;
            transition: transform 0.3s;
        }}

        .product-image:hover img {{
            transform: scale(1.05);
        }}

        .product-name {{
            font-size: 1.2em;
            font-weight: 700;
            color: #ffffff;
            margin-bottom: 15px;
            line-height: 1.4;
        }}

        .product-price {{
            font-size: 2em;
            font-weight: 700;
            color: #e74c3c;
            margin-bottom: 10px;
        }}

        .product-date {{
            font-size: 0.85em;
            color: #a0aec0;
        }}

        /* 硬核参数区块 */
        .product-specs {{
            padding: 25px;
            border-right: 1px solid rgba(255, 255, 255, 0.1);
        }}

        .block-title {{
            font-size: 1.1em;
            font-weight: 600;
            color: #667eea;
            margin-bottom: 15px;
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        .block-title::before {{
            content: '';
            width: 4px;
            height: 18px;
            background: #667eea;
            border-radius: 2px;
        }}

        .specs-list {{
            display: flex;
            flex-direction: column;
            gap: 10px;
        }}

        .spec-item {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 8px 12px;
            background: rgba(0, 0, 0, 0.2);
            border-radius: 6px;
        }}

        .spec-label {{
            color: #a0aec0;
            font-size: 0.9em;
        }}

        .spec-value {{
            color: #ffffff;
            font-weight: 600;
            font-size: 0.95em;
        }}

        .no-specs {{
            color: #718096;
            font-style: italic;
            text-align: center;
            padding: 20px;
        }}

        /* PM 洞察区块 */
        .product-analysis {{
            padding: 25px;
            background: rgba(0, 0, 0, 0.1);
        }}

        /* 自适应布局：没有参数时，PM 洞察占满 */
        .product-card.no-specs {{
            grid-template-columns: 300px 1fr;
        }}

        .product-card.no-specs .product-overview {{
            border-right: 1px solid rgba(255, 255, 255, 0.1);
        }}

        .product-card.no-specs .product-analysis {{
            border-right: none;
        }}

        /* PM 洞察为空时的缺省状态 */
        .empty-analysis {{
            text-align: center;
            padding: 40px 20px;
            color: #718096;
        }}

        .empty-analysis-icon {{
            font-size: 3em;
            margin-bottom: 15px;
            opacity: 0.5;
        }}

        .empty-analysis-text {{
            font-size: 0.95em;
        }}

        .analysis-section {{
            margin-bottom: 20px;
        }}

        .analysis-section:last-child {{
            margin-bottom: 0;
        }}

        .analysis-label {{
            font-size: 0.8em;
            color: #667eea;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 8px;
            font-weight: 600;
        }}

        .analysis-text {{
            color: #e0e0e0;
            font-size: 0.95em;
            line-height: 1.5;
        }}

        .verdict-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
            margin-top: 15px;
        }}

        .verdict-box {{
            padding: 15px;
            border-radius: 8px;
        }}

        .verdict-box.pros {{
            background: rgba(72, 187, 120, 0.15);
            border: 1px solid rgba(72, 187, 120, 0.3);
        }}

        .verdict-box.cons {{
            background: rgba(245, 101, 101, 0.15);
            border: 1px solid rgba(245, 101, 101, 0.3);
        }}

        .verdict-title {{
            font-size: 0.85em;
            font-weight: 600;
            margin-bottom: 10px;
            display: flex;
            align-items: center;
            gap: 6px;
        }}

        .verdict-title.pros {{
            color: #48bb78;
        }}

        .verdict-title.cons {{
            color: #f56565;
        }}

        .verdict-list {{
            list-style: none;
            padding: 0;
            margin: 0;
        }}

        .verdict-list li {{
            font-size: 0.9em;
            padding: 4px 0;
            padding-left: 20px;
            position: relative;
            color: #cbd5e0;
            margin-bottom: 6px;
        }}

        .verdict-list li:last-child {{
            margin-bottom: 0;
        }}

        .verdict-list.pros li::before {{
            content: '✓';
            position: absolute;
            left: 0;
            color: #48bb78;
            font-weight: bold;
        }}

        .verdict-list.cons li::before {{
            content: '✗';
            position: absolute;
            left: 0;
            color: #f56565;
            font-weight: bold;
        }}

        .pm-summary {{
            background: linear-gradient(135deg, rgba(102, 126, 234, 0.2) 0%, rgba(118, 75, 162, 0.2) 100%);
            border-left: 4px solid #667eea;
            padding: 15px;
            border-radius: 0 8px 8px 0;
            margin-top: 15px;
        }}

        .pm-summary-text {{
            color: #ffffff;
            font-size: 0.95em;
            font-style: italic;
            line-height: 1.6;
        }}

        .source-links {{
            margin-top: 20px;
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
        }}

        .source-link {{
            font-size: 0.8em;
            color: #667eea;
            text-decoration: none;
            padding: 6px 12px;
            border: 1px solid rgba(102, 126, 234, 0.5);
            border-radius: 4px;
            transition: all 0.3s;
        }}

        .source-link:hover {{
            background: rgba(102, 126, 234, 0.2);
            border-color: #667eea;
        }}

        .footer {{
            text-align: center;
            padding: 30px;
            color: #718096;
            font-size: 0.9em;
            border-top: 1px solid rgba(255, 255, 255, 0.1);
            margin-top: 50px;
        }}

        /* 回到顶部按钮 */
        .back-to-top {{
            position: fixed;
            bottom: 30px;
            right: 30px;
            width: 50px;
            height: 50px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            opacity: 0;
            visibility: hidden;
            transition: all 0.3s;
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
            z-index: 999;
            font-size: 1.5em;
            color: white;
        }}

        .back-to-top.visible {{
            opacity: 1;
            visibility: visible;
        }}

        .back-to-top:hover {{
            transform: translateY(-5px);
            box-shadow: 0 6px 20px rgba(102, 126, 234, 0.6);
        }}

        /* Lightbox 图片预览 */
        .lightbox {{
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.95);
            display: none;
            align-items: center;
            justify-content: center;
            z-index: 10000;
            cursor: zoom-out;
        }}

        .lightbox.active {{
            display: flex;
        }}

        .lightbox img {{
            max-width: 90%;
            max-height: 90%;
            object-fit: contain;
            border-radius: 8px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
        }}

        .lightbox-close {{
            position: absolute;
            top: 30px;
            right: 30px;
            font-size: 2em;
            color: white;
            cursor: pointer;
            transition: transform 0.3s;
        }}

        .lightbox-close:hover {{
            transform: rotate(90deg);
        }}

        // [FIX] 响应式断点：添加更多移动端适配
        @media (max-width: 1400px) {{
            .container {{
                max-width: 1200px;
                padding: 15px;
            }}
        }}

        @media (max-width: 1200px) {{
            .products-grid {{
                grid-template-columns: 1fr;
            }}

            .product-card {{
                grid-template-columns: 1fr;
            }}

            .product-overview {{
                border-right: none;
                border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            }}

            .product-specs {{
                border-right: none;
                border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            }}
        }}

        @media (max-width: 900px) {{
            .container {{
                max-width: 100%;
                padding: 10px;
            }}

            .header h1 {{
                font-size: 2em;
            }}

            .stats {{
                gap: 15px;
            }}

            .stat-item {{
                padding: 15px 20px;
                min-width: 120px;
            }}
        }}

        @media (max-width: 768px) {{
            .header h1 {{
                font-size: 1.8em;
            }}

            .stats {{
                flex-direction: column;
            }}

            .verdict-grid {{
                grid-template-columns: 1fr;
            }}

            .nav-bar {{
                flex-direction: column;
                align-items: stretch;
            }}

            .search-box {{
                max-width: none;
            }}
        }}

        @media (max-width: 600px) {{
            .header h1 {{
                font-size: 1.5em;
            }}

            .header .subtitle {{
                font-size: 1em;
            }}

            .section-title {{
                font-size: 1.3em;
            }}

            .charts-grid {{
                grid-template-columns: 1fr;
            }}
        }}

        @media (max-width: 480px) {{
            body {{
                padding: 10px;
            }}

            .header {{
                padding: 20px 10px;
            }}

            .nav-btn {{
                padding: 8px 15px;
                font-size: 0.9em;
            }}

            .product-card {{
                border-radius: 12px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- 导航栏 -->
        <div class="nav-bar">
            <div class="nav-buttons">
                <a href="#mice" class="nav-btn">🖱️ 鼠标 ({len(self.mice)})</a>
                <a href="#keyboards" class="nav-btn">⌨️ 键盘 ({len(self.keyboards)})</a>
                <a href="#others" class="nav-btn">📦 其他 ({len(self.others)})</a>
            </div>
            <div class="search-box">
                <input type="text" class="search-input" id="searchInput" placeholder="搜索产品名称或品牌...">
                <span class="search-icon">🔍</span>
            </div>
        </div>

        <!-- 头部 -->
        <div class="header">
            <h1>{TARGET_YEAR}年{TARGET_MONTH}月外设新品监控报告</h1>
            <div class="subtitle">PM 深度分析版 | 外设天下 × in外设 新品汇总</div>
            <div class="stats">
                <div class="stat-item">
                    <div class="stat-number">{len(self.products)}</div>
                    <div class="stat-label">总产品数</div>
                </div>
                <div class="stat-item">
                    <div class="stat-number">{len(self.mice)}</div>
                    <div class="stat-label">鼠标新品</div>
                </div>
                <div class="stat-item">
                    <div class="stat-number">{len(self.keyboards)}</div>
                    <div class="stat-label">键盘新品</div>
                </div>
            </div>
        </div>

        <!-- 月度市场风向标 -->
        {self._render_executive_summary()}

        <!-- 宏观数据仪表盘 -->
        {self._render_charts()}

        <!-- 鼠标新品 -->
        {self._render_section('鼠标', self.mice, 'mice')}

        <!-- 键盘新品 -->
        {self._render_section('键盘', self.keyboards, 'keyboards')}

        <!-- 其他产品 -->
        {self._render_section('其他', self.others, 'others')}

        <!-- 尾部 -->
        <div class="footer">
            <p>报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <p>数据来源: in外设 (inwaishe.com) & 外设天下 (wstx.com) | PM 深度分析由 LLM 生成</p>
        </div>
    </div>

    <!-- 回到顶部按钮 -->
    <div class="back-to-top" id="backToTop" title="回到顶部">↑</div>

    <!-- Lightbox 图片预览 -->
    <div class="lightbox" id="lightbox">
        <span class="lightbox-close">×</span>
        <img src="" alt="产品图片预览" id="lightboxImg">
    </div>

    <script>
        // 搜索功能
        const searchInput = document.getElementById('searchInput');
        const productCards = document.querySelectorAll('.product-card');

        searchInput.addEventListener('input', function(e) {{
            const searchTerm = e.target.value.toLowerCase().trim();

            productCards.forEach(card => {{
                const productName = card.querySelector('.product-name')?.textContent.toLowerCase() || '';
                const productPrice = card.querySelector('.product-price')?.textContent.toLowerCase() || '';
                const productSource = card.querySelector('.source-badge')?.textContent.toLowerCase() || '';

                const matches = productName.includes(searchTerm) ||
                              productPrice.includes(searchTerm) ||
                              productSource.includes(searchTerm);

                if (matches || searchTerm === '') {{
                    card.classList.remove('hidden');
                }} else {{
                    card.classList.add('hidden');
                }}
            }});

            // 检查是否有可见卡片
            const visibleCards = document.querySelectorAll('.product-card:not(.hidden)');
            const sections = document.querySelectorAll('.section');

            sections.forEach(section => {{
                const cardsInSection = section.querySelectorAll('.product-card:not(.hidden)');
                if (cardsInSection.length === 0) {{
                    section.style.display = 'none';
                }} else {{
                    section.style.display = 'block';
                }}
            }});
        }});

        // 回到顶部按钮
        const backToTop = document.getElementById('backToTop');

        window.addEventListener('scroll', function() {{
            if (window.pageYOffset > 300) {{
                backToTop.classList.add('visible');
            }} else {{
                backToTop.classList.remove('visible');
            }}
        }});

        backToTop.addEventListener('click', function() {{
            window.scrollTo({{
                top: 0,
                behavior: 'smooth'
            }});
        }});

        // Lightbox 图片预览
        const lightbox = document.getElementById('lightbox');
        const lightboxImg = document.getElementById('lightboxImg');
        const productImages = document.querySelectorAll('.product-image img');

        productImages.forEach(img => {{
            img.addEventListener('click', function() {{
                const src = this.getAttribute('src');
                if (src && !src.includes('unsplash.com')) {{
                    lightboxImg.src = src;
                    lightbox.classList.add('active');
                }}
            }});
        }});

        lightbox.addEventListener('click', function() {{
            lightbox.classList.remove('active');
        }});

        // ESC 关闭 Lightbox
        document.addEventListener('keydown', function(e) {{
            if (e.key === 'Escape') {{
                lightbox.classList.remove('active');
            }}
        }});
    </script>
</body>
</html>"""

    def _render_executive_summary(self) -> str:
        """渲染月度市场风向标"""
        tech_trends = self.market_analyzer.analyze_tech_trends()
        pricing_insights = self.market_analyzer.analyze_pricing_insights()
        pm_takeaways = self.market_analyzer.generate_pm_takeaways()

        return f"""
        <div class="executive-summary">
            <h2 class="summary-title">📊 月度市场风向标</h2>
            <div class="summary-grid">
                <div class="summary-card">
                    <div class="summary-card-header">
                        <span class="summary-card-icon">🔬</span>
                        <span class="summary-card-title">技术趋势</span>
                    </div>
                    <div class="summary-card-content">{tech_trends}</div>
                </div>
                <div class="summary-card">
                    <div class="summary-card-header">
                        <span class="summary-card-icon">💰</span>
                        <span class="summary-card-title">价格行情</span>
                    </div>
                    <div class="summary-card-content">{pricing_insights}</div>
                </div>
                <div class="summary-card">
                    <div class="summary-card-header">
                        <span class="summary-card-icon">🎯</span>
                        <span class="summary-card-title">PM 启示录</span>
                    </div>
                    <div class="summary-card-content">{pm_takeaways}</div>
                </div>
            </div>
        </div>"""

    def _render_charts(self) -> str:
        """渲染宏观数据仪表盘"""
        chart_data = self.market_analyzer.get_chart_data()

        # Prepare chart data JSON
        import json
        category_labels = json.dumps(chart_data['category']['labels'])
        category_data = json.dumps(chart_data['category']['data'])

        sensor_labels = json.dumps(list(chart_data['sensor'].keys()))
        sensor_data = json.dumps(list(chart_data['sensor'].values()))

        price_labels = json.dumps(list(chart_data['price_range'].keys()))
        price_data = json.dumps(list(chart_data['price_range'].values()))

        # 获取覆盖率统计
        sensor_coverage = chart_data['coverage']['sensor']
        price_coverage = chart_data['coverage']['price']

        sensor_title = f"鼠标传感器分布 ({sensor_coverage['known']}/{sensor_coverage['total']})"
        # [FIX C.3] 价格标题写清楚样本量："已公开 X/Y"
        price_title = f"价格区间分布（已公开 {price_coverage['known']}/{price_coverage['total']}）"

        return f"""
        <div class="charts-section">
            <h2 class="section-title">📈 宏观数据仪表盘</h2>
            <div class="charts-grid">
                <div class="chart-container">
                    <div class="chart-title">品类占比分布</div>
                    <canvas id="categoryChart" class="chart-canvas"></canvas>
                </div>
                <div class="chart-container">
                    <div class="chart-title">{sensor_title}</div>
                    <canvas id="sensorChart" class="chart-canvas"></canvas>
                </div>
                <div class="chart-container">
                    <div class="chart-title">{price_title}</div>
                    <canvas id="priceChart" class="chart-canvas"></canvas>
                </div>
            </div>
        </div>

        <script>
            // Chart.js global config
            Chart.defaults.color = '#a0aec0';
            Chart.defaults.borderColor = 'rgba(255, 255, 255, 0.1)';

            // Category Pie Chart
            new Chart(document.getElementById('categoryChart'), {{
                type: 'pie',
                data: {{
                    labels: {category_labels},
                    datasets: [{{
                        data: {category_data},
                        backgroundColor: [
                            'rgba(102, 126, 234, 0.8)',
                            'rgba(118, 75, 162, 0.8)',
                            'rgba(245, 101, 101, 0.8)'
                        ],
                        borderWidth: 2,
                        borderColor: 'rgba(0, 0, 0, 0.3)'
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: true,
                    plugins: {{
                        legend: {{
                            position: 'bottom',
                            labels: {{
                                padding: 15,
                                font: {{ size: 12 }}
                            }}
                        }}
                    }}
                }}
            }});

            // Sensor Doughnut Chart
            const sensorLabels = {sensor_labels};
            // [FIX] 动态生成颜色数组，确保长度匹配
            const sensorColors = sensorLabels.map((_, i) => {{
                const colors = [
                    'rgba(72, 187, 120, 0.8)',
                    'rgba(245, 158, 11, 0.8)',
                    'rgba(66, 153, 225, 0.8)',
                    'rgba(159, 122, 234, 0.8)',
                    'rgba(236, 72, 153, 0.8)',
                    'rgba(20, 184, 166, 0.8)',
                    'rgba(102, 126, 234, 0.8)',
                    'rgba(245, 101, 101, 0.8)',
                    'rgba(46, 213, 115, 0.8)',
                    'rgba(237, 137, 54, 0.8)'
                ];
                return colors[i % colors.length];
            }});

            new Chart(document.getElementById('sensorChart'), {{
                type: 'doughnut',
                data: {{
                    labels: {sensor_labels},
                    datasets: [{{
                        data: {sensor_data},
                        backgroundColor: sensorColors,
                        borderWidth: 2,
                        borderColor: 'rgba(0, 0, 0, 0.3)'
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: true,
                    plugins: {{
                        legend: {{
                            position: 'bottom',
                            labels: {{
                                padding: 15,
                                font: {{ size: 11 }}
                            }}
                        }}
                    }}
                }}
            }});

            // Price Range Bar Chart
            new Chart(document.getElementById('priceChart'), {{
                type: 'bar',
                data: {{
                    labels: {price_labels},
                    datasets: [{{
                        label: '产品数量',
                        data: {price_data},
                        backgroundColor: 'rgba(102, 126, 234, 0.8)',
                        borderColor: 'rgba(102, 126, 234, 1)',
                        borderWidth: 2,
                        borderRadius: 8
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: true,
                    scales: {{
                        y: {{
                            beginAtZero: true,
                            ticks: {{
                                stepSize: 1
                            }}
                        }}
                    }},
                    plugins: {{
                        legend: {{
                            display: false
                        }}
                    }}
                }}
            }});
        </script>"""

    def _render_section(self, title: str, products: List[Dict], anchor_id: str) -> str:
        """渲染产品区块"""
        if not products:
            return ""

        cards = '\n'.join([self._render_card(p) for p in products])

        return f"""
        <div class="section" id="{anchor_id}">
            <h2 class="section-title">{title}新品 ({len(products)})</h2>
            <div class="products-grid">
                {cards}
            </div>
        </div>"""

    def _render_key_specs(self, product: Dict) -> str:
        """渲染Top 3核心参数（带图标）- 使用 Top 15 Schema 字段"""
        category = product.get('category', '')
        specs = product.get('specs', {})

        if category == '鼠标':
            # 鼠标Top 3: 使用 Top 15 Schema 字段
            key_specs = [
                ('⚖️', 'weight_center', '重量'),
                ('🖱️', 'sensor_solution', '传感器'),
                ('⚡', 'polling_rate', '回报率')
            ]
        elif category == '键盘':
            # 键盘Top 3: 使用 Top 15 Schema 字段
            key_specs = [
                ('⌨️', 'structure_form', '结构'),
                ('🔌', 'connection_storage', '连接'),
                ('🔘', 'switch_details', '轴体')
            ]
        else:
            return ''

        badges = []
        for icon, spec_key, label in key_specs:
            value = specs.get(spec_key, '')
            value_str = str(value).strip() if value else ''

            # [FIX B.4] 缺失值显示逻辑重构：不再隐藏缺失值
            if not value_str:
                # 空值 → 显示"未提及"
                display_value = '未提及'
                badge_class = 'spec-missing'
            elif any(marker in value_str.lower() for marker in [
                '未提及', '原文未提及', '未提供', '未知', 'unknown', 'none', 'null'
            ]):
                # 未提及类
                display_value = '未提及'
                badge_class = 'spec-missing'
            elif any(marker in value_str.lower() for marker in [
                '未公开', '厂商未公开', 'tbd', '待公布'
            ]):
                # 未公开类
                display_value = '未公开'
                badge_class = 'spec-undisclosed'
            elif any(marker in value_str.lower() for marker in [
                '待实测', '待官方实测', '实测中'
            ]):
                # 待实测类
                display_value = '待实测'
                badge_class = 'spec-pending'
            elif any(marker in value_str.lower() for marker in [
                '预估', '推断', '推测', '可能'
            ]):
                # 预估类
                display_value = f'{value} (预估)'
                badge_class = 'spec-estimated'
            else:
                # 正常值处理
                display_value = value
                badge_class = ''

                # 简化值显示（去除冗余信息）
                if spec_key == 'weight_center' and 'g' in str(value):
                    display_value = str(value).replace('g', '').strip() + 'g'
                elif spec_key == 'polling_rate' and 'Hz' in str(value):
                    display_value = str(value).replace('Hz', '').replace('hz', '').strip() + 'Hz'

            # [FIX E] 检查二次补全状态 - 优先级高于默认判定
            enrichment = product.get('enrichment', {})
            field_status = enrichment.get('field_status', {})
            evidence = enrichment.get('evidence', {})

            # 如果字段被补全，覆盖 badge_class
            if spec_key in field_status:
                status = field_status[spec_key]
                if status == 'enriched':
                    badge_class = 'spec-enriched'
                elif status == 'inferred':
                    badge_class = 'spec-inferred'

            # 构建 badge HTML
            evidence_attr = ''
            wrapper_class = ''

            # 如果有证据片段，添加 tooltip
            if spec_key in evidence:
                evidence_data = evidence[spec_key]
                snippet = evidence_data.get('snippet', '')
                method = evidence_data.get('method', 'unknown')
                source = evidence_data.get('source', 'local')
                if snippet:
                    evidence_attr = f' data-evidence="📋 证据片段 ({method}提取，{source}源):\n{snippet}"'
                    wrapper_class = 'evidence-tooltip'

            if badge_class:
                badge_html = f'<span class="key-spec-badge {badge_class}{f" {wrapper_class}" if wrapper_class else ""}"{evidence_attr}><span class="spec-icon">{icon}</span>{label}: <span class="spec-value">{display_value}</span></span>'
            else:
                badge_html = f'<span class="key-spec-badge{f" {wrapper_class}" if wrapper_class else ""}"{evidence_attr}><span class="spec-icon">{icon}</span>{label}: <span class="spec-value">{display_value}</span></span>'
            badges.append(badge_html)

        return f'<div class="key-specs">{"".join(badges)}</div>' if badges else ''

    def _get_price_status(self, price: str) -> tuple:
        """获取价格和状态标签 - [FIX C.2] 禁止叠加，只展示一种 status"""
        if not price or not price.strip():
            return ('未提及', 'missing')
        elif price == '价格未公开':
            return ('未公开', 'undisclosed')

        price_lower = price.lower().strip()

        # [FIX C.2] 优先级：未公开 > 未提及 > 待实测 > 预估 > 正常
        if any(marker in price_lower for marker in ['未公开', '厂商未公开', 'tbd', '待公布']):
            return ('未公开', 'undisclosed')
        elif any(marker in price_lower for marker in ['未提及', '原文未提及', '未提供']):
            return ('未提及', 'missing')
        elif any(marker in price_lower for marker in ['待实测', '待官方实测', '实测中']):
            return ('待实测', 'pending')
        elif any(marker in price_lower for marker in ['预估', '推断', '推测']):
            return (price, 'estimated')  # 保留原始值但标记为预估
        else:
            return (price, 'normal')  # 正常价格

    @staticmethod
    def _standardize_price(price_str: str, product_name: str = '') -> str:
        """
        标准化价格显示，处理外币转换和格式统一

        Args:
            price_str: 原始价格字符串
            product_name: 产品名称（用于推断价格区间）

        Returns:
            标准化后的价格字符串
        """
        import re

        if not price_str or price_str == '价格未公开':
            return '价格未公开'

        price_str = str(price_str).strip()

        # 汇率（简化版，2025年参考）
        exchange_rates = {
            'USD': 7.2,    # 1美元 = 7.2人民币
            '$': 7.2,
            'JPY': 0.048,  # 1日元 = 0.048人民币
            '¥': 0.048,    # 日元符号（需要上下文判断）
            'EUR': 7.8,    # 1欧元 = 7.8人民币
            '€': 7.8,
            'HKD': 0.92,   # 1港币 = 0.92人民币
            'TWD': 0.23    # 1台币 = 0.23人民币
        }

        # 提取数字和货币符号
        # 匹配：19980日元、$99、99USD、199元等
        patterns = [
            r'(\d+(?:\.\d+)?)\s*(日元|JPY|¥)\s*',  # 日元
            r'[\$](\d+(?:\.\d+)?)',                 # 美元
            r'(\d+(?:\.\d+)?)\s*(USD|EUR|€|HKD|TWD)\s*',  # 其他外币
            r'(\d+)\s*(?:元|圆|RMB|CNY)\s*',        # 人民币
            r'约\s*(\d+)\s*元'                      # "约XXX元"
        ]

        for pattern in patterns[:1]:  # 先处理日元
            match = re.search(pattern, price_str, re.IGNORECASE)
            if match:
                amount = float(match.group(1))
                currency = match.group(2) if len(match.groups()) > 1 else 'JPY'

                # 日元转换
                if currency in ['日元', 'JPY', '¥']:
                    # 判断是否是日元价格（通常日元价格数字较大）
                    if amount > 1000:  # 日元价格通常>1000
                        cny_price = amount * exchange_rates['JPY']
                        return f'约{int(cny_price)}元（原价{int(amount)}日元）'

        # 处理美元
        usd_match = re.search(r'\$(\d+(?:\.\d+)?)', price_str)
        if usd_match:
            amount = float(usd_match.group(1))
            cny_price = amount * exchange_rates['$']
            return f'约{int(cny_price)}元（原价${amount}）'

        # 处理欧元
        eur_match = re.search(r'(?:€|EUR)\s*(\d+(?:\.\d+)?)', price_str, re.IGNORECASE)
        if eur_match:
            amount = float(eur_match.group(1))
            cny_price = amount * exchange_rates['EUR']
            return f'约{int(cny_price)}元（原价€{amount}）'

        # 提取人民币数字
        cny_match = re.search(r'(\d+)\s*(?:元|圆|CNY|RMB|约)', price_str)
        if cny_match:
            amount = int(cny_match.group(1))
            if '预估' in price_str or '约' in price_str:
                return f'{amount}元（预估）'
            return f'{amount}元'

        # 如果是纯数字，补充单位
        digits_match = re.search(r'^(\d+)$', price_str.strip())
        if digits_match:
            amount = int(digits_match.group(1))
            if amount < 200:
                return f'{amount}元（预估）'
            return f'{amount}元'

        # 原样返回
        return price_str

    def _render_card(self, product: Dict) -> str:
        """渲染单个产品卡片 - 三栏布局"""
        # 获取原始数据
        raw_data = product.get('_raw', product)
        records = raw_data.get('records', []) if isinstance(raw_data, dict) else []

        # 获取主图 - 使用多层fallback逻辑
        main_image = product.get('main_image', '')

        # Fallback 1: 如果main_image为空，尝试从_raw.images获取第一张
        if not main_image and isinstance(raw_data, dict):
            raw_images = raw_data.get('images', [])
            if raw_images and len(raw_images) > 0:
                main_image = raw_images[0]

        # Fallback 2: 如果还是为空，尝试从records中查找第一张有图片的记录
        if not main_image and records:
            for record in records:
                if isinstance(record, dict):
                    record_images = record.get('images', [])
                    # 处理字符串形式的列表
                    if isinstance(record_images, str) and record_images not in ['[]', 'nan', '']:
                        try:
                            import ast
                            parsed = ast.literal_eval(record_images)
                            if isinstance(parsed, list) and len(parsed) > 0:
                                record_images = parsed
                        except:
                            pass
                    # 确保record_images是列表且不为空
                    if isinstance(record_images, list) and len(record_images) > 0:
                        first_img = record_images[0]
                        # 验证第一个元素是有效的URL字符串
                        if isinstance(first_img, str) and first_img and first_img not in ['[', ']']:
                            main_image = first_img
                            break

        image_html = self._render_image(main_image, product.get('category', ''))

        # 渲染硬核参数
        specs = product.get('specs', {})
        # 检查是否有有效参数（排除"暂无数据"、"待实测"等无效值）
        has_specs = self._has_valid_specs(specs)

        # 渲染 PM 深度洞察（传入 product 以显示创新标签）
        analysis_html = self._render_analysis(product.get('analysis', {}), has_specs, product)

        # 获取发布日期
        publish_date = records[0].get('publish_date', '') if records else ''
        date_html = f'<div class="product-date">发布时间: {publish_date[:10]}</div>' if publish_date else ''

        # 渲染来源链接
        links_html = self._render_links(records)

        # 渲染来源 Badge
        sources = raw_data.get('sources', []) if isinstance(raw_data, dict) else []
        badge_html = self._render_source_badge(sources)

        # 判断卡片样式类
        card_classes = ['product-card']
        if not has_specs:
            card_classes.append('no-specs')

        # 渲染Top 3核心参数
        key_specs_html = self._render_key_specs(product)

        # 获取价格和状态
        price = product.get('release_price', '')
        display_price, price_status = self._get_price_status(price)

        # [FIX C.2] 构建价格HTML（带状态标签）- 更新状态文本映射
        price_html = f'<div class="product-price">{display_price}'
        if price_status and price_status != 'normal':
            # 状态文本映射
            status_text_map = {
                'missing': '未提及',
                'undisclosed': '未公开',
                'pending': '待实测',
                'estimated': '预估'
            }
            status_text = status_text_map.get(price_status, price_status)
            price_html += f' <span class="price-status {price_status}">{status_text}</span>'
        price_html += '</div>'

        return f"""
        <div class="{' '.join(card_classes)}">
            {badge_html}
            <!-- 左栏：产品概览 -->
            <div class="product-overview">
                {image_html}
                <div class="product-name">{product.get('product_name', '未知产品')}</div>
                {price_html}
                {key_specs_html}
                {date_html}
                {links_html}
            </div>

            <!-- 中栏：硬核参数（如果有）-->
            {f'''<div class="product-specs">
                <div class="block-title">硬核参数</div>
                {self._render_specs(specs, product.get('data_sources'), product.get('category', ''))}
            </div>''' if has_specs else ''}

            <!-- 右栏：PM 深度洞察 -->
            <div class="product-analysis">
                <div class="block-title">PM 深度洞察</div>
                {analysis_html}
            </div>
        </div>
    </div>"""

    def _render_image(self, image_url: str, category: str) -> str:
        """渲染产品图片 - 使用科技感占位图 + lazy loading"""
        # 使用默认科技感占位图
        final_image = image_url if image_url else DEFAULT_IMAGE_URL

        # 将 http://www.inwaishe.com 的图片 URL 转换为 https://
        if final_image and final_image.startswith('http://www.inwaishe.com'):
            final_image = final_image.replace('http://', 'https://', 1)

        return f'''<div class="product-image" title="点击放大预览">
                <img src="{final_image}" alt="产品图片" loading="lazy" onerror="this.src='{DEFAULT_IMAGE_URL}'">
            </div>'''

    def _render_specs(self, specs: Dict, data_sources: Dict = None, category: str = '') -> str:
        """渲染硬核参数列表（Top 15 Schema）"""
        if not specs:
            return '<div class="no-specs">暂无详细参数</div>'

        rows = []

        # Top 15 Schema 中文标签映射（鼠标 + 键盘）
        label_map = {
            # 鼠标 Top 15 参数
            'product_pricing': '产品与定价',
            'mold_lineage': '模具血统',
            'weight_center': '重量与重心',
            'sensor_solution': '传感器方案',
            'mcu_chip': '主控芯片',
            'polling_rate': '回报率配置',
            'end_to_end_latency': '全链路延迟',
            'switch_features': '微动特性',
            'scroll_encoder': '滚轮编码器',
            'coating_process': '涂层工艺',
            'high_refresh_battery': '高刷续航',
            'structure_quality': '结构做工',
            'feet_config': '脚贴配置',
            'wireless_interference': '无线抗干扰',
            'driver_experience': '驱动体验',
            # 键盘 Top 15 参数
            'product_layout': '产品与配列',
            'structure_form': '结构形式',
            'tech_route': '技术路线',
            'rt_params': 'RT参数',
            'sound_dampening': '声音包填充',
            'switch_details': '轴体详解',
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

        # 鼠标 Top 15 优先级排序
        mouse_priority = [
            'product_pricing', 'mold_lineage', 'weight_center', 'sensor_solution',
            'mcu_chip', 'polling_rate', 'end_to_end_latency', 'switch_features',
            'scroll_encoder', 'coating_process', 'high_refresh_battery',
            'structure_quality', 'feet_config', 'wireless_interference',
            'driver_experience'
        ]

        # 键盘 Top 15 优先级排序
        keyboard_priority = [
            'product_layout', 'structure_form', 'tech_route', 'rt_params',
            'sound_dampening', 'switch_details', 'measured_latency',
            'keycap_craftsmanship', 'bigkey_tuning', 'pcb_features',
            'case_craftsmanship', 'front_height', 'battery_efficiency',
            'connection_storage', 'software_support'
        ]

        # 根据类别选择优先级顺序
        if '鼠标' in category:
            priority_order = mouse_priority
        elif '键盘' in category:
            priority_order = keyboard_priority
        else:
            # 混合情况：优先显示鼠标字段
            priority_order = mouse_priority + [k for k in keyboard_priority if k not in mouse_priority]

        # 按优先级排序显示
        for key in priority_order:
            if key in specs:
                value = specs[key]
                if value and str(value).strip():
                    # 格式化显示值：处理字典/JSON格式
                    display_value = self._format_spec_value(value)

                    # 过滤掉无效值（暂无数据、待实测、未提及等）
                    invalid_markers = ['暂无数据', '待实测', '未提及', '未知', 'unknown', 'null', 'none']
                    if any(marker in display_value for marker in invalid_markers):
                        continue

                    label = label_map.get(key, key)

                    # 检查数据来源，添加搜索图标
                    source_icon = ''
                    if data_sources and data_sources.get(key) == 'search':
                        source_icon = ' <span style="color: #667eea;">🔍</span>'

                    rows.append(f'''<div class="spec-item">
                        <span class="spec-label">{label}{source_icon}</span>
                        <span class="spec-value">{display_value}</span>
                    </div>''')

        return f'<div class="specs-list">{"".join(rows)}</div>' if rows else '<div class="no-specs">暂无详细参数</div>'

    @staticmethod
    def _has_valid_specs(specs: Dict) -> bool:
        """
        检查 specs 字典中是否有有效的参数值

        有效值：非空、非纯"暂无数据"标记
        注意："待实测"、"未提及"等描述性文本会被保留，只在显示时做判断

        Args:
            specs: 参数字典

        Returns:
            是否存在有效参数
        """
        # 只检查是否有非空值，不做深度过滤
        # "待实测"、"未提及"等描述性文本在显示时再决定是否隐藏
        for value in specs.values():
            if value and str(value).strip():
                # 有任何非空值就返回 True
                return True

        return False

    @staticmethod
    def _format_spec_value(value: Any) -> str:
        """
        格式化参数值，处理字典/列表等复杂格式

        Args:
            value: 原始参数值

        Returns:
            格式化后的 HTML 字符串
        """
        import re

        # 处理 None 值
        if value is None:
            return '<span style="color: #718096; font-style: italic;">暂无数据</span>'

        # 转为字符串处理
        value_str = str(value).strip()

        # 空值处理
        if not value_str or value_str.lower() in ['unknown', '未知', 'none', 'null']:
            return '<span style="color: #718096; font-style: italic;">暂无数据</span>'

        # 检测是否是字典/JSON 格式
        if value_str.startswith('{') and value_str.endswith('}'):
            try:
                import json
                parsed = json.loads(value_str)
                if isinstance(parsed, dict):
                    # 转换为易读的 HTML 列表
                    items = []
                    for k, v in parsed.items():
                        # 递归格式化嵌套值
                        formatted_v = HTMLReportGenerator._format_spec_value(v)
                        # 去掉HTML标签，只保留文本（避免嵌套HTML）
                        v_clean = re.sub('<[^<]+?>', '', formatted_v)
                        items.append(f'<strong>{k}</strong>: {v_clean}')
                    return '<br>'.join(items)
            except:
                pass

        # 检测是否是列表格式
        if value_str.startswith('[') and value_str.endswith(']'):
            try:
                import json
                parsed = json.loads(value_str)
                if isinstance(parsed, list):
                    return '、'.join(str(item) for item in parsed if item)
            except:
                pass

        # 处理换行符
        if '\n' in value_str:
            return '<br>'.join(value_str.split('\n'))

        # 默认返回原值
        return value_str

    def _render_analysis(self, analysis: Dict, has_specs: bool, product: Dict = None) -> str:
        """渲染 PM 深度洞察"""
        if not analysis or not any(analysis.values()):
            # PM 洞察为空时的缺省状态
            return '''<div class="empty-analysis">
                <div class="empty-analysis-icon">📊</div>
                <div class="empty-analysis-text">PM 深度分析中...</div>
                <div class="empty-analysis-text" style="font-size: 0.85em; margin-top: 8px;">等待 LLM 接入后提供完整分析</div>
            </div>'''

        html_parts = []

        # 创新标签（新增）
        innovation_tags = product.get('innovation_tags', []) if product else []
        if innovation_tags:
            tags_html = ' '.join([f'<span style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 4px 10px; border-radius: 4px; font-size: 0.75em; margin-right: 5px; margin-bottom: 5px; display: inline-block; color: white;">{tag}</span>' for tag in innovation_tags])
            html_parts.append(f'''<div class="analysis-section">
                <div class="analysis-label">创新标签</div>
                <div class="analysis-text">{tags_html}</div>
            </div>''')

        # 市场定位
        if analysis.get('market_position'):
            html_parts.append(f'''<div class="analysis-section">
                <div class="analysis-label">市场定位</div>
                <div class="analysis-text">{analysis['market_position']}</div>
            </div>''')

        # 竞品分析
        if analysis.get('competitors'):
            html_parts.append(f'''<div class="analysis-section">
                <div class="analysis-label">竞品对比</div>
                <div class="analysis-text">{analysis['competitors']}</div>
            </div>''')

        # 目标用户
        if analysis.get('target_audience'):
            html_parts.append(f'''<div class="analysis-section">
                <div class="analysis-label">目标用户</div>
                <div class="analysis-text">{analysis['target_audience']}</div>
            </div>''')

        # 核心卖点
        if analysis.get('selling_point'):
            html_parts.append(f'''<div class="analysis-section">
                <div class="analysis-label">核心卖点</div>
                <div class="analysis-text">{analysis['selling_point']}</div>
            </div>''')

        # 优缺点分析
        verdict = analysis.get('verdict', {})
        if verdict:
            pros_list = ''.join([f'<li>{p}</li>' for p in verdict.get('pros', [])])
            cons_list = ''.join([f'<li>{c}</li>' for c in verdict.get('cons', [])])

            html_parts.append(f'''<div class="analysis-section">
                <div class="verdict-grid">
                    <div class="verdict-box pros">
                        <div class="verdict-title pros">✓ 优点</div>
                        <ul class="verdict-list pros">{pros_list}</ul>
                    </div>
                    <div class="verdict-box cons">
                        <div class="verdict-title cons">✗ 缺点</div>
                        <ul class="verdict-list cons">{cons_list}</ul>
                    </div>
                </div>
            </div>''')

        # PM 总结论
        if analysis.get('pm_summary'):
            html_parts.append(f'''<div class="pm-summary">
                <div class="pm-summary-text">"{analysis['pm_summary']}"</div>
            </div>''')

        return ''.join(html_parts) if html_parts else '<div class="no-specs">暂无 PM 分析</div>'

    def _render_links(self, records: List[Dict]) -> str:
        """渲染来源链接"""
        if not records:
            return ''

        links = []
        seen_urls = set()

        for record in records[:3]:  # 最多显示3个链接
            url = record.get('url', '')
            if url and url not in seen_urls:
                seen_urls.add(url)
                source = record.get('source', '详情')
                links.append(f'<a class="source-link" href="{url}" target="_blank" rel="noopener noreferrer">{source}</a>')

        return f'<div class="source-links">{"".join(links)}</div>' if links else ''

    def _render_source_badge(self, sources: List[str]) -> str:
        """渲染来源 Badge"""
        if not sources:
            return ''

        # 判断来源
        has_inwaishe = 'in外设' in sources
        has_wstx = '外设天下' in sources

        if has_inwaishe and has_wstx:
            badge_class = 'both'
            badge_text = '双平台'
        elif has_inwaishe:
            badge_class = 'inwaishe'
            badge_text = 'in外设'
        else:
            badge_class = 'wstx'
            badge_text = '外设天下'

        return f'<div class="source-badge {badge_class}">{badge_text}</div>'


# ==================== 主流程 ====================

def mcp_search_wrapper(query: str) -> Optional[str]:
    """
    MCP 搜索包装函数 - 用于 ParameterCompleter

    注意：此函数需要在 Claude Code 环境中运行，并已配置 web-search-prime 工具

    Args:
        query: 搜索查询字符串

    Returns:
        搜索结果摘要文本（合并前3个结果的content字段）
    """
    try:
        # 这里需要调用 MCP 工具
        # 由于 Python 代码无法直接访问 MCP 工具，我们需要通过特殊的方式
        # 在实际运行时，此函数会被替换为真正的 MCP 调用

        # 临时方案：返回特殊标记，由调用者处理
        # 在主流程中，我们会通过其他方式处理搜索
        print(f"        [MCP搜索] 请求: {query}")
        return f"MCP_SEARCH:{query}"

    except Exception as e:
        print(f"        [MCP搜索] 失败: {str(e)[:100]}")
        return None


# ==================== 数据完整性检查与二次搜索补全 ====================

def check_data_completeness(extracted: Dict) -> Dict:
    """
    检查产品数据的完整性

    Args:
        extracted: LLM提取的产品数据

    Returns:
        dict: {
            'is_complete': bool,  # 数据是否完整
            'missing_fields': list,  # 缺失的关键字段
            'completeness_score': float  # 完整度分数 (0-1)
        }
    """
    category = extracted.get('category', '').lower()
    specs = extracted.get('specs', {})

    # 定义关键字段（不同产品类别）
    critical_fields = {
        'mouse': ['sensor', 'weight', 'polling_rate', 'price', 'connection'],
        'keyboard': ['switch', 'connection', 'layout', 'structure', 'price']
    }

    # 根据类别选择关键字段
    if 'mouse' in category or '鼠标' in extracted.get('product_name', ''):
        required_fields = critical_fields['mouse']
    elif 'keyboard' in category or '键盘' in extracted.get('product_name', ''):
        required_fields = critical_fields['keyboard']
    else:
        # 未知类别，检查所有字段
        required_fields = list(set(critical_fields['mouse'] + critical_fields['keyboard']))

    # 检查缺失字段
    missing_fields = []
    present_fields = 0

    for field in required_fields:
        value = specs.get(field, '')
        if value and value not in ['未知', '未公开', 'N/A', '']:
            present_fields += 1
        else:
            missing_fields.append(field)

    completeness_score = present_fields / len(required_fields) if required_fields else 0

    # 判断是否完整（完整度 >= 60%）
    is_complete = completeness_score >= 0.6

    return {
        'is_complete': is_complete,
        'missing_fields': missing_fields,
        'completeness_score': completeness_score,
        'present_count': present_fields,
        'total_count': len(required_fields)
    }


def second_round_search(product_name: str, category: str, missing_fields: list, search_func) -> Optional[Dict]:
    """
    第二次搜索补全 - 针对缺失的字段进行专门搜索

    Args:
        product_name: 产品名称
        category: 产品类别
        missing_fields: 缺失的字段列表
        search_func: 搜索函数

    Returns:
        补全后的数据，或 None
    """
    if not search_func or not missing_fields:
        return None

    print(f"        [二次搜索] 启动补全搜索，缺失字段: {missing_fields}")

    # 构造搜索关键词
    search_queries = []

    # 基础搜索：产品名 + 规格
    search_queries.append(f"{product_name} 规格 参数")

    # 针对缺失字段的专门搜索
    field_keywords_cn = {
        'sensor': '传感器',
        'weight': '重量',
        'polling_rate': '回报率',
        'price': '价格',
        'connection': '连接方式',
        'switch': '轴体',
        'layout': '配列',
        'structure': '结构'
    }

    for field in missing_fields[:2]:  # 最多搜索2个缺失字段
        keyword = field_keywords_cn.get(field, field)
        search_queries.append(f"{product_name} {keyword}")

    # 添加站点限定搜索（专门搜索in外设和外设天下）
    site_queries = [
        f"site:inwaishe.com {product_name}",
        f"site:wstx.com {product_name}"
    ]
    search_queries.extend(site_queries)

    # 执行搜索
    all_search_results = []
    for query in search_queries[:4]:  # 限制搜索次数
        try:
            print(f"        [二次搜索] 查询: {query}")
            result = search_func(query)
            if result:
                all_search_results.append(result)
        except Exception as e:
            print(f"        [二次搜索] 失败: {str(e)[:50]}")

    if not all_search_results:
        print(f"        [二次搜索] 无搜索结果")
        return None

    # 合并搜索结果
    combined_content = '\n\n'.join(all_search_results)

    print(f"        [二次搜索] 获得 {len(all_search_results)} 条结果，总字符数: {len(combined_content)}")

    return {
        'search_results': all_search_results,
        'combined_content': combined_content,
        'queries_used': search_queries[:4]
    }


def process_single_product(extractor, completer, product, index):
    """
    处理单个产品（用于并发调用）

    Args:
        extractor: LLMExtractor实例
        completer: ParameterCompleter实例（参数补全器）
        product: 产品数据
        index: 产品索引

    Returns:
        处理结果字典，包含extracted数据或error信息
    """
    try:
        # 确保 product 是字典类型
        if not isinstance(product, dict):
            return {
                'error': True,
                'dropped': True,
                'reason': f'类型异常: {type(product)}'
            }

        product_name = product.get('product_name', 'Unknown')
        if isinstance(product_name, str):
            product_name = product_name[:30]
        else:
            product_name = str(product_name)[:30]

        print(f"    [{index}] 开始处理: {product_name}...")

        # 调用API提取产品信息
        extracted = extractor.extract_product_info(product)

        # 保留原始数据
        extracted['_raw'] = product

        # 【修复】参数自动补全 V2 - 在 specs 检查之前执行！
        if completer:
            try:
                # 为 ParameterCompleterV2 准备数据
                product_for_completion = {
                    'product_name': extracted.get('product_name', ''),
                    'category': extracted.get('category', ''),
                    'content_text': product.get('combined_content', ''),
                    'specs': extracted.get('specs', {}),
                    'data_sources': {}
                }

                # 调用 V2 版本的参数补全
                completed = completer.complete_parameters(product_for_completion)

                # 更新 extracted 数据
                extracted['specs'] = completed.get('specs', {})
                extracted['data_sources'] = completed.get('data_sources', {})

            except Exception as e:
                print(f"    [{index}] 参数补全失败: {str(e)[:50]}")

        # 【新增】数据完整性检查
        completeness_check = check_data_completeness(extracted)
        print(f"    [{index}] 数据完整度: {completeness_check['completeness_score']:.1%} ({completeness_check['present_count']}/{completeness_check['total_count']})")

        # 【新增】第二次搜索补全 - 如果数据不完整
        if not completeness_check['is_complete'] and completer and completer.search_enabled:
            missing_fields = completeness_check['missing_fields']
            print(f"    [{index}] 数据不完整，缺失: {missing_fields}，启动二次搜索...")

            try:
                # 执行第二次搜索
                search_result = second_round_search(
                    product_name=extracted.get('product_name', ''),
                    category=extracted.get('category', ''),
                    missing_fields=missing_fields,
                    search_func=completer.search_func
                )

                if search_result:
                    # 使用搜索结果再次补全参数
                    product_for_completion_v2 = {
                        'product_name': extracted.get('product_name', ''),
                        'category': extracted.get('category', ''),
                        'content_text': search_result.get('combined_content', ''),
                        'specs': extracted.get('specs', {}),
                        'data_sources': {}
                    }

                    completed_v2 = completer.complete_parameters(product_for_completion_v2)

                    # 更新 extracted 数据（第二次补全）
                    extracted['specs'].update(completed_v2.get('specs', {}))
                    extracted['data_sources'].update(completed_v2.get('data_sources', {}))

                    # 记录二次搜索来源
                    if '_search_sources' not in extracted:
                        extracted['_search_sources'] = []
                    extracted['_search_sources'].extend(search_result.get('queries_used', []))

                    print(f"    [{index}] 二次搜索补全完成")

            except Exception as e:
                print(f"    [{index}] 二次搜索失败: {str(e)[:50]}")

        # 补全后再检查 specs 是否为空
        specs = extracted.get('specs', {})
        has_valid_specs = any(specs.values())

        if not has_valid_specs:
            print(f"    [{index}] 跳过（补全后仍无有效specs）: {product_name}")
            return {
                'error': False,
                'dropped': True,
                'data': None
            }

        print(f"    [{index}] 完成: {product_name}")
        return {
            'error': False,
            'dropped': False,
            'data': extracted
        }

    except Exception as e:
        print(f"    [{index}] 失败: {str(e)[:50]}...")
        return {
            'error': True,
            'dropped': True,
            'reason': str(e)
        }


def _parse_chart_data(html_content: str, chart_id: str) -> dict:
    """
    解析 Chart.js 图表的 data/labels

    Args:
        html_content: HTML报告内容
        chart_id: 图表元素ID (如 'categoryChart', 'sensorChart', 'priceChart')

    Returns:
        dict: {
            'labels': list,      # 图表标签列表
            'data': list,        # 图表数据列表
            'labels_count': int, # 标签数量
            'samples_sum': int,  # 数据总和
            'error': str or None # 解析错误信息
        }
    """
    result = {
        'labels': [],
        'data': [],
        'labels_count': 0,
        'samples_sum': 0,
        'error': None
    }

    # 查找 new Chart(document.getElementById('{chart_id}')) 调用
    chart_pattern = rf'new Chart\(document\.getElementById\(\'{chart_id}\'\),\s*\{{(.*?)\}}\);'
    chart_match = re.search(chart_pattern, html_content, re.DOTALL)

    if not chart_match:
        result['error'] = f"未找到图表元素 '{chart_id}'"
        return result

    chart_content = chart_match.group(1)

    # 解析 labels 数组
    labels_match = re.search(r'labels:\s*\[([^\]]*(?:\[[^\]]*\][^\]]*)*)\]', chart_content, re.DOTALL)
    if not labels_match:
        result['error'] = f"图表 '{chart_id}' 缺少 labels 数组"
        return result

    labels_str = labels_match.group(1)
    # 处理 Unicode 转义序列和 JSON 字符串
    try:
        # 尝试直接解析为 JSON 数组
        labels_str_clean = labels_str.strip()
        # 处理 JavaScript Unicode 转义 (如 \u9f20\u6807)
        labels_str_clean = labels_str_clean.encode().decode('unicode-escape')
        labels = json.loads(f'[{labels_str_clean}]')
        result['labels'] = labels
        result['labels_count'] = len(labels)
    except:
        # 降级：简单分割处理
        labels = [l.strip().strip('"').strip("'") for l in labels_str.split(',') if l.strip()]
        result['labels'] = labels
        result['labels_count'] = len(labels)

    # 解析 data 数组
    data_match = re.search(r'data:\s*\[([^\]]*)\]', chart_content, re.DOTALL)
    if not data_match:
        result['error'] = f"图表 '{chart_id}' 缺少 data 数组"
        return result

    data_str = data_match.group(1)
    try:
        data_values = [int(d.strip()) for d in data_str.split(',') if d.strip().isdigit() or d.strip().lstrip('-').isdigit()]
        result['data'] = data_values
        result['samples_sum'] = sum(data_values)
    except:
        result['error'] = f"图表 '{chart_id}' data 数组解析失败"

    return result


def _validate_four_way_consistency(html_content: str) -> dict:
    """
    四向一致性校验：nav_counts == section_counts == chart_counts == card_counts

    Args:
        html_content: HTML报告内容

    Returns:
        dict: {
            'structural_passed': bool,  # 结构性校验是否通过
            'data_passed': bool,        # 数据一致性校验是否通过
            'details': dict,            # 详细信息
            'errors': list              # 错误列表
        }
    """
    result = {
        'structural_passed': True,
        'data_passed': True,
        'details': {},
        'errors': [],
        'warnings': []
    }

    # 1. 提取导航栏分类按钮数 (nav_count)
    # 统计 class="nav-btn" 的数量，这是导航分类按钮数（鼠标/键盘/其他等）
    nav_btn_count = 0
    nav_match = re.search(r'<div[^>]*class="[^"]*nav-bar[^"]*"[^>]*>(.*?)</div>', html_content, re.DOTALL)
    if nav_match:
        nav_content = nav_match.group(1)
        nav_btns = re.findall(r'<a[^>]*class="[^"]*nav-btn[^"]*"[^>]*>', nav_content)
        nav_btn_count = len(nav_btns)

    result['details']['nav_category_buttons'] = nav_btn_count

    # 2. 提取板块数量 (section_count) - 统计 <div class="product-card">
    section_count = len(re.findall(r'<div[^>]*class="[^"]*product-card[^"]*"[^>]*>', html_content))
    result['details']['section_count'] = section_count

    # 3. 提取卡片数量 (card_count) - 统计产品卡片 div
    card_count = len(re.findall(r'<div[^>]*class="[^"]*product-card[^"]*"[^>]*>', html_content))
    result['details']['card_count'] = card_count

    # 4. 解析图表数据 (labels_count, samples_sum)
    charts = {
        'category': '品类占比',
        'sensor': '鼠标传感器',
        'price': '价格区间'
    }

    chart_details = {}
    for chart_id, chart_name in charts.items():
        chart_data = _parse_chart_data(html_content, f'{chart_id}Chart')
        chart_details[chart_id] = {
            'name': chart_name,
            'labels_count': chart_data['labels_count'],
            'samples_sum': chart_data['samples_sum'],
            'labels': chart_data['labels'],
            'data': chart_data['data'],
            'error': chart_data.get('error')
        }

        if chart_data.get('error'):
            result['warnings'].append(f"{chart_name}图表解析失败: {chart_data['error']}")

    result['details']['charts'] = chart_details

    # 结构性校验：确保关键计数都提取成功
    if section_count == 0:
        result['errors'].append("产品板块计数为0，可能缺少产品卡片")
        result['structural_passed'] = False

    if nav_btn_count == 0:
        result['warnings'].append("导航栏分类按钮数为0，可能缺少导航栏")

    # 数据一致性校验：section == card（核心一致性）
    if section_count != card_count:
        result['errors'].append(
            f"核心数量不一致: section={section_count}, card={card_count}"
        )
        result['data_passed'] = False

    # 图表一致性校验
    # category_chart samples_sum 应等于总卡片数
    category_sum = chart_details['category']['samples_sum']
    if category_sum > 0 and category_sum != card_count:
        result['errors'].append(
            f"品类图表数据总和({category_sum}) != 卡片总数({card_count})"
        )
        result['data_passed'] = False

    # sensor_chart samples_sum 应等于鼠标数
    sensor_sum = chart_details['sensor']['samples_sum']
    # 从导航按钮中查找鼠标数量（格式：🖱️ 鼠标 (9)）
    mice_count_match = re.search(r'鼠标\s*\((\d+)\)', html_content)
    mice_count = int(mice_count_match.group(1)) if mice_count_match else 0
    if sensor_sum > 0 and mice_count > 0 and sensor_sum != mice_count:
        result['warnings'].append(
            f"传感器图表数据总和({sensor_sum}) != 鼠标数({mice_count})，可能存在鼠标产品未标记传感器"
        )

    # price_chart samples_sum 应等于有有效价格的产品数（或根据策略）
    price_sum = chart_details['price']['samples_sum']
    if price_sum > 0 and price_sum > card_count:
        result['errors'].append(
            f"价格图表数据总和({price_sum}) > 卡片总数({card_count})"
        )
        result['data_passed'] = False

    return result


def validate_html_report(html_path: str, force: bool = False) -> bool:
    """
    校验HTML报告是否包含所有必需的关键组件

    Args:
        html_path: HTML报告文件路径
        force: 是否强制输出（仅绕过数据一致性校验，不绕过结构性校验）

    Returns:
        bool: 校验是否通过

    Raises:
        SystemExit: 结构性校验失败时退出程序
    """
    # [FIX 8] 四向一致性校验分级：结构性必失败；数据一致性默认失败但支持 --force 输出
    required_components = {
        'nav-bar': '导航栏（包含快速跳转和搜索框）',
        'searchInput': '搜索输入框',
        'product-overview': '产品概览模块（左栏）',
        'product-specs': '硬核参数模块（中栏）',
        'product-analysis': 'PM深度洞察模块（右栏）',
        'PM 深度洞察': 'PM深度洞察标题'
    }

    print(f"\n[校验] 检查HTML报告: {html_path}")

    if not Path(html_path).exists():
        print(f"[ERROR] 文件不存在: {html_path}")
        raise SystemExit(1)

    with open(html_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # ===== 阶段 1: 结构性校验（必失败） =====
    missing_components = []
    for component, description in required_components.items():
        if component not in content:
            missing_components.append(f"  [X] {component}: {description}")

    if missing_components:
        print(f"\n[FAIL] HTML报告结构性校验失败！缺少以下关键组件:")
        for item in missing_components:
            print(item)
        print(f"\n请使用 --template pm_deep 参数重新生成报告！")
        raise SystemExit(1)
    else:
        print("[OK] 所有关键组件结构性校验通过:")
        for component, description in required_components.items():
            print(f"  [OK] {component}: {description}")

    # ===== 阶段 2: 四向数据一致性校验（可 --force 强制通过） =====
    print("\n[校验] 四向数据一致性校验...")
    validation_result = _validate_four_way_consistency(content)

    # 打印详细信息
    details = validation_result['details']
    print(f"  - 导航分类按钮 (nav_btn):  {details.get('nav_category_buttons', 'N/A')}")
    print(f"  - 板块计数 (section):      {details.get('section_count', 'N/A')}")
    print(f"  - 卡片计数 (card):         {details.get('card_count', 'N/A')}")

    # 打印图表详情
    if details.get('charts'):
        print(f"  - 图表数据 (charts):")
        for chart_id, chart_info in details['charts'].items():
            name = chart_info.get('name', chart_id)
            labels_count = chart_info.get('labels_count', 0)
            samples_sum = chart_info.get('samples_sum', 0)
            error = chart_info.get('error')
            if error:
                print(f"      * {name}: [ERROR] {error}")
            else:
                print(f"      * {name}: labels_count={labels_count}, samples_sum={samples_sum}")

    # 打印警告信息（如果有）
    if validation_result.get('warnings'):
        print("\n[WARNING] 解析警告:")
        for warning in validation_result['warnings']:
            print(f"  [!] {warning}")

    if validation_result['data_passed']:
        print("[OK] 四向数据一致性校验通过")
    else:
        print("[WARNING] 四向数据一致性校验发现问题:")
        for error in validation_result['errors']:
            print(f"  [!] {error}")

        if force:
            print("\n[FORCE] 使用 --force 强制输出（数据一致性问题已忽略）")
        else:
            print("\n[FAIL] 数据一致性校验失败，使用 --force 可强制输出")
            raise SystemExit(1)

    return True


def main(template_mode="pm_deep"):
    """主流程

    Args:
        template_mode: 模板模式，"pm_deep" (默认) 或 "simple"
    """
    global TEMPLATE_MODE, HTML_REPORT
    TEMPLATE_MODE = template_mode

    print("=" * 60)
    print("外设新品监控报告生成系统 (Phase 4 最终优化版)")
    print(f"模板模式: {AVAILABLE_TEMPLATES.get(template_mode, template_mode)}")
    print("PM 深度分析版 | 产品去重合并 | 交互优化")
    print("=" * 60)

    # 确保输出目录存在
    OUTPUT_DIR.mkdir(exist_ok=True)

    # 步骤 1: 数据清洗
    print("\n[步骤 1/5] 数据预处理与清洗")
    cleaner = DataCleaner('output/report_data_2026_01.xlsx')
    filtered_df = cleaner.filter_by_keywords()
    filtered_df = cleaner.filter_by_blacklist(filtered_df)  # 黑名单过滤
    products = cleaner.smart_deduplicate(filtered_df)

    # 步骤 2: LLM PM 深度分析（并发处理）
    print(f"\n[步骤 2/5] LLM PM 深度分析（并发模式）")
    extractor = LLMExtractor(LLM_CONFIG)

    # 初始化参数补全器 V2（Top 15 Schema）
    print(f"\n[步骤 2.1/5] 初始化参数补全器V2（Top 15 Schema）...")

    # 导入 MCP 客户端
    from mcp_client import get_mcp_client

    mcp_client = get_mcp_client()

    def mcp_search_func(query: str) -> str:
        """MCP 搜索函数封装"""
        if mcp_client.is_available():
            result = mcp_client.search(query, max_results=3)
            return result if result else ""
        return ""

    # 根据 MCP 可用性决定是否传入搜索函数
    search_func = mcp_search_func if mcp_client.is_available() else None
    completer = ParameterCompleterV2(llm_config=LLM_CONFIG, search_func=search_func)

    search_status = "启用" if mcp_client.is_available() else "禁用"
    print(f"[OK] 参数补全器V2已初始化（Top 15 Schema，MCP搜索: {search_status}）")

    import concurrent.futures
    import time

    # 并发处理配置（降低并发以提高稳定性）
    batch_size = 5  # 每批并发5个（从9降低到5以减少API压力）
    total_products = len(products)
    total_batches = (total_products + batch_size - 1) // batch_size

    print(f"  总产品数: {total_products}")
    print(f"  并发数: {batch_size}")
    print(f"  分批数: {total_batches}")
    print(f"  预计耗时: {total_batches * 15}秒 ≈ {total_batches * 15 // 60}分钟")
    print(f"  参数补全: {'启用' if completer.search_enabled else '禁用'}")
    print()

    processed_products = []
    dropped_count = 0
    failed_items = []  # 记录失败的产品信息
    start_time = time.time()

    # 分批并发处理
    for batch_idx in range(total_batches):
        start_idx = batch_idx * batch_size
        end_idx = min(start_idx + batch_size, total_products)
        batch_products = products[start_idx:end_idx]

        print(f"[批次 {batch_idx + 1}/{total_batches}] 处理产品 {start_idx + 1}-{end_idx}...")

        # 使用线程池并发处理当前批次
        with concurrent.futures.ThreadPoolExecutor(max_workers=batch_size) as executor:
            # 提交所有任务（注意：现在传递 completer 参数）
            future_to_idx = {
                executor.submit(process_single_product, extractor, completer, product, idx + 1): idx + 1
                for idx, product in enumerate(batch_products, start_idx)
            }

            # 等待所有任务完成
            for future in concurrent.futures.as_completed(future_to_idx):
                idx = future_to_idx[future]
                try:
                    result = future.result()
                    if result.get('error'):
                        print(f"      [{idx}] 处理失败: {result.get('reason', 'Unknown error')}")
                        # 记录失败项
                        failed_items.append({
                            'index': idx,
                            'reason': result.get('reason', 'Unknown error'),
                            'product_name': batch_products[idx - start_idx - 1].get('product_name', 'Unknown')
                        })
                        dropped_count += 1
                    elif result.get('dropped'):
                        # specs为空，正常跳过
                        dropped_count += 1
                    else:
                        # 成功提取
                        processed_products.append(result['data'])
                except Exception as e:
                    print(f"      [{idx}] 异常: {e}")
                    # 记录异常项
                    failed_items.append({
                        'index': idx,
                        'reason': str(e),
                        'product_name': batch_products[idx - start_idx - 1].get('product_name', 'Unknown')
                    })
                    dropped_count += 1

    elapsed = time.time() - start_time
    print(f"\n  [完成] 并发处理耗时: {elapsed:.1f}秒")

    if dropped_count > 0:
        print(f"[OK] 过滤掉 {dropped_count} 个无效产品")

    # 保存失败项到日志
    if failed_items:
        from datetime import datetime
        log_dir = Path('logs')
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / f'failed_items_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        with open(log_file, 'w', encoding='utf-8') as f:
            json.dump(failed_items, f, ensure_ascii=False, indent=2)
        print(f"[INFO] 失败项已记录到: {log_file}")

    # 步骤 2.5: 按优先级排序产品（品牌权重 + 文章长度）
    print(f"\n[步骤 2.5/5] 按优先级排序产品...")
    # 为每个产品计算优先级分数
    for product in processed_products:
        product['_priority_score'] = extractor.calculate_product_priority(product)

    # 按优先级分数降序排序
    processed_products.sort(key=lambda p: p.get('_priority_score', 0), reverse=True)
    print(f"[OK] 已按优先级排序（品牌权重 + 文章长度 + 图片数量）")

    # 步骤 3: 生成深色极客风 HTML 报告（含产品合并）
    print(f"\n[步骤 3/5] 生成深色极客风 HTML 报告")
    generator = HTMLReportGenerator(processed_products)
    generator.generate(HTML_REPORT)

    # 保存合并后的数据
    with open(PROCESSED_JSON, 'w', encoding='utf-8') as f:
        json.dump(generator.products, f, ensure_ascii=False, indent=2)
    print(f"[OK] 合并后数据已保存: {PROCESSED_JSON} ({len(generator.products)} 款产品)")

    # 步骤 4: 完成
    print(f"\n[步骤 4/5] 全部完成！")
    print(f"\n交付物清单:")
    print(f"  1. {PROCESSED_JSON} ({len(generator.products)} 款产品)")
    print(f"  2. {HTML_REPORT}")
    print(f"\n新特性:")
    print(f"  [+] 产品智能去重与合并")
    print(f"  [+] 实时搜索过滤")
    print(f"  [+] 分类锚点导航")
    print(f"  [+] 回到顶部按钮")
    print(f"  [+] 图片懒加载 + Lightbox预览")
    print(f"  [+] PM洞察为空时的自适应布局")
    print(f"\n" + "=" * 60)


def main(template_mode="pm_deep", input_file=None, target_year=None, target_month=None):
    """主流程

    Args:
        template_mode: 模板模式，"pm_deep" (默认) 或 "simple"
        input_file: 输入文件路径（如果为 None，则使用默认路径）
        target_year: 目标年份（如果为 None，则使用 TARGET_YEAR）
        target_month: 目标月份（如果为 None，则使用 TARGET_MONTH）
    """
    global TEMPLATE_MODE, HTML_REPORT, TARGET_YEAR, TARGET_MONTH
    TEMPLATE_MODE = template_mode

    # 更新全局配置
    if target_year is not None:
        TARGET_YEAR = target_year
    if target_month is not None:
        TARGET_MONTH = target_month

    print("=" * 60)
    print("外设新品监控报告生成系统 (Phase 4 最终优化版)")
    print(f"模板模式: {AVAILABLE_TEMPLATES.get(template_mode, template_mode)}")
    print(f"目标期间: {TARGET_YEAR}年{TARGET_MONTH}月")
    print("PM 深度分析版 | 产品去重合并 | 交互优化")
    print("=" * 60)

    # 确定输入文件路径
    if input_file is None:
        input_file = f'output/report_data_{TARGET_YEAR}_{TARGET_MONTH:02d}.json'

    # 检查输入文件是否存在
    input_path = Path(input_file)
    if not input_path.exists():
        # 尝试 Excel 格式
        excel_path = Path(str(input_path).replace('.json', '.xlsx'))
        if excel_path.exists():
            input_path = excel_path
        else:
            print(f"\n[ERROR] 输入文件不存在: {input_file}")
            print(f"\n请先运行爬虫采集数据，或使用 --input 参数指定输入文件：")
            print(f"  python etl_pipeline.py --input <your_data.json>")
            print(f"  python etl_pipeline.py --month {TARGET_YEAR}-{TARGET_MONTH:02d}")
            raise SystemExit(1)

    print(f"\n[INFO] 输入文件: {input_path}")

    # 确保输出目录存在
    OUTPUT_DIR.mkdir(exist_ok=True)

    # 步骤 1: 数据清洗
    print("\n[步骤 1/5] 数据预处理与清洗")
    cleaner = DataCleaner(str(input_path))
    filtered_df = cleaner.filter_by_keywords()
    filtered_df = cleaner.filter_by_blacklist(filtered_df)  # 黑名单过滤
    products = cleaner.smart_deduplicate(filtered_df)

    # 步骤 2: LLM PM 深度分析（并发处理）
    print(f"\n[步骤 2/5] LLM PM 深度分析（并发模式）")
    extractor = LLMExtractor(LLM_CONFIG)

    # 初始化参数补全器 V2（Top 15 Schema）
    print(f"\n[步骤 2.1/5] 初始化参数补全器V2（Top 15 Schema）...")

    completer = ParameterCompleterV2(llm_config=LLM_CONFIG, search_func=None)
    print(f"[OK] 参数补全器V2已初始化（Top 15 Schema，搜索功能已禁用）")

    import concurrent.futures
    import time

    # 并发处理配置
    batch_size = 5
    total_products = len(products)
    total_batches = (total_products + batch_size - 1) // batch_size

    print(f"  总产品数: {total_products}")
    print(f"  并发数: {batch_size}")
    print(f"  分批数: {total_batches}")
    print()

    processed_products = []
    dropped_count = 0
    failed_items = []
    start_time = time.time()

    # 分批并发处理
    for batch_idx in range(total_batches):
        start_idx = batch_idx * batch_size
        end_idx = min(start_idx + batch_size, total_products)
        batch_products = products[start_idx:end_idx]

        print(f"[批次 {batch_idx + 1}/{total_batches}] 处理产品 {start_idx + 1}-{end_idx}...")

        with concurrent.futures.ThreadPoolExecutor(max_workers=batch_size) as executor:
            future_to_idx = {
                executor.submit(process_single_product, extractor, completer, product, idx + 1): idx + 1
                for idx, product in enumerate(batch_products, start_idx)
            }

            for future in concurrent.futures.as_completed(future_to_idx):
                idx = future_to_idx[future]
                try:
                    result = future.result()
                    if result.get('error'):
                        print(f"      [{idx}] 处理失败: {result.get('reason', 'Unknown error')}")
                        failed_items.append({
                            'index': idx,
                            'reason': result.get('reason', 'Unknown error'),
                            'product_name': batch_products[idx - start_idx - 1].get('product_name', 'Unknown')
                        })
                        dropped_count += 1
                    elif result.get('dropped'):
                        dropped_count += 1
                    else:
                        processed_products.append(result['data'])
                except Exception as e:
                    print(f"      [{idx}] 异常: {e}")
                    failed_items.append({
                        'index': idx,
                        'reason': str(e),
                        'product_name': batch_products[idx - start_idx - 1].get('product_name', 'Unknown')
                    })
                    dropped_count += 1

    elapsed = time.time() - start_time
    print(f"\n  [完成] 并发处理耗时: {elapsed:.1f}秒")

    if dropped_count > 0:
        print(f"[OK] 过滤掉 {dropped_count} 个无效产品")

    # 保存失败项到日志
    if failed_items:
        from datetime import datetime
        log_dir = Path('logs')
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / f'failed_items_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        with open(log_file, 'w', encoding='utf-8') as f:
            json.dump(failed_items, f, ensure_ascii=False, indent=2)
        print(f"[INFO] 失败项已记录到: {log_file}")

    # 步骤 2.5: 按优先级排序产品
    print(f"\n[步骤 2.5/5] 按优先级排序产品...")
    for product in processed_products:
        product['_priority_score'] = extractor.calculate_product_priority(product)
    processed_products.sort(key=lambda p: p.get('_priority_score', 0), reverse=True)
    print(f"[OK] 已按优先级排序")

    # 步骤 2.6: 二次补全（必经流程）
    print(f"\n[步骤 2.6/5] 二次补全（必经流程）...")

    # 保存补全前的数据（用于覆盖率对比）
    products_before_enrichment = [p.copy() for p in processed_products]

    processed_products = enrich_missing_fields(processed_products)

    # 打印补全统计摘要（包含覆盖率对比）并返回统计信息
    enrichment_summary = print_enrichment_summary(processed_products, products_before_enrichment)

    # 检查覆盖率告警阈值
    for category in ['鼠标', '键盘']:
        if category in enrichment_summary['coverage']['after']:
            coverage_rate = enrichment_summary['coverage']['after'][category]['coverage']

            if coverage_rate < 30:
                print(f"\n[WARNING] {category} 关键字段覆盖率仍然较低: {coverage_rate:.1f}%")
                print(f"  建议：检查输入数据质量，或考虑启用跨源补全（SECOND_ROUND_MODE=search/both）")

    print(f"[OK] 二次补全完成")

    # 步骤 3: 生成 HTML 报告
    print(f"\n[步骤 3/5] 生成深色极客风 HTML 报告")
    generator = HTMLReportGenerator(processed_products)
    generator.generate(HTML_REPORT)

    # 保存合并后的数据
    with open(PROCESSED_JSON, 'w', encoding='utf-8') as f:
        json.dump(generator.products, f, ensure_ascii=False, indent=2)
    print(f"[OK] 合并后数据已保存: {PROCESSED_JSON} ({len(generator.products)} 款产品)")
    print(f"[OK] HTML 报告已生成: {HTML_REPORT}")

    # 步骤 4: 完成
    print(f"\n[步骤 4/5] 全部完成！")
    print(f"\n交付物清单:")
    print(f"  1. {PROCESSED_JSON} ({len(generator.products)} 款产品)")
    print(f"  2. {HTML_REPORT}")
    print(f"\n" + "=" * 60)

if __name__ == '__main__':
    import argparse
    import re

    parser = argparse.ArgumentParser(
        description='外设新品监控报告生成系统',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例用法:
  # 一键模式：爬取 + 生成 PM 深度分析版报告（推荐）
  python etl_pipeline.py --month 2026-01 --fetch --template pm_deep

  # 使用默认输入文件 (output/report_data_2026_01.json)
  python etl_pipeline.py

  # 指定月份（自动查找 input/output/report_data_YYYY_MM.json）
  python etl_pipeline.py --month 2026-01

  # 指定自定义输入文件
  python etl_pipeline.py --input data/my_products.json

  # 组合使用：指定月份和模板
  python etl_pipeline.py --month 2026-01 --template pm_deep

  # 仅校验现有报告
  python etl_pipeline.py --validate-only --report-path output/monthly_report_2026_01.html

可用模板:
  pm_deep  - PM深度分析版（完整三栏布局 + nav-bar + 搜索 + PM深度洞察）
  simple   - 简化版（仅基本信息）
        '''
    )

    parser.add_argument(
        '--template', '-t',
        type=str,
        default='pm_deep',
        choices=['pm_deep', 'simple'],
        help='报告模板模式（默认: pm_deep）'
    )

    parser.add_argument(
        '--month',
        type=str,
        metavar='YYYY-MM',
        help='目标月份（格式: YYYY-MM，如 2026-01）'
    )

    parser.add_argument(
        '--input',
        type=str,
        metavar='PATH',
        help='输入文件路径（JSON 或 Excel 格式）'
    )

    parser.add_argument(
        '--validate-only',
        action='store_true',
        help='仅校验现有HTML报告，不生成新报告'
    )

    parser.add_argument(
        '--report-path',
        type=str,
        default=None,
        help='要校验的HTML报告路径'
    )

    parser.add_argument(
        '--fetch', '--crawl',
        action='store_true',
        help='先运行爬虫采集数据，再生成报告（一键模式）'
    )

    parser.add_argument(
        '--force',
        action='store_true',
        help='数据一致性校验失败时仍强制输出（仅绕过数据一致性校验，不绕过结构性校验）'
    )

    args = parser.parse_args()

    # 解析 --month 参数
    target_year = None
    target_month = None

    if args.month:
        match = re.match(r'(\d{4})-(\d{2})', args.month)
        if not match:
            print(f"[ERROR] 无效的月份格式: {args.month}")
            print("正确格式: YYYY-MM (例如: 2026-01)")
            raise SystemExit(1)
        target_year = int(match.group(1))
        target_month = int(match.group(2))

    # 如果使用 --fetch，确保提供了 --month
    if args.fetch:
        if target_year is None or target_month is None:
            # 使用默认值
            target_year = TARGET_YEAR
            target_month = TARGET_MONTH

        # 运行爬虫
        fetch_data(target_year, target_month)

    # 确定 report_path 默认值
    if args.report_path is None:
        args.report_path = str(HTML_REPORT)

    if args.validate_only:
        # 仅校验模式
        validate_html_report(args.report_path, force=args.force)

        # [FIX E] 如果存在 processed_products.json，也输出 enrichment summary
        json_path = Path(str(args.report_path).replace('.html', '.json'))
        if not json_path.exists():
            json_path = PROCESSED_JSON

        if json_path.exists():
            print("\n" + "=" * 60)
            print("执行 enrichment 统计校验...")
            print("=" * 60)
            validate_enrichment_summary(str(json_path))
        else:
            print(f"\n[INFO] 未找到 enrichment 数据文件: {json_path}")
            print("  跳过 enrichment 统计校验")
    else:
        # 生成报告模式
        main(
            template_mode=args.template,
            input_file=args.input,
            target_year=target_year,
            target_month=target_month
        )
        # 生成后自动校验
        print("\n" + "=" * 60)
        print("执行生成后校验...")
        print("=" * 60)
        validate_html_report(str(HTML_REPORT), force=args.force)
