# coding=utf-8
"""
Reddit 数据源

使用 Reddit RSS Feed 获取热门内容（比 JSON API 更稳定）
支持代理配置
"""

import time
import requests
import feedparser
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime

# 导入降级请求工具
from ..utils.request_utils import fetch_with_retry

# 导入 Clash 代理工具
try:
    from ..utils import create_clash_session
    CLASH_SUPPORT = True
except ImportError:
    CLASH_SUPPORT = False


@dataclass
class RedditItem:
    """Reddit 条目"""
    id: str
    title: str
    url: str
    score: int
    comments: int
    author: str
    subreddit: str
    created_at: str
    selftext: str = ""
    source: str = "reddit"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "url": self.url,
            "score": self.score,
            "comments": self.comments,
            "author": self.author,
            "subreddit": self.subreddit,
            "created_at": self.created_at,
            "selftext": self.selftext[:2000] if self.selftext else "",  # 提升到 2000 字符
            "source": self.source,
        }


class RedditSource:
    """
    Reddit 数据源
    
    使用 Reddit RSS Feed 获取热门内容（比 JSON API 更稳定，不易被拦截）
    """
    
    BASE_URL = "https://old.reddit.com"  # 使用 old 版本避免 403 封锁
    
    # 浏览器 User-Agent（避免被 Reddit 拦截）
    USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    
    def __init__(
        self,
        subreddits: List[Dict[str, Any]] = None,
        search_keywords: List[str] = None,
        search_time: str = "day",
        sort: str = "hot",
        max_items: int = 50,
        min_score: int = 5,
        request_interval: float = 1.0,
        proxy_url: str = None,
    ):
        """
        初始化 Reddit 数据源
        
        Args:
            subreddits: Subreddit 配置列表 [{"name": "MachineLearning", "limit": 15}]
            search_keywords: 全站搜索关键词（可选）
            search_time: 搜索时间范围 (hour/day/week/month/year/all)
            sort: 排序方式 (hot/new/top/relevance)
            max_items: 最大返回条目数
            min_score: 最低分数过滤（RSS 无法获取分数，此参数仅用于备用）
            request_interval: 请求间隔（秒）
            proxy_url: 代理地址（如 http://127.0.0.1:7897）
        """
        self.subreddits = subreddits or [
            {"name": "MachineLearning", "limit": 15},
            {"name": "artificial", "limit": 15},
            {"name": "robotics", "limit": 10},
            {"name": "startups", "limit": 10},
            {"name": "venturecapital", "limit": 10},
        ]
        self.search_keywords = search_keywords or ["AI", "LLM", "robotics", "startup"]
        self.search_time = search_time
        self.sort = sort
        self.max_items = max_items
        self.min_score = min_score
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
                "User-Agent": self.USER_AGENT,
                "Accept": "application/rss+xml, application/xml, text/xml, */*",
                "Accept-Language": "en-US,en;q=0.9",
            })

            # 配置代理
            if proxy_url:
                self.proxies = {
                    "http": proxy_url,
                    "https": proxy_url,
                }
                self.session.proxies.update(self.proxies)
    
    def fetch(self) -> List[RedditItem]:
        """
        获取 Reddit 热门内容
        
        策略：
        1. 从配置的 subreddit 获取 RSS feed
        2. 合并去重
        
        Returns:
            RedditItem 列表
        """
        all_items = []
        seen_ids = set()
        
        # 从各 subreddit 获取 RSS feed
        for sub_config in self.subreddits:
            try:
                items = self._fetch_subreddit_rss(
                    sub_config["name"],
                    limit=sub_config.get("limit", 15),
                )
                for item in items:
                    if item.id not in seen_ids:
                        seen_ids.add(item.id)
                        all_items.append(item)
                
                time.sleep(self.request_interval)
                
            except Exception as e:
                print(f"[Reddit] 获取 r/{sub_config['name']} 失败: {e}")
                continue
        
        # 截取最大条目数
        return all_items[:self.max_items]
    
    def _fetch_subreddit_rss(self, subreddit: str, limit: int = 25) -> List[RedditItem]:
        """
        获取 subreddit 的 RSS feed（直连优先、代理降级）

        Args:
            subreddit: Subreddit 名称
            limit: 最大条目数

        Returns:
            RedditItem 列表
        """
        # 使用 old.reddit.com（避免 403）
        url = f"{self.BASE_URL}/r/{subreddit}/.rss?limit={limit}"

        # 使用直连优先、代理降级策略（带重试）
        response, mode = fetch_with_retry(
            self.session,
            url,
            proxy_url=self.proxy_url,
            timeout=15,
            max_retries=3,
            retry_delay=2.0
        )

        if response is None:
            print(f"[Reddit] r/{subreddit} 请求失败: 直连和代理都不可用")
            return []

        print(f"[Reddit] r/{subreddit} 请求成功 (模式: {mode})")

        try:
            # 解析 RSS feed
            feed = feedparser.parse(response.content)
            items = []

            for entry in feed.entries[:limit]:
                try:
                    item = self._parse_entry(entry, subreddit)
                    if item:
                        items.append(item)
                except Exception as e:
                    print(f"[Reddit] 解析条目失败: {e}")
                    continue

            return items

        except Exception as e:
            print(f"[Reddit] 解析 RSS 失败: {e}")
            return []

    def _parse_entry(self, entry: dict, subreddit: str) -> Optional[RedditItem]:
        """
        解析 RSS 条目

        Args:
            entry: feedparser 条目
            subreddit: Subreddit 名称

        Returns:
            RedditItem 或 None
        """
        import re
        from html import unescape

        # 提取帖子 ID
        post_id = entry.get("id", "").split("/")[-1] or entry.get("link", "").split("/")[-2]

        # 解析发布时间
        published = entry.get("published", "")
        try:
            if published:
                dt = parsedate_to_datetime(published)
                created_at = dt.isoformat()
            else:
                created_at = datetime.now().isoformat()
        except:
            created_at = datetime.now().isoformat()

        # 提取作者（格式：/u/username）
        author = entry.get("author", "")
        if author.startswith("/u/"):
            author = author[3:]

        # 提取完整内容（优先使用 content 字段，而非 summary）
        content_elem = entry.get("content", [{}])[0].get("value", "")
        summary_elem = entry.get("summary", "")

        # 使用完整的 content，如果没有才用 summary
        raw_content = content_elem if content_elem else summary_elem

        # 清理 HTML 但保留更多内容（2000 字符）
        content = unescape(raw_content)
        content = re.sub(r'</p>', '\n\n', content)
        content = re.sub(r'<br\s*/?>', '\n', content)
        content = re.sub(r'<[^>]+>', '', content)
        content = content[:2000].strip()

        return RedditItem(
            id=f"reddit_{post_id}",
            title=entry.get("title", ""),
            url=entry.get("link", ""),
            score=0,  # Atom Feed 不包含分数
            comments=0,  # Atom Feed 不包含评论数
            author=author,
            subreddit=subreddit,
            created_at=created_at,
            selftext=content,
        )
    
    @classmethod
    def from_config(cls, config: dict, proxy_url: str = None) -> "RedditSource":
        """
        从配置创建实例
        
        Args:
            config: reddit 配置字典
            proxy_url: 代理地址
            
        Returns:
            RedditSource 实例
        """
        return cls(
            subreddits=config.get("subreddits"),
            search_keywords=config.get("search_keywords"),
            search_time=config.get("search_time", "day"),
            sort=config.get("sort", "hot"),
            max_items=config.get("max_items", 50),
            min_score=config.get("min_score", 5),
            request_interval=config.get("request_interval", 1.0),
            proxy_url=proxy_url,
        )
