"""
外设资讯自动化采集与清洗工具 (v1.0)
项目代号: Peripherals-Hunter

目标网站:
- in外设 (inwaishe.com)
- 外设天下 (wstx.com)
"""

import sys
import time
import random
import logging
import re
from datetime import datetime
from pathlib import Path
import requests
from bs4 import BeautifulSoup
import pandas as pd
from typing import Dict, List, Optional, Generator
import config


class SpiderLogger:
    """日志处理器"""

    @staticmethod
    def setup():
        """配置日志系统"""
        # 确保输出目录存在
        from pathlib import Path
        Path(config.OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

        logging.basicConfig(
            level=getattr(logging, config.LOG_LEVEL),
            format='%(asctime)s [%(levelname)s] %(message)s',
            handlers=[
                logging.FileHandler(config.OUTPUT_DIR + '/' + config.LOG_FILE, encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        return logging.getLogger(__name__)


logger = SpiderLogger.setup()


class BaseSpider:
    """爬虫基类"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': config.USER_AGENT,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        })
        self.target_date = datetime(config.TARGET_YEAR, config.TARGET_MONTH, 1)

    def random_delay(self):
        """
        随机延时，避免被封

        使用 SPIDER_DELAY_SECONDS + SPIDER_DELAY_JITTER 配置
        降级支持旧的 MIN_DELAY/MAX_DELAY（向后兼容）
        """
        # 优先使用新的统一配置
        if hasattr(config, 'SPIDER_DELAY_SECONDS'):
            base_delay = config.SPIDER_DELAY_SECONDS
            jitter = getattr(config, 'SPIDER_DELAY_JITTER', 1.0)
            delay = base_delay + random.uniform(-jitter, jitter)
            delay = max(0, delay)  # 确保非负
        else:
            # 降级使用旧配置
            delay = random.uniform(config.MIN_DELAY, config.MAX_DELAY)

        logger.debug(f"延时 {delay:.2f} 秒...")
        time.sleep(delay)

    def request(self, url: str, max_retries: int = 3) -> Optional[requests.Response]:
        """发送 HTTP 请求"""
        for attempt in range(max_retries):
            try:
                response = self.session.get(url, timeout=config.REQUEST_TIMEOUT)
                response.encoding = response.apparent_encoding
                return response
            except Exception as e:
                logger.warning(f"请求失败 (尝试 {attempt + 1}/{max_retries}): {url}")
                logger.warning(f"错误: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2)
        logger.error(f"请求最终失败: {url}")
        return None

    def compare_date(self, article_date: datetime) -> str:
        """
        比较文章日期与目标日期

        Returns:
            'skip': 晚于目标月份，跳过
            'stop': 早于目标月份，停止抓取
            'keep': 属于目标月份，保留
        """
        if article_date.year > self.target_date.year:
            return 'skip'
        elif article_date.year < self.target_date.year:
            return 'stop'
        else:
            if article_date.month > self.target_date.month:
                return 'skip'
            elif article_date.month < self.target_date.month:
                return 'stop'
            else:
                return 'keep'

    def parse_date(self, date_str: str) -> Optional[datetime]:
        """解析日期字符串"""
        # 常见日期格式
        formats = [
            '%Y-%m-%d %H:%M',
            '%Y-%m-%d',
            '%Y-%m-%d %H:%M:%S',
            '%Y/%m/%d %H:%M',
            '%Y/%m/%d',
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue

        logger.warning(f"无法解析日期: {date_str}")
        return None


class InwaisheSpider(BaseSpider):
    """in外设 爬虫"""

    BASE_URL = 'http://www.inwaishe.com'
    LIST_URL_TEMPLATE = f'{BASE_URL}/portal.php?mod=list&catid=1&page={{page}}'

    def get_article_urls(self, page: int) -> Generator[str, None, None]:
        """从列表页获取文章链接"""
        url = self.LIST_URL_TEMPLATE.format(page=page)
        logger.info(f"正在访问列表页 (第 {page} 页): {url}")

        response = self.request(url)
        if not response:
            return

        soup = BeautifulSoup(response.text, 'lxml')

        # 查找文章链接，使用集合去重
        seen_urls = set()
        # in外设的文章链接通常在 .bm_c 或类似容器中
        for link in soup.find_all('a', href=True):
            href = link.get('href')

            # 匹配文章详情页链接 pattern
            if href and ('article-' in href or 'portal.php?mod=view&aid=' in href):
                # 处理相对路径
                if href.startswith('/'):
                    full_url = self.BASE_URL + href
                elif not href.startswith('http'):
                    full_url = self.BASE_URL + '/' + href
                else:
                    full_url = href

                # 去重：只保留唯一的URL
                if full_url not in seen_urls:
                    seen_urls.add(full_url)
                    yield full_url

        self.random_delay()

    def parse_article(self, url: str) -> Optional[Dict]:
        """解析文章详情页"""
        response = self.request(url)
        if not response:
            return None

        soup = BeautifulSoup(response.text, 'lxml')

        try:
            # 提取发布时间
            publish_time = None
            time_element = soup.find('span', class_='xg1') or soup.find('em', class_='xg1')

            if time_element:
                time_text = time_element.get_text(strip=True)
                publish_time = self.parse_date(time_text)

            if not publish_time:
                logger.warning(f"无法提取发布时间: {url}")
                return None

            # 判断是否为目标月份
            action = self.compare_date(publish_time)

            if action == 'skip':
                logger.debug(f"跳过 (晚于目标月份): {soup.title.get_text(strip=True) if soup.title else url} - {publish_time}")
                return None
            elif action == 'stop':
                logger.info(f"遇到早于目标月份的文章，停止抓取: {publish_time}")
                return 'STOP'

            # 提取标题
            title = ''
            title_elem = soup.find('h1') or soup.find('h2', class_='ph') or soup.find('title')
            if title_elem:
                title = title_elem.get_text(strip=True)

            # 提取作者
            author = ''
            author_elem = soup.find('a', class_='xw1') or soup.find('a', href=lambda x: x and 'uid=' in x)
            if author_elem:
                author = author_elem.get_text(strip=True)

            # 提取正文内容
            content_elem = soup.find('td', id=lambda x: x and x.startswith('article_content')) or \
                          soup.find('div', class_='d') or \
                          soup.find('div', class_='content')

            content_text = ''
            content_html = ''

            if content_elem:
                # 保留换行符的纯文本
                content_text = content_elem.get_text('\n', strip=True)
                # HTML 内容
                content_html = str(content_elem)

            # 提取图片链接（只取第一张）
            images = []
            if content_elem:
                first_img = content_elem.find('img', src=True)
                if first_img:
                    img_src = first_img.get('src')
                    if img_src:
                        if img_src.startswith('//'):
                            img_src = 'http:' + img_src
                        elif img_src.startswith('/'):
                            img_src = self.BASE_URL + img_src
                        images.append(img_src)

            data = {
                'source': 'in外设',
                'title': title,
                'publish_date': publish_time.strftime('%Y-%m-%d %H:%M:%S'),
                'url': url,
                'author': author,
                'content_text': content_text,
                'content_html': content_html,
                'images': images
            }

            logger.info(f"✓ 采集: {title} - {publish_time}")
            return data

        except Exception as e:
            logger.error(f"解析文章失败: {url}")
            logger.error(f"错误: {e}")
            return None


class WstxSpider(BaseSpider):
    """外设天下 爬虫"""

    BASE_URL = 'https://www.wstx.com'

    def get_article_urls(self, page: int) -> Generator[str, None, None]:
        """从列表页获取文章链接"""
        # 正确的URL模式：https://www.wstx.com/news/1, /news/2, /news/3...
        url = f'{self.BASE_URL}/news/{page}'

        logger.info(f"正在访问列表页 (第 {page} 页): {url}")

        response = self.request(url)
        if not response:
            return

        soup = BeautifulSoup(response.text, 'lxml')

        # 查找文章链接，使用集合去重
        seen_urls = set()

        # 外设天下的文章链接特征: /p-{id}-1 格式
        for link in soup.find_all('a', href=True):
            href = link.get('href')

            # 匹配文章详情页链接 pattern: /p-数字-1
            if href and href.startswith('/p-') and href.endswith('-1'):
                # 进一步验证格式: /p-{数字}-1
                if re.match(r'^/p-\d+-1$', href):
                    # 处理相对路径
                    if href.startswith('/'):
                        full_url = self.BASE_URL + href
                    elif not href.startswith('http'):
                        full_url = self.BASE_URL + '/' + href
                    else:
                        full_url = href

                    # 去重：只保留唯一的URL
                    if full_url not in seen_urls:
                        seen_urls.add(full_url)
                        yield full_url

        self.random_delay()

    def parse_article(self, url: str) -> Optional[Dict]:
        """解析文章详情页"""
        response = self.request(url)
        if not response:
            return None

        soup = BeautifulSoup(response.text, 'lxml')

        try:
            # 提取发布时间 - 必须从详情页获取
            publish_time = None

            # 尝试多种时间定位方式
            # 外设天下的时间在 <span class="author"> 中，格式：作者：xxx|发布时间：2026-01-21 10:03:37
            time_selectors = [
                ('span', {'class': 'author'}),  # 外设天下专用
                ('div', {'class': 'artTime'}),   # 备用：父容器
                ('span', {'class': 'info'}),
                ('span', {'class': 'property'}),
                ('div', {'class': 'info'}),
                ('div', {'class': 'property'}),
                ('p', {'class': 'info'}),
            ]

            for tag, attrs in time_selectors:
                time_elem = soup.find(tag, attrs)
                if time_elem:
                    time_text = time_elem.get_text(strip=True)
                    # 提取日期时间部分 (支持格式：2026-01-21 10:03:37)
                    date_match = re.search(r'\d{4}[-/]\d{1,2}[-/]\d{1,2}(?:\s+\d{1,2}:\d{1,2}(?::\d{1,2})?)?', time_text)
                    if date_match:
                        publish_time = self.parse_date(date_match.group())
                        break

            if not publish_time:
                logger.warning(f"无法提取发布时间: {url}")
                return None

            # 判断是否为目标月份
            action = self.compare_date(publish_time)

            if action == 'skip':
                logger.debug(f"跳过 (晚于目标月份): {soup.title.get_text(strip=True) if soup.title else url} - {publish_time}")
                return None
            elif action == 'stop':
                logger.info(f"遇到早于目标月份的文章，停止抓取: {publish_time}")
                return 'STOP'

            # 提取标题
            title = ''
            title_elem = soup.find('h1') or soup.find('h2') or soup.find('title')
            if title_elem:
                title = title_elem.get_text(strip=True)

            # 提取作者
            author = ''
            author_elem = soup.find('a', href=lambda x: x and 'uid=' in x) or \
                         soup.find('span', class_='author')
            if author_elem:
                author = author_elem.get_text(strip=True)

            # 提取正文内容
            content_elem = soup.find('div', class_='articleNr') or \
                          soup.find('div', class_='content') or \
                          soup.find('div', id='content') or \
                          soup.find('div', class_='article-content')

            content_text = ''
            content_html = ''

            if content_elem:
                # 保留换行符的纯文本
                content_text = content_elem.get_text('\n', strip=True)
                # HTML 内容
                content_html = str(content_elem)

            # 提取图片链接（只取第一张）
            images = []
            if content_elem:
                first_img = content_elem.find('img', src=True)
                if first_img:
                    img_src = first_img.get('src')
                    if img_src:
                        if img_src.startswith('//'):
                            img_src = 'https:' + img_src
                        elif img_src.startswith('/'):
                            img_src = self.BASE_URL + img_src
                        images.append(img_src)

            data = {
                'source': '外设天下',
                'title': title,
                'publish_date': publish_time.strftime('%Y-%m-%d %H:%M:%S'),
                'url': url,
                'author': author,
                'content_text': content_text,
                'content_html': content_html,
                'images': images
            }

            logger.info(f"✓ 采集: {title} - {publish_time}")
            return data

        except Exception as e:
            logger.error(f"解析文章失败: {url}")
            logger.error(f"错误: {e}")
            return None


class DataExporter:
    """数据导出器"""

    def __init__(self):
        self.output_dir = Path(config.OUTPUT_DIR)
        self.output_dir.mkdir(exist_ok=True)

    def export_to_excel(self, data: List[Dict], filename: str = None):
        """导出到 Excel"""
        if not filename:
            filename = config.OUTPUT_EXCEL

        filepath = self.output_dir / filename

        df = pd.DataFrame(data)

        # 重新排列列顺序
        columns_order = ['source', 'title', 'publish_date', 'url', 'author',
                        'content_text', 'content_html', 'images']
        df = df.reindex(columns=columns_order, fill_value='')

        df.to_excel(filepath, index=False, engine='openpyxl')
        logger.info(f"数据已导出到: {filepath}")
        logger.info(f"共导出 {len(data)} 条记录")

    def export_to_json(self, data: List[Dict], filename: str = None):
        """导出到 JSON"""
        if not filename:
            filename = config.OUTPUT_JSON

        filepath = self.output_dir / filename

        import json
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"数据已导出到: {filepath}")


def run_spider(spider_class, spider_name: str, max_pages: int = 50):
    """运行爬虫"""
    logger.info(f"\n{'='*60}")
    logger.info(f"开始抓取: {spider_name}")
    logger.info(f"目标月份: {config.TARGET_YEAR}-{config.TARGET_MONTH:02d}")
    logger.info(f"{'='*60}\n")

    spider = spider_class()
    all_data = []

    for page in range(1, max_pages + 1):
        logger.info(f"\n--- 第 {page} 页 ---")

        # 获取该页的所有文章链接
        article_urls = list(spider.get_article_urls(page))

        if not article_urls:
            logger.warning(f"第 {page} 页没有找到文章链接")
            continue

        logger.info(f"找到 {len(article_urls)} 个链接")

        # 逐个访问详情页
        stop_signal = False
        for url in article_urls:
            spider.random_delay()

            result = spider.parse_article(url)

            if result == 'STOP':
                # 遇到早于目标月份的文章，停止整个爬虫
                logger.info(f"收到停止信号，结束抓取")
                stop_signal = True
                break
            elif result:
                all_data.append(result)

        if stop_signal:
            break

    logger.info(f"\n{spider_name} 抓取完成，共获取 {len(all_data)} 条数据\n")

    return all_data


def run_spider_all(target_year: int = None, target_month: int = None, max_pages: int = 20) -> List[Dict]:
    """
    运行所有爬虫并返回数据

    Args:
        target_year: 目标年份（None 则使用 config 配置）
        target_month: 目标月份（None 则使用 config 配置）
        max_pages: 最大抓取页数

    Returns:
        List[Dict]: 抓取到的文章数据列表
    """
    # 如果指定了年月，更新配置
    if target_year is not None and target_month is not None:
        config.TARGET_YEAR = target_year
        config.TARGET_MONTH = target_month
        config.OUTPUT_EXCEL = f'report_data_{target_year}_{target_month:02d}.xlsx'
        config.OUTPUT_JSON = f'report_data_{target_year}_{target_month:02d}.json'

    print(f"目标月份: {config.TARGET_YEAR}-{config.TARGET_MONTH:02d}")
    print(f"输出目录: {config.OUTPUT_DIR}/")
    print("-" * 60)

    # 创建输出目录
    Path(config.OUTPUT_DIR).mkdir(exist_ok=True)

    # 运行爬虫
    all_articles = []

    # in外设
    try:
        inwaishe_data = run_spider(InwaisheSpider, "in外设", max_pages=max_pages)
        all_articles.extend(inwaishe_data)
    except Exception as e:
        logger.error(f"in外设 抓取出错: {e}")

    # 外设天下
    try:
        wstx_data = run_spider(WstxSpider, "外设天下", max_pages=max_pages)
        all_articles.extend(wstx_data)
    except Exception as e:
        logger.error(f"外设天下 抓取出错: {e}")

    return all_articles


def main(export: bool = True):
    """
    主函数

    Args:
        export: 是否导出数据到文件（默认 True）
    """
    print(r"""
    ╔═══════════════════════════════════════════════════════╗
    ║   外设资讯自动化采集与清洗工具 v1.0                  ║
    ║   Peripherals-Hunter                                 ║
    ╚═══════════════════════════════════════════════════════╝
    """)

    # 运行爬虫
    all_articles = run_spider_all()

    # 导出数据
    if export:
        if all_articles:
            exporter = DataExporter()

            logger.info(f"\n{'='*60}")
            logger.info(f"开始导出数据")
            logger.info(f"{'='*60}\n")

            exporter.export_to_excel(all_articles)
            exporter.export_to_json(all_articles)

            print(f"\n{'='*60}")
            print(f"✓ 抓取完成！")
            print(f"✓ 共采集 {len(all_articles)} 条文章")
            print(f"✓ 数据已保存到: {config.OUTPUT_DIR}/")
            print(f"{'='*60}\n")
        else:
            logger.warning("没有采集到任何数据")
    else:
        # 不导出，仅返回数据
        return all_articles


if __name__ == '__main__':
    main()
