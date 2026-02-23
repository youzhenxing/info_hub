# coding=utf-8
"""
Twitter/X 数据源

使用 RSS-Bridge 或 Nitter 获取推文
"""

import time
import requests
import feedparser
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlencode, quote


# 导入 Clash 代理工具
try:
    from ..utils import create_clash_session
    CLASH_SUPPORT = True
except ImportError:
    CLASH_SUPPORT = False


@dataclass
class TwitterItem:
    """Twitter 推文"""
    id: str
    content: str
    url: str
    author: str
    author_handle: str
    created_at: str
    retweets: int = 0
    likes: int = 0
    source: str = "twitter"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "content": self.content[:500] if self.content else "",
            "url": self.url,
            "author": self.author,
            "author_handle": self.author_handle,
            "created_at": self.created_at,
            "retweets": self.retweets,
            "likes": self.likes,
            "source": self.source,
        }


class TwitterSource:
    """
    Twitter 数据源
    
    使用 RSS-Bridge 获取推文（不需要官方 API）
    """
    
    # 公共 RSS-Bridge 实例列表（备用）
    PUBLIC_BRIDGES = [
        "https://rss-bridge.org/bridge01/",
        "https://rss.plenio.xyz/",
        "https://wtf.roflcopter.fr/rss-bridge/",
    ]
    
    def __init__(
        self,
        bridge_url: str = None,
        accounts: List[str] = None,
        search_queries: List[str] = None,
        max_items: int = 30,
        request_interval: float = 2.0,
        proxy_url: str = None,
    ):
        """
        初始化 Twitter 数据源

        Args:
            bridge_url: RSS-Bridge URL（留空使用公共实例）
            accounts: 要关注的账号列表（不带 @）
            search_queries: 搜索关键词
            max_items: 最大返回条目数
            request_interval: 请求间隔（秒）
            proxy_url: 代理地址（用于访问 Nitter/Bridge）
        """
        self.bridge_url = bridge_url
        self.accounts = accounts or ["elonmusk"]  # 默认关注马斯克作为测试
        self.search_queries = search_queries or ["AI", "robotics", "startup"]
        self.max_items = max_items
        self.request_interval = request_interval
        self.proxy_url = proxy_url

        # 配置 Session
        if proxy_url and CLASH_SUPPORT:
            # 使用兼容 Clash 的 Session（解决 TLS 问题）
            self.session = create_clash_session(proxy_url=proxy_url)
        else:
            # 使用标准 Session
            self.session = requests.Session()
            self.session.headers.update({
                "User-Agent": "TrendRadar/1.0 (Community Monitor)"
            })
    
    def fetch(self) -> List[TwitterItem]:
        """
        获取 Twitter 内容
        
        策略：
        1. 从关注账号获取最新推文
        2. 使用关键词搜索（如果 Bridge 支持）
        3. 合并去重
        
        Returns:
            TwitterItem 列表
        """
        all_items = []
        seen_ids = set()
        
        # 1. 从关注账号获取推文
        for account in self.accounts:
            try:
                items = self._fetch_user_timeline(account)
                for item in items:
                    if item.id not in seen_ids:
                        seen_ids.add(item.id)
                        all_items.append(item)
                
                time.sleep(self.request_interval)
                
            except Exception as e:
                print(f"[Twitter] 获取 @{account} 失败: {e}")
                continue
        
        # 2. 使用关键词搜索
        for query in self.search_queries:
            try:
                items = self._search(query)
                for item in items:
                    if item.id not in seen_ids:
                        seen_ids.add(item.id)
                        all_items.append(item)
                
                time.sleep(self.request_interval)
                
            except Exception as e:
                print(f"[Twitter] 搜索 '{query}' 失败: {e}")
                continue
        
        # 按时间排序
        all_items.sort(key=lambda x: x.created_at, reverse=True)
        return all_items[:self.max_items]
    
    def _fetch_user_timeline(self, username: str) -> List[TwitterItem]:
        """
        获取用户时间线
        
        使用 RSS-Bridge 的 Twitter Bridge
        
        Args:
            username: Twitter 用户名（不带 @）
            
        Returns:
            TwitterItem 列表
        """
        # RSS-Bridge Twitter 参数
        params = {
            "action": "display",
            "bridge": "TwitterBridge",
            "context": "By username",
            "u": username,
            "format": "Atom",
        }
        
        url = f"{self.bridge_url.rstrip('/')}/?{urlencode(params)}"
        
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            return self._parse_feed(response.text, username)
            
        except Exception as e:
            print(f"[Twitter] RSS-Bridge 请求失败: {e}")
            # 尝试备用 Bridge
            return self._try_fallback_bridges(username)
    
    def _search(self, query: str) -> List[TwitterItem]:
        """
        搜索推文
        
        使用 RSS-Bridge 的搜索功能
        
        Args:
            query: 搜索关键词
            
        Returns:
            TwitterItem 列表
        """
        params = {
            "action": "display",
            "bridge": "TwitterBridge",
            "context": "By keyword or hashtag",
            "q": query,
            "format": "Atom",
        }
        
        url = f"{self.bridge_url.rstrip('/')}/?{urlencode(params)}"
        
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            return self._parse_feed(response.text, query)
            
        except Exception as e:
            print(f"[Twitter] 搜索失败: {e}")
            return []
    
    def _try_fallback_bridges(self, username: str) -> List[TwitterItem]:
        """
        尝试备用 RSS-Bridge 实例
        
        Args:
            username: Twitter 用户名
            
        Returns:
            TwitterItem 列表
        """
        for bridge_url in self.PUBLIC_BRIDGES:
            if bridge_url == self.bridge_url:
                continue
            
            try:
                params = {
                    "action": "display",
                    "bridge": "TwitterBridge",
                    "context": "By username",
                    "u": username,
                    "format": "Atom",
                }
                
                url = f"{bridge_url.rstrip('/')}/?{urlencode(params)}"
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                
                items = self._parse_feed(response.text, username)
                if items:
                    print(f"[Twitter] 使用备用 Bridge: {bridge_url}")
                    return items
                    
            except Exception:
                continue
        
        return []
    
    def _parse_feed(self, feed_content: str, source: str) -> List[TwitterItem]:
        """
        解析 RSS/Atom feed
        
        Args:
            feed_content: Feed XML 内容
            source: 来源标识
            
        Returns:
            TwitterItem 列表
        """
        feed = feedparser.parse(feed_content)
        items = []
        
        for entry in feed.entries[:20]:
            try:
                # 提取推文 ID
                entry_id = entry.get("id", entry.get("link", ""))
                tweet_id = entry_id.split("/")[-1] if "/" in entry_id else entry_id
                
                # 提取作者信息
                author = entry.get("author", source)
                author_handle = source if "@" not in source else source
                
                # 解析内容（去除 HTML 标签）
                content = entry.get("summary", entry.get("title", ""))
                content = self._strip_html(content)
                
                # 解析时间
                created_at = entry.get("published", entry.get("updated", ""))
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    created_at = datetime(*entry.published_parsed[:6]).isoformat()
                
                item = TwitterItem(
                    id=f"twitter_{tweet_id}",
                    content=content,
                    url=entry.get("link", ""),
                    author=author,
                    author_handle=author_handle,
                    created_at=created_at,
                )
                items.append(item)
                
            except Exception as e:
                print(f"[Twitter] 解析条目失败: {e}")
                continue
        
        return items
    
    def _strip_html(self, text: str) -> str:
        """移除 HTML 标签"""
        import re
        clean = re.compile('<.*?>')
        return re.sub(clean, '', text).strip()
    
    @classmethod
    def from_config(cls, config: dict, proxy_url: str = None) -> "TwitterSource":
        """
        从配置创建实例

        Args:
            config: twitter 配置字典
            proxy_url: 代理地址

        Returns:
            TwitterSource 实例
        """
        return cls(
            bridge_url=config.get("bridge_url"),
            accounts=config.get("accounts"),
            search_queries=config.get("search_queries"),
            max_items=config.get("max_items", 30),
            request_interval=config.get("request_interval", 2.0),
            proxy_url=proxy_url,  # 传递代理配置
        )
