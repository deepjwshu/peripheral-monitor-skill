"""
MCP HTTP 客户端 - 调用公司内部 MCP 服务

支持服务：
- web-search-prime: 搜索服务
- web-reader: 网页内容抓取服务
"""
import os
import json
import requests
from typing import Optional, Dict, Any
from dotenv import load_dotenv

load_dotenv()


class MCPHTTPClient:
    """
    MCP HTTP 客户端

    用于调用公司内部部署的 MCP HTTP 服务
    """

    def __init__(self):
        # 从环境变量读取配置
        self.base_url = os.getenv('MCP_BASE_URL', 'http://192.168.0.250:7891')
        self.token = os.getenv('MCP_TOKEN', '')
        self.timeout = int(os.getenv('MCP_TIMEOUT', '30'))
        self.enabled = os.getenv('MCP_SEARCH_ENABLED', 'false').lower() == 'true'

        # 服务端点
        self.search_endpoint = os.getenv(
            'MCP_SEARCH_ENDPOINT',
            f'{self.base_url}/mcp_web_search'
        )
        self.reader_endpoint = os.getenv(
            'MCP_READER_ENDPOINT',
            f'{self.base_url}/mcp_web_reader'
        )

    def is_available(self) -> bool:
        """检查 MCP 服务是否可用"""
        if not self.enabled:
            return False

        if not self.token:
            print("[MCP客户端] 警告: 未配置 MCP_TOKEN，跳过 MCP 调用")
            return False

        return True

    def _call_mcp(self, endpoint: str, method: str, params: Dict) -> Optional[Dict]:
        """
        调用 MCP HTTP 服务

        Args:
            endpoint: 服务端点 URL
            method: MCP 方法名称（如 search/webSearchPrime）
            params: 方法参数

        Returns:
            MCP 返回结果，失败返回 None
        """
        if not self.is_available():
            return None

        # 构造 JSON-RPC 2.0 请求
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}"
        }

        try:
            response = requests.post(
                endpoint,
                json=payload,
                headers=headers,
                timeout=self.timeout
            )
            response.raise_for_status()

            result = response.json()

            # 检查是否有错误
            if "error" in result:
                print(f"[MCP客户端] 服务返回错误: {result['error']}")
                return None

            # 返回结果
            return result.get("result")

        except requests.exceptions.Timeout:
            print(f"[MCP客户端] 请求超时: {endpoint}")
            return None
        except requests.exceptions.RequestException as e:
            print(f"[MCP客户端] 请求失败: {str(e)[:100]}")
            return None
        except Exception as e:
            print(f"[MCP客户端] 未知错误: {str(e)[:100]}")
            return None

    def search(self, query: str, max_results: int = 3) -> Optional[str]:
        """
        执行搜索（使用 web-search-prime）

        Args:
            query: 搜索关键词
            max_results: 最大返回结果数

        Returns:
            搜索结果摘要文本，失败返回 None
        """
        if not self.is_available():
            return None

        result = self._call_mcp(
            endpoint=self.search_endpoint,
            method="search/webSearchPrime",
            params={
                "search_query": query,
                "content_size": "medium",
                "search_recency_filter": "noLimit"
            }
        )

        if not result:
            return None

        # 解析搜索结果
        return self._parse_search_results(result, max_results)

    def _parse_search_results(self, result: Dict, max_results: int) -> str:
        """
        解析搜索结果为纯文本

        Args:
            result: MCP 返回的搜索结果
            max_results: 最多取前 N 个结果

        Returns:
            合并后的纯文本
        """
        try:
            # 根据实际 API 返回格式解析
            # 这里假设返回格式为 {results: [{title, url, content}, ...]}
            results = result.get('results', [])[:max_results]

            texts = []
            for item in results:
                title = item.get('title', '')
                content = item.get('content', '')
                url = item.get('url', '')

                # 组合信息
                text = f"标题: {title}\nURL: {url}\n内容: {content}"
                texts.append(text)

            return '\n\n---\n\n'.join(texts)

        except Exception as e:
            print(f"[MCP客户端] 解析搜索结果失败: {str(e)[:100]}")
            # 尝试直接返回原始结果
            return str(result)

    def read_url(self, url: str) -> Optional[str]:
        """
        抓取网页内容（使用 web-reader）

        Args:
            url: 目标网页 URL

        Returns:
            网页纯文本内容，失败返回 None
        """
        if not self.is_available():
            return None

        result = self._call_mcp(
            endpoint=self.reader_endpoint,
            method="read",
            params={"url": url}
        )

        if not result:
            return None

        # 返回网页内容
        # 根据实际 API 格式调整
        if isinstance(result, str):
            return result
        elif isinstance(result, dict):
            return result.get('content') or result.get('text') or str(result)

        return str(result)


# 创建全局实例（单例模式）
_mcp_client_instance = None


def get_mcp_client() -> MCPHTTPClient:
    """获取 MCP 客户端单例"""
    global _mcp_client_instance
    if _mcp_client_instance is None:
        _mcp_client_instance = MCPHTTPClient()
    return _mcp_client_instance


# 便捷函数
def mcp_search(query: str, max_results: int = 3) -> Optional[str]:
    """
    便捷函数：执行 MCP 搜索

    用法：
        from mcp_client import mcp_search
        result = mcp_search("罗技G304传感器")
    """
    return get_mcp_client().search(query, max_results)


def mcp_read_url(url: str) -> Optional[str]:
    """
    便捷函数：抓取网页内容

    用法：
        from mcp_client import mcp_read_url
        content = mcp_read_url("https://example.com/article")
    """
    return get_mcp_client().read_url(url)
