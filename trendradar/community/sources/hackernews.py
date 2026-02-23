# coding=utf-8
"""
HackerNews 数据源

使用 Algolia HN Search API 进行智能搜索
API 文档: https://hn.algolia.com/api
"""

import time
import requests
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta


@dataclass
class HNItem:
    """HackerNews 条目"""
    id: str
    title: str
    url: str
    score: int
    comments: int
    author: str
    created_at: str
    source: str = "hackernews"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "url": self.url,
            "score": self.score,
            "comments": self.comments,
            "author": self.author,
            "created_at": self.created_at,
            "source": self.source,
        }


class HackerNewsSource:
    """
    HackerNews 数据源
    
    使用 Algolia Search API 进行关键词搜索
    """
    
    ALGOLIA_API = "https://hn.algolia.com/api/v1"
    
    def __init__(
        self,
        search_keywords: List[str] = None,
        max_items: int = 30,
        min_score: int = 10,
        max_age_hours: int = 24,
        request_interval: float = 0.5,
    ):
        """
        初始化 HackerNews 数据源
        
        Args:
            search_keywords: 搜索关键词列表
            max_items: 最大返回条目数
            min_score: 最低分数过滤
            max_age_hours: 最大时间范围（小时）
            request_interval: 请求间隔（秒）
        """
        self.search_keywords = search_keywords or ["AI", "LLM", "robotics", "startup", "AGI"]
        self.max_items = max_items
        self.min_score = min_score
        self.max_age_hours = max_age_hours
        self.request_interval = request_interval
        
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "TrendRadar/1.0 (Community Monitor)"
        })
    
    def fetch(self) -> List[HNItem]:
        """
        获取 HackerNews 热门内容
        
        使用 Algolia Search API 按关键词搜索
        
        Returns:
            HNItem 列表
        """
        all_items = []
        seen_ids = set()
        
        # 计算时间范围
        now = int(time.time())
        min_time = now - (self.max_age_hours * 3600)
        
        for keyword in self.search_keywords:
            try:
                items = self._search_by_keyword(keyword, min_time)
                for item in items:
                    if item.id not in seen_ids:
                        seen_ids.add(item.id)
                        all_items.append(item)
                
                time.sleep(self.request_interval)
                
            except Exception as e:
                print(f"[HackerNews] 搜索关键词 '{keyword}' 失败: {e}")
                continue
        
        # 按分数排序并截取
        all_items.sort(key=lambda x: x.score, reverse=True)
        return all_items[:self.max_items]
    
    def _search_by_keyword(self, keyword: str, min_time: int) -> List[HNItem]:
        """
        按关键词搜索
        
        Args:
            keyword: 搜索关键词
            min_time: 最早时间戳
            
        Returns:
            HNItem 列表
        """
        url = f"{self.ALGOLIA_API}/search_by_date"
        params = {
            "query": keyword,
            "tags": "story",  # 只搜索 story，不包括 comment
            "numericFilters": f"created_at_i>{min_time},points>{self.min_score}",
            "hitsPerPage": 50,
        }
        
        response = self.session.get(url, params=params, timeout=15)
        response.raise_for_status()
        
        data = response.json()
        items = []
        
        for hit in data.get("hits", []):
            # 处理 URL（有些是 Ask HN 没有外链）
            item_url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
            
            item = HNItem(
                id=f"hn_{hit.get('objectID')}",
                title=hit.get("title", ""),
                url=item_url,
                score=hit.get("points", 0),
                comments=hit.get("num_comments", 0),
                author=hit.get("author", ""),
                created_at=hit.get("created_at", ""),
            )
            items.append(item)
        
        return items
    
    def fetch_top_stories(self, limit: int = 30) -> List[HNItem]:
        """
        获取 Top Stories（备用方法，不使用搜索）
        
        使用官方 Firebase API
        
        Returns:
            HNItem 列表
        """
        firebase_api = "https://hacker-news.firebaseio.com/v0"
        
        # 获取 top stories ID 列表
        response = self.session.get(f"{firebase_api}/topstories.json", timeout=15)
        response.raise_for_status()
        story_ids = response.json()[:limit]
        
        items = []
        for story_id in story_ids:
            try:
                item_resp = self.session.get(f"{firebase_api}/item/{story_id}.json", timeout=10)
                item_resp.raise_for_status()
                item_data = item_resp.json()
                
                if not item_data or item_data.get("type") != "story":
                    continue
                
                # 分数过滤
                if item_data.get("score", 0) < self.min_score:
                    continue
                
                item_url = item_data.get("url") or f"https://news.ycombinator.com/item?id={story_id}"
                
                item = HNItem(
                    id=f"hn_{story_id}",
                    title=item_data.get("title", ""),
                    url=item_url,
                    score=item_data.get("score", 0),
                    comments=item_data.get("descendants", 0),
                    author=item_data.get("by", ""),
                    created_at=datetime.fromtimestamp(item_data.get("time", 0)).isoformat(),
                )
                items.append(item)
                
                time.sleep(self.request_interval)
                
            except Exception as e:
                print(f"[HackerNews] 获取 story {story_id} 失败: {e}")
                continue
        
        return items
    
    @classmethod
    def from_config(cls, config: dict) -> "HackerNewsSource":
        """
        从配置创建实例
        
        Args:
            config: hackernews 配置字典
            
        Returns:
            HackerNewsSource 实例
        """
        return cls(
            search_keywords=config.get("search_keywords"),
            max_items=config.get("max_items", 30),
            min_score=config.get("min_score", 10),
            max_age_hours=config.get("max_age_hours", 24),
            request_interval=config.get("request_interval", 0.5),
        )
