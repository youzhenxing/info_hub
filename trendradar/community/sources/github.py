# coding=utf-8
"""
GitHub Trending 数据源

使用 GitHub Search API 获取热门仓库
"""

import time
import requests
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime, timedelta

# 导入降级请求工具
from ..utils.request_utils import fetch_with_fallback


@dataclass
class GitHubItem:
    """GitHub 仓库条目"""
    id: str
    name: str
    full_name: str
    description: str
    url: str
    stars: int
    forks: int
    language: str
    owner: str
    created_at: str
    updated_at: str
    topics: List[str]
    source: str = "github"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "full_name": self.full_name,
            "title": self.name,  # 兼容其他数据源
            "description": self.description,
            "url": self.url,
            "stars": self.stars,
            "forks": self.forks,
            "language": self.language or "Unknown",
            "owner": self.owner,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "topics": self.topics,
            "source": self.source,
        }


class GitHubSource:
    """
    GitHub 数据源
    
    使用 GitHub Search API 获取热门 AI/机器人相关仓库
    """
    
    API_URL = "https://api.github.com/search/repositories"
    
    # User-Agent
    USER_AGENT = "TrendRadar/1.0 (Community Monitor)"
    
    def __init__(
        self,
        topics: List[str] = None,
        min_stars: int = 10,
        created_days: int = 7,
        max_items: int = 30,
        request_interval: float = 1.0,
        proxy_url: str = None,
        api_token: str = None,
    ):
        """
        初始化 GitHub 数据源
        
        Args:
            topics: 搜索主题列表
            min_stars: 最低 star 数
            created_days: 创建时间范围（天）
            max_items: 最大返回条目数
            request_interval: 请求间隔（秒）
            proxy_url: 代理地址
            api_token: GitHub API Token（可选，提高限额）
        """
        self.topics = topics or [
            "ai",
            "llm",
            "machine-learning",
            "robotics",
            "deep-learning",
        ]
        self.min_stars = min_stars
        self.created_days = created_days
        self.max_items = max_items
        self.request_interval = request_interval
        self.proxy_url = proxy_url
        self.api_token = api_token
        
        # 配置代理
        self.proxies = None
        if proxy_url:
            self.proxies = {
                "http": proxy_url,
                "https": proxy_url,
            }
        
        self.session = requests.Session()
        headers = {
            "User-Agent": self.USER_AGENT,
            "Accept": "application/vnd.github.v3+json",
        }
        if api_token:
            headers["Authorization"] = f"token {api_token}"
        self.session.headers.update(headers)
        
        if self.proxies:
            self.session.proxies.update(self.proxies)
    
    def fetch(self) -> List[GitHubItem]:
        """
        获取 GitHub 热门仓库
        
        Returns:
            GitHubItem 列表
        """
        all_items = []
        seen_ids = set()
        
        # 计算日期范围
        date_from = (datetime.now() - timedelta(days=self.created_days)).strftime("%Y-%m-%d")
        
        # 按主题搜索
        for topic in self.topics:
            try:
                items = self._search_by_topic(topic, date_from)
                for item in items:
                    if item.id not in seen_ids:
                        seen_ids.add(item.id)
                        all_items.append(item)
                
                time.sleep(self.request_interval)
                
            except Exception as e:
                print(f"[GitHub] 搜索主题 '{topic}' 失败: {e}")
                continue
        
        # 按 star 数排序
        all_items.sort(key=lambda x: x.stars, reverse=True)
        return all_items[:self.max_items]
    
    def _search_by_topic(self, topic: str, date_from: str) -> List[GitHubItem]:
        """
        按主题搜索仓库

        Args:
            topic: 主题名称
            date_from: 最早创建日期

        Returns:
            GitHubItem 列表
        """
        # 构建搜索查询
        query = f"topic:{topic} stars:>={self.min_stars} created:>={date_from}"

        params = {
            "q": query,
            "sort": "stars",
            "order": "desc",
            "per_page": min(30, self.max_items),
        }

        # 使用直连优先、代理降级策略
        response, mode = fetch_with_fallback(
            self.session,
            self.API_URL,
            proxy_url=self.proxy_url,
            timeout=15,
            params=params
        )

        if response is None:
            raise Exception(f"搜索主题 '{topic}' 失败: 直连和代理都不可用")

        print(f"[GitHub] 搜索 '{topic}' 成功 (模式: {mode})")
        data = response.json()
        return self._parse_response(data)
    
    def _parse_response(self, data: dict) -> List[GitHubItem]:
        """
        解析 GitHub API 响应
        
        Args:
            data: API 响应
            
        Returns:
            GitHubItem 列表
        """
        items = []
        
        for repo in data.get("items", []):
            try:
                item = GitHubItem(
                    id=f"github_{repo.get('id')}",
                    name=repo.get("name", ""),
                    full_name=repo.get("full_name", ""),
                    description=repo.get("description", "") or "",
                    url=repo.get("html_url", ""),
                    stars=repo.get("stargazers_count", 0),
                    forks=repo.get("forks_count", 0),
                    language=repo.get("language", "") or "",
                    owner=repo.get("owner", {}).get("login", ""),
                    created_at=repo.get("created_at", ""),
                    updated_at=repo.get("updated_at", ""),
                    topics=repo.get("topics", []),
                )
                items.append(item)
                
            except Exception as e:
                print(f"[GitHub] 解析仓库失败: {e}")
                continue
        
        return items
    
    @classmethod
    def from_config(cls, config: dict, proxy_url: str = None) -> "GitHubSource":
        """
        从配置创建实例
        
        Args:
            config: github 配置字典
            proxy_url: 代理地址
            
        Returns:
            GitHubSource 实例
        """
        return cls(
            topics=config.get("topics"),
            min_stars=config.get("min_stars", 10),
            created_days=config.get("created_days", 7),
            max_items=config.get("max_items", 30),
            request_interval=config.get("request_interval", 1.0),
            proxy_url=proxy_url,
            api_token=config.get("api_token"),
        )
