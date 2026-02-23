# coding=utf-8
"""
Kickstarter 数据源

使用 Kickstarter Discover API 和 RSS 获取热门项目
"""

import time
import requests
import feedparser
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime


@dataclass
class KickstarterItem:
    """Kickstarter 项目"""
    id: str
    name: str
    blurb: str
    url: str
    category: str
    pledged: float
    goal: float
    backers: int
    created_at: str
    currency: str = "USD"
    state: str = "live"
    source: str = "kickstarter"
    
    @property
    def funded_percent(self) -> float:
        """资金完成百分比"""
        if self.goal > 0:
            return round((self.pledged / self.goal) * 100, 1)
        return 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "blurb": self.blurb,
            "url": self.url,
            "category": self.category,
            "pledged": self.pledged,
            "goal": self.goal,
            "backers": self.backers,
            "funded_percent": self.funded_percent,
            "created_at": self.created_at,
            "currency": self.currency,
            "state": self.state,
            "source": self.source,
        }


class KickstarterSource:
    """
    Kickstarter 数据源
    
    使用 Discover API 获取热门项目
    """
    
    DISCOVER_API = "https://www.kickstarter.com/discover/advanced"
    RSS_URL = "https://www.kickstarter.com/discover/categories/{category}.atom"
    
    # 分类 ID 映射
    CATEGORY_IDS = {
        "technology": 16,
        "robots": 337,  # Technology > Robots
        "hardware": 335,  # Technology > Hardware
        "software": 338,  # Technology > Software
        "gadgets": 334,  # Technology > Gadgets
        "design": 7,
        "games": 12,
    }
    
    def __init__(
        self,
        categories: List[str] = None,
        search_keywords: List[str] = None,
        max_items: int = 20,
        sort: str = "magic",
        request_interval: float = 1.0,
    ):
        """
        初始化 Kickstarter 数据源
        
        Args:
            categories: 要监控的分类列表
            search_keywords: 搜索关键词
            max_items: 最大返回条目数
            sort: 排序方式 (magic/popularity/newest/end_date/most_funded)
            request_interval: 请求间隔（秒）
        """
        self.categories = categories or ["technology", "robots"]
        self.search_keywords = search_keywords or ["AI", "robot", "hardware"]
        self.max_items = max_items
        self.sort = sort
        self.request_interval = request_interval
        
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
        })
    
    def fetch(self) -> List[KickstarterItem]:
        """
        获取 Kickstarter 热门项目
        
        策略：
        1. 从配置的分类获取热门项目
        2. 使用关键词搜索
        3. 合并去重
        
        Returns:
            KickstarterItem 列表
        """
        all_items = []
        seen_ids = set()
        
        # 1. 从各分类获取热门项目
        for category in self.categories:
            try:
                items = self._fetch_category(category)
                for item in items:
                    if item.id not in seen_ids:
                        seen_ids.add(item.id)
                        all_items.append(item)
                
                time.sleep(self.request_interval)
                
            except Exception as e:
                print(f"[Kickstarter] 获取分类 '{category}' 失败: {e}")
                continue
        
        # 2. 使用关键词搜索
        for keyword in self.search_keywords:
            try:
                items = self._search(keyword)
                for item in items:
                    if item.id not in seen_ids:
                        seen_ids.add(item.id)
                        all_items.append(item)
                
                time.sleep(self.request_interval)
                
            except Exception as e:
                print(f"[Kickstarter] 搜索 '{keyword}' 失败: {e}")
                continue
        
        # 按资金完成度排序
        all_items.sort(key=lambda x: x.funded_percent, reverse=True)
        return all_items[:self.max_items]
    
    def _fetch_category(self, category: str, limit: int = 15) -> List[KickstarterItem]:
        """
        获取分类的热门项目
        
        Args:
            category: 分类名称
            limit: 最大条目数
            
        Returns:
            KickstarterItem 列表
        """
        # 直接使用 RSS，因为 API 经常被限制
        return self._fetch_category_rss(category)
    
    def _fetch_category_rss(self, category: str) -> List[KickstarterItem]:
        """
        通过 RSS 获取分类项目
        
        使用多个 RSS 源尝试获取
        
        Args:
            category: 分类名称
            
        Returns:
            KickstarterItem 列表
        """
        category_id = self.CATEGORY_IDS.get(category, category)
        
        # 尝试多个 RSS 源
        rss_urls = [
            f"https://www.kickstarter.com/discover/categories/{category_id}.atom",
            f"https://www.kickstarter.com/discover/advanced.atom?category_id={category_id}&sort=magic",
        ]
        
        for url in rss_urls:
            try:
                response = self.session.get(url, timeout=15)
                if response.status_code != 200:
                    continue
                    
                feed = feedparser.parse(response.text)
                if not feed.entries:
                    continue
                    
                items = []
                for entry in feed.entries[:15]:
                    item = KickstarterItem(
                        id=f"ks_{entry.get('id', '')}",
                        name=entry.get("title", ""),
                        blurb=entry.get("summary", "")[:300],
                        url=entry.get("link", ""),
                        category=category,
                        pledged=0,
                        goal=0,
                        backers=0,
                        created_at=entry.get("published", ""),
                    )
                    items.append(item)
                
                if items:
                    return items
                    
            except Exception as e:
                continue
        
        print(f"[Kickstarter] 所有 RSS 源获取失败: {category}")
        return []
    
    def _search(self, keyword: str, limit: int = 15) -> List[KickstarterItem]:
        """
        搜索项目
        
        由于 API 限制，搜索功能暂时禁用
        
        Args:
            keyword: 搜索关键词
            limit: 最大条目数
            
        Returns:
            KickstarterItem 列表（空列表，因为搜索被限制）
        """
        # Kickstarter 的 API 经常返回 403，搜索功能暂时跳过
        # 主要依赖分类获取
        return []
    
    def _parse_projects(self, projects: List[dict]) -> List[KickstarterItem]:
        """
        解析项目数据
        
        Args:
            projects: Kickstarter API 返回的项目列表
            
        Returns:
            KickstarterItem 列表
        """
        items = []
        
        for project in projects:
            try:
                # 提取分类信息
                category = project.get("category", {})
                category_name = category.get("name", "") if isinstance(category, dict) else str(category)
                
                item = KickstarterItem(
                    id=f"ks_{project.get('id')}",
                    name=project.get("name", ""),
                    blurb=project.get("blurb", "")[:300],
                    url=project.get("urls", {}).get("web", {}).get("project", ""),
                    category=category_name,
                    pledged=float(project.get("pledged", 0)),
                    goal=float(project.get("goal", 0)),
                    backers=int(project.get("backers_count", 0)),
                    created_at=datetime.fromtimestamp(project.get("created_at", 0)).isoformat() if project.get("created_at") else "",
                    currency=project.get("currency", "USD"),
                    state=project.get("state", "live"),
                )
                items.append(item)
                
            except Exception as e:
                print(f"[Kickstarter] 解析项目失败: {e}")
                continue
        
        return items
    
    @classmethod
    def from_config(cls, config: dict) -> "KickstarterSource":
        """
        从配置创建实例
        
        Args:
            config: kickstarter 配置字典
            
        Returns:
            KickstarterSource 实例
        """
        return cls(
            categories=config.get("categories"),
            search_keywords=config.get("search_keywords"),
            max_items=config.get("max_items", 20),
            sort=config.get("sort", "magic"),
            request_interval=config.get("request_interval", 1.0),
        )
