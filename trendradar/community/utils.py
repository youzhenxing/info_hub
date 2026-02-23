# coding=utf-8
"""
社区模块工具函数

包含：
- ClashSSLAdapter: 解决 Clash 代理 TLS 握手问题
- create_clash_session: 创建兼容 Clash 代理的 Session
"""

import ssl
from urllib3.util.ssl_ import create_urllib3_context
from requests.adapters import HTTPAdapter
import requests
import urllib3


class ClashSSLAdapter(HTTPAdapter):
    """
    自定义 SSL Adapter，解决 Clash 代理 TLS 握手问题

    问题：Clash 的 TLS 检查与某些网站（Reddit/Twitter）不兼容
    解决：降低 SSL 安全级别到 SECLEVEL=1

    使用示例：
        session = requests.Session()
        session.mount('https://', ClashSSLAdapter())
        session.proxies = {'http': 'http://127.0.0.1:7897', 'https': 'http://127.0.0.1:7897'}
    """

    def init_poolmanager(self, *args, **kwargs):
        """初始化 PoolManager，使用自定义 SSL 上下文"""
        # 创建自定义 SSL 上下文
        ctx = create_urllib3_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        # 关键：设置 SECLEVEL=1（解决 Clash TLS 问题）
        try:
            ctx.set_ciphers('DEFAULT@SECLEVEL=1')
        except Exception:
            # 如果不支持 SECLEVEL，使用默认配置
            pass

        kwargs['ssl_context'] = ctx
        return super().init_poolmanager(*args, **kwargs)


def create_clash_session(proxy_url=None):
    """
    创建兼容 Clash 代理的 Session

    Args:
        proxy_url: 代理地址，如 http://127.0.0.1:7897

    Returns:
        配置好的 requests.Session 对象，带有自定义 SSL Adapter

    使用示例：
        >>> session = create_clash_session(proxy_url="http://127.0.0.1:7897")
        >>> response = session.get("https://old.reddit.com/r/MachineLearning/.rss")
    """
    # 禁用 SSL 警告
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    session = requests.Session()

    # 挂载自定义 SSL Adapter
    session.mount('https://', ClashSSLAdapter())

    # 配置
    session.verify = False

    if proxy_url:
        session.proxies = {
            'http': proxy_url,
            'https': proxy_url,
        }

    # 设置完整的浏览器 User-Agent
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                      '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
    })

    return session
