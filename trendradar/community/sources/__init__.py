# coding=utf-8
"""
社区数据源模块

支持的数据源：
- HackerNews: Algolia Search API
- Reddit: RSS Feed（通过代理）
- Kickstarter: RSS Feed + Discover API
- Twitter: RSS-Bridge
- GitHub: Search API（热门仓库）
- ProductHunt: RSS Feed（热门产品）
"""

from .hackernews import HackerNewsSource
from .reddit import RedditSource
from .kickstarter import KickstarterSource
from .twitter import TwitterSource
from .github import GitHubSource
from .producthunt import ProductHuntSource

__all__ = [
    "HackerNewsSource",
    "RedditSource",
    "KickstarterSource",
    "TwitterSource",
    "GitHubSource",
    "ProductHuntSource",
]
