# coding=utf-8
"""
网络请求工具 - 支持直连优先、代理降级策略

用于社区模块的数据源请求，优先使用直连，失败时自动降级使用代理。
"""

import requests
from typing import Optional, Tuple, Dict, Any


def fetch_with_fallback(
    session: requests.Session,
    url: str,
    proxy_url: Optional[str] = None,
    timeout: int = 15,
    method: str = "GET",
    **kwargs
) -> Tuple[Optional[requests.Response], str]:
    """
    直连优先、代理降级的请求策略

    Args:
        session: requests Session 对象
        url: 请求 URL
        proxy_url: 代理地址（如 http://host.docker.internal:7897）
        timeout: 超时时间（秒）
        method: HTTP 方法（GET/POST）
        **kwargs: 传递给 session.request 的其他参数

    Returns:
        (response, mode):
            - response: 响应对象，失败时为 None
            - mode: "direct"（直连成功）/ "proxy"（代理成功）/ "failed"（都失败）
    """
    # 保存原始代理配置
    original_proxies = session.proxies.copy()

    # 1. 优先尝试直连
    try:
        # 临时移除代理
        session.proxies.clear()

        response = session.request(method, url, timeout=timeout, **kwargs)
        response.raise_for_status()

        # 恢复原始代理配置
        session.proxies.update(original_proxies)
        return response, "direct"

    except Exception as direct_error:
        # 2. 直连失败，尝试代理降级
        if proxy_url:
            try:
                # 配置代理
                session.proxies.update({
                    "http": proxy_url,
                    "https": proxy_url,
                })

                response = session.request(method, url, timeout=timeout, **kwargs)
                response.raise_for_status()

                return response, "proxy"

            except Exception as proxy_error:
                # 恢复原始代理配置
                session.proxies.clear()
                session.proxies.update(original_proxies)

                print(f"  [请求失败] 直连: {str(direct_error)[:50]}...")
                print(f"  [请求失败] 代理: {str(proxy_error)[:50]}...")
                return None, "failed"

        # 没有代理配置，直连失败即失败
        session.proxies.update(original_proxies)
        print(f"  [请求失败] 直连: {str(direct_error)[:60]}...")
        return None, "failed"


def fetch_with_retry(
    session: requests.Session,
    url: str,
    proxy_url: Optional[str] = None,
    timeout: int = 15,
    max_retries: int = 3,
    retry_delay: float = 2.0,
    **kwargs
) -> Tuple[Optional[requests.Response], str]:
    """
    带重试的请求（直连优先、代理降级）

    Args:
        session: requests Session 对象
        url: 请求 URL
        proxy_url: 代理地址
        timeout: 超时时间
        max_retries: 最大重试次数
        retry_delay: 重试间隔（秒）
        **kwargs: 传递给 fetch_with_fallback 的其他参数

    Returns:
        (response, mode): 同 fetch_with_fallback
    """
    import time

    last_mode = "failed"
    last_response = None

    for attempt in range(max_retries):
        response, mode = fetch_with_fallback(
            session, url, proxy_url, timeout, **kwargs
        )

        if response is not None:
            return response, mode

        last_mode = mode

        if attempt < max_retries - 1:
            time.sleep(retry_delay)

    return last_response, last_mode
