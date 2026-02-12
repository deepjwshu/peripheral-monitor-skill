"""
配置文件 - 外设资讯采集工具
"""
import os
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

# 目标配置
TARGET_YEAR = 2026
TARGET_MONTH = 1

# 请求配置
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
REQUEST_TIMEOUT = 10

# 延时配置（秒）
# [FIX 4] 统一爬虫延时 env key：优先使用 SPIDER_DELAY_SECONDS + SPIDER_DELAY_JITTER
# 降级支持旧的 MIN_DELAY/MAX_DELAY（用于向后兼容）
SPIDER_DELAY_SECONDS = float(os.getenv('SPIDER_DELAY_SECONDS', '2.0'))  # 基础延时
SPIDER_DELAY_JITTER = float(os.getenv('SPIDER_DELAY_JITTER', '1.0'))   # 随机抖动范围

# 向后兼容：如果 .env 中定义了旧值，优先使用
MIN_DELAY = float(os.getenv('MIN_DELAY', SPIDER_DELAY_SECONDS))
MAX_DELAY = float(os.getenv('MAX_DELAY', SPIDER_DELAY_SECONDS + SPIDER_DELAY_JITTER))

# 输出配置
OUTPUT_DIR = 'output'
OUTPUT_EXCEL = f'report_data_{TARGET_YEAR}_{TARGET_MONTH:02d}.xlsx'
OUTPUT_JSON = f'report_data_{TARGET_YEAR}_{TARGET_MONTH:02d}.json'

# 日志配置
LOG_FILE = 'spider.log'
LOG_LEVEL = 'INFO'  # DEBUG, INFO, WARNING, ERROR
