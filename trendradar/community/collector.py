# coding=utf-8
"""
社区内容收集器

从多个数据源收集内容并合并
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

from .sources import (
    HackerNewsSource,
    RedditSource,
    KickstarterSource,
    TwitterSource,
    GitHubSource,
    ProductHuntSource,
)


@dataclass
class SourceData:
    """单个数据源的数据"""
    source_id: str
    source_name: str
    items: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None
    fetch_time: str = ""
    
    @property
    def count(self) -> int:
        return len(self.items)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "source_name": self.source_name,
            "items": self.items,
            "count": self.count,
            "error": self.error,
            "fetch_time": self.fetch_time,
        }


@dataclass
class CollectedData:
    """收集的全部数据"""
    date: str
    timestamp: str
    sources: Dict[str, SourceData] = field(default_factory=dict)
    total_items: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "date": self.date,
            "timestamp": self.timestamp,
            "sources": {k: v.to_dict() for k, v in self.sources.items()},
            "total_items": self.total_items,
        }
    
    def get_all_items(self) -> List[Dict[str, Any]]:
        """获取所有来源的全部条目"""
        all_items = []
        for source_data in self.sources.values():
            all_items.extend(source_data.items)
        return all_items


class CommunityCollector:
    """
    社区内容收集器
    
    从 HackerNews、Reddit、Kickstarter、Twitter、GitHub、ProductHunt 收集热门内容
    """
    
    def __init__(
        self,
        sources_config: dict,
        topics: List[str] = None,
        proxy_url: str = None,
    ):
        """
        初始化收集器
        
        Args:
            sources_config: 数据源配置
            topics: 关注的话题列表
            proxy_url: 代理地址（用于访问被墙网站）
        """
        self.sources_config = sources_config
        self.topics = topics or ["AI", "机器人", "AI硬件", "创业", "投资", "LLM", "AGI"]
        self.proxy_url = proxy_url
        
        # 初始化数据源
        self._init_sources()
    
    def _init_sources(self):
        """初始化各数据源"""
        self.sources = {}
        
        # HackerNews（无需代理）
        hn_config = self.sources_config.get("hackernews", {})
        if hn_config.get("enabled", True):
            hn_config.setdefault("search_keywords", self._get_english_topics())
            self.sources["hackernews"] = HackerNewsSource.from_config(hn_config)
        
        # Reddit（需要代理）
        reddit_config = self.sources_config.get("reddit", {})
        if reddit_config.get("enabled", True):
            reddit_config.setdefault("search_keywords", self._get_english_topics())
            self.sources["reddit"] = RedditSource.from_config(reddit_config, proxy_url=self.proxy_url)
        
        # Kickstarter（需要代理）
        ks_config = self.sources_config.get("kickstarter", {})
        if ks_config.get("enabled", False):  # 默认关闭
            ks_config.setdefault("search_keywords", self._get_english_topics())
            self.sources["kickstarter"] = KickstarterSource.from_config(ks_config)
        
        # Twitter（需要代理）
        twitter_config = self.sources_config.get("twitter", {})
        if twitter_config.get("enabled", False):  # 默认关闭
            twitter_config.setdefault("search_queries", self._get_english_topics())
            self.sources["twitter"] = TwitterSource.from_config(
                twitter_config,
                proxy_url=self.proxy_url  # 传递代理配置
            )
        
        # GitHub（通过代理或直连均可）
        github_config = self.sources_config.get("github", {})
        if github_config.get("enabled", True):
            self.sources["github"] = GitHubSource.from_config(github_config, proxy_url=self.proxy_url)
        
        # ProductHunt（需要代理）
        ph_config = self.sources_config.get("producthunt", {})
        if ph_config.get("enabled", True):
            self.sources["producthunt"] = ProductHuntSource.from_config(ph_config, proxy_url=self.proxy_url)
    
    def _get_english_topics(self) -> List[str]:
        """获取英文关键词列表"""
        english_keywords = []
        for topic in self.topics:
            if topic.isascii():
                english_keywords.append(topic)
            elif topic == "机器人":
                english_keywords.append("robotics")
            elif topic in ["AI硬件", "AI 硬件"]:
                english_keywords.append("AI hardware")
            elif topic == "创业":
                english_keywords.append("startup")
            elif topic == "投资":
                english_keywords.append("venture capital")
        
        return english_keywords
    
    def collect(self) -> CollectedData:
        """
        收集所有数据源的内容
        
        Returns:
            CollectedData 对象
        """
        now = datetime.now()
        collected = CollectedData(
            date=now.strftime("%Y-%m-%d"),
            timestamp=now.strftime("%Y-%m-%d %H:%M:%S"),
        )
        
        total = 0
        
        # HackerNews
        if "hackernews" in self.sources:
            source_data = self._collect_hackernews()
            collected.sources["hackernews"] = source_data
            total += source_data.count
            print(f"[Collector] HackerNews: {source_data.count} 条")
        
        # Reddit
        if "reddit" in self.sources:
            source_data = self._collect_reddit()
            collected.sources["reddit"] = source_data
            total += source_data.count
            print(f"[Collector] Reddit: {source_data.count} 条")
        
        # Kickstarter
        if "kickstarter" in self.sources:
            source_data = self._collect_kickstarter()
            collected.sources["kickstarter"] = source_data
            total += source_data.count
            print(f"[Collector] Kickstarter: {source_data.count} 条")
        
        # Twitter
        if "twitter" in self.sources:
            source_data = self._collect_twitter()
            collected.sources["twitter"] = source_data
            total += source_data.count
            print(f"[Collector] Twitter: {source_data.count} 条")
        
        # GitHub
        if "github" in self.sources:
            source_data = self._collect_github()
            collected.sources["github"] = source_data
            total += source_data.count
            print(f"[Collector] GitHub: {source_data.count} 条")
        
        # ProductHunt
        if "producthunt" in self.sources:
            source_data = self._collect_producthunt()
            collected.sources["producthunt"] = source_data
            total += source_data.count
            print(f"[Collector] ProductHunt: {source_data.count} 条")
        
        collected.total_items = total
        print(f"[Collector] 总计收集: {total} 条")
        
        return collected
    
    def _collect_hackernews(self) -> SourceData:
        """收集 HackerNews 数据"""
        source = self.sources["hackernews"]
        
        try:
            items = source.fetch()
            return SourceData(
                source_id="hackernews",
                source_name="HackerNews",
                items=[item.to_dict() for item in items],
                fetch_time=datetime.now().isoformat(),
            )
        except Exception as e:
            print(f"[Collector] HackerNews 错误: {e}")
            return SourceData(
                source_id="hackernews",
                source_name="HackerNews",
                error=str(e),
                fetch_time=datetime.now().isoformat(),
            )
    
    def _collect_reddit(self) -> SourceData:
        """收集 Reddit 数据"""
        source = self.sources["reddit"]
        
        try:
            items = source.fetch()
            return SourceData(
                source_id="reddit",
                source_name="Reddit",
                items=[item.to_dict() for item in items],
                fetch_time=datetime.now().isoformat(),
            )
        except Exception as e:
            print(f"[Collector] Reddit 错误: {e}")
            return SourceData(
                source_id="reddit",
                source_name="Reddit",
                error=str(e),
                fetch_time=datetime.now().isoformat(),
            )
    
    def _collect_kickstarter(self) -> SourceData:
        """收集 Kickstarter 数据"""
        source = self.sources["kickstarter"]
        
        try:
            items = source.fetch()
            return SourceData(
                source_id="kickstarter",
                source_name="Kickstarter",
                items=[item.to_dict() for item in items],
                fetch_time=datetime.now().isoformat(),
            )
        except Exception as e:
            print(f"[Collector] Kickstarter 错误: {e}")
            return SourceData(
                source_id="kickstarter",
                source_name="Kickstarter",
                error=str(e),
                fetch_time=datetime.now().isoformat(),
            )
    
    def _collect_twitter(self) -> SourceData:
        """收集 Twitter 数据"""
        source = self.sources["twitter"]
        
        try:
            items = source.fetch()
            return SourceData(
                source_id="twitter",
                source_name="Twitter/X",
                items=[item.to_dict() for item in items],
                fetch_time=datetime.now().isoformat(),
            )
        except Exception as e:
            print(f"[Collector] Twitter 错误: {e}")
            return SourceData(
                source_id="twitter",
                source_name="Twitter/X",
                error=str(e),
                fetch_time=datetime.now().isoformat(),
            )
    
    def _collect_github(self) -> SourceData:
        """收集 GitHub 数据"""
        source = self.sources["github"]
        
        try:
            items = source.fetch()
            return SourceData(
                source_id="github",
                source_name="GitHub Trending",
                items=[item.to_dict() for item in items],
                fetch_time=datetime.now().isoformat(),
            )
        except Exception as e:
            print(f"[Collector] GitHub 错误: {e}")
            return SourceData(
                source_id="github",
                source_name="GitHub Trending",
                error=str(e),
                fetch_time=datetime.now().isoformat(),
            )
    
    def _collect_producthunt(self) -> SourceData:
        """收集 ProductHunt 数据"""
        source = self.sources["producthunt"]
        
        try:
            items = source.fetch()
            return SourceData(
                source_id="producthunt",
                source_name="ProductHunt",
                items=[item.to_dict() for item in items],
                fetch_time=datetime.now().isoformat(),
            )
        except Exception as e:
            print(f"[Collector] ProductHunt 错误: {e}")
            return SourceData(
                source_id="producthunt",
                source_name="ProductHunt",
                error=str(e),
                fetch_time=datetime.now().isoformat(),
            )
    
    @classmethod
    def from_config(cls, config: dict) -> "CommunityCollector":
        """
        从配置创建收集器
        
        Args:
            config: 完整配置字典
            
        Returns:
            CommunityCollector 实例
        """
        community_config = config.get("COMMUNITY", config.get("community", {}))
        sources_config = community_config.get("SOURCES", community_config.get("sources", {}))
        topics = community_config.get("TOPICS", community_config.get("topics", []))
        
        # 获取代理配置
        proxy_config = community_config.get("PROXY", community_config.get("proxy", {}))
        proxy_url = None
        if proxy_config.get("ENABLED", proxy_config.get("enabled", False)):
            proxy_url = proxy_config.get("URL", proxy_config.get("url", ""))
        
        return cls(
            sources_config=sources_config,
            topics=topics,
            proxy_url=proxy_url,
        )
