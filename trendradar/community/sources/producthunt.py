# coding=utf-8
"""
ProductHunt 数据源

使用 ProductHunt RSS Feed 获取热门产品
"""

import time
import requests
import feedparser
import re
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime

# 导入降级请求工具
from ..utils.request_utils import fetch_with_fallback


@dataclass
class ProductHuntItem:
    """ProductHunt 产品条目"""
    id: str
    name: str
    tagline: str
    url: str
    votes: int
    comments: int
    posted_at: str
    topics: List[str]
    thumbnail: str = ""
    source: str = "producthunt"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "title": self.name,  # 兼容其他数据源
            "tagline": self.tagline,
            "description": self.tagline,  # 兼容
            "url": self.url,
            "votes": self.votes,
            "comments": self.comments,
            "posted_at": self.posted_at,
            "created_at": self.posted_at,  # 兼容
            "topics": self.topics,
            "thumbnail": self.thumbnail,
            "source": self.source,
        }


class ProductHuntSource:
    """
    ProductHunt 数据源
    
    使用 RSS Feed 获取每日热门产品
    """
    
    # ProductHunt RSS Feed URL
    RSS_URL = "https://www.producthunt.com/feed"
    
    # 备用 RSS 源（第三方）
    FALLBACK_RSS_URLS = [
        "https://rsshub.app/producthunt/today",
    ]
    
    # User-Agent
    USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    
    def __init__(
        self,
        max_items: int = 20,
        proxy_url: str = None,
    ):
        """
        初始化 ProductHunt 数据源
        
        Args:
            max_items: 最大返回条目数
            proxy_url: 代理地址
        """
        self.max_items = max_items
        self.proxy_url = proxy_url
        
        # 配置代理
        self.proxies = None
        if proxy_url:
            self.proxies = {
                "http": proxy_url,
                "https": proxy_url,
            }
        
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": self.USER_AGENT,
            "Accept": "application/rss+xml, application/xml, text/xml, */*",
        })
        if self.proxies:
            self.session.proxies.update(self.proxies)
    
    def fetch(self) -> List[ProductHuntItem]:
        """
        获取 ProductHunt 热门产品
        
        Returns:
            ProductHuntItem 列表
        """
        # 尝试主 RSS
        items = self._fetch_rss(self.RSS_URL)
        
        # 如果失败，尝试备用源
        if not items:
            for fallback_url in self.FALLBACK_RSS_URLS:
                try:
                    items = self._fetch_rss(fallback_url)
                    if items:
                        break
                except:
                    continue
        
        return items[:self.max_items]
    
    def _fetch_rss(self, url: str) -> List[ProductHuntItem]:
        """
        获取 RSS Feed

        Args:
            url: RSS URL

        Returns:
            ProductHuntItem 列表
        """
        # 使用直连优先、代理降级策略
        response, mode = fetch_with_fallback(
            self.session,
            url,
            proxy_url=self.proxy_url,
            timeout=15
        )

        if response is None:
            print(f"[ProductHunt] 获取 RSS 失败 ({url}): 直连和代理都不可用")
            return []

        print(f"[ProductHunt] 获取 RSS 成功 (模式: {mode})")

        try:
            feed = feedparser.parse(response.content)
            items = []

            for entry in feed.entries[:self.max_items]:
                try:
                    item = self._parse_entry(entry)
                    if item:
                        items.append(item)
                except Exception as e:
                    print(f"[ProductHunt] 解析条目失败: {e}")
                    continue

            return items

        except Exception as e:
            print(f"[ProductHunt] 解析 RSS 失败: {e}")
            return []
    
    def _parse_entry(self, entry: dict) -> Optional[ProductHuntItem]:
        """
        解析 RSS 条目
        
        Args:
            entry: feedparser 条目
            
        Returns:
            ProductHuntItem 或 None
        """
        # 提取标题和标语
        title = entry.get("title", "")
        
        # 尝试分离产品名和标语（格式：产品名 - 标语）
        if " – " in title:
            name, tagline = title.split(" – ", 1)
        elif " - " in title:
            name, tagline = title.split(" - ", 1)
        else:
            name = title
            tagline = entry.get("summary", "") or ""
        
        # 提取 ID
        link = entry.get("link", "")
        post_id = link.split("/")[-1] if link else ""
        
        # 解析发布时间
        published = entry.get("published", "")
        try:
            if published:
                dt = parsedate_to_datetime(published)
                posted_at = dt.isoformat()
            else:
                posted_at = datetime.now().isoformat()
        except:
            posted_at = datetime.now().isoformat()
        
        # 提取描述（清理 HTML）
        summary = entry.get("summary", "") or ""
        summary = re.sub(r'<[^>]+>', '', summary)
        if not tagline:
            tagline = summary[:200]
        
        # 提取标签
        topics = []
        for tag in entry.get("tags", []):
            topics.append(tag.get("term", ""))
        
        return ProductHuntItem(
            id=f"producthunt_{post_id or hash(title)}",
            name=name.strip(),
            tagline=tagline.strip()[:200],
            url=link,
            votes=0,  # RSS 不包含投票数
            comments=0,  # RSS 不包含评论数
            posted_at=posted_at,
            topics=topics,
        )
    
    @classmethod
    def from_config(cls, config: dict, proxy_url: str = None) -> "ProductHuntSource":
        """
        从配置创建实例
        
        Args:
            config: producthunt 配置字典
            proxy_url: 代理地址
            
        Returns:
            ProductHuntSource 实例
        """
        return cls(
            max_items=config.get("max_items", 20),
            proxy_url=proxy_url,
        )
