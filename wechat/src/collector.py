"""
数据采集器 - 从 Wewe-RSS 获取公众号文章
"""

import logging
import hashlib
import time
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from pathlib import Path

import requests
import feedparser
from dateutil import parser as date_parser

from .models import Article, WechatFeed, FeedType
from .config_loader import ConfigLoader, WeweRssConfig, CollectorConfig
from .storage import Storage

logger = logging.getLogger(__name__)


class WechatCollector:
    """微信公众号文章采集器"""
    
    def __init__(self, config: ConfigLoader, storage: Storage):
        self.config = config
        self.storage = storage
        self.wewe_config: WeweRssConfig = config.wewe_rss
        self.collector_config: CollectorConfig = config.collector
        self.is_production = config.is_production
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'WechatCollector/1.0'
        })
        
        if not self.is_production:
            logger.info("🔧 开发环境模式：使用 tRPC 缓存 API，不触发账号同步")
    
    def collect_all(
        self,
        feed_limit: Optional[int] = None,
        test_feeds: Optional[List[str]] = None,
    ) -> List[Article]:
        """
        采集所有公众号的文章

        Args:
            feed_limit: 限制处理的公众号数量（测试模式）
            test_feeds: 指定测试的公众号名称列表（优先级高于feed_limit）

        Returns:
            新采集的文章列表
        """
        feeds = self.config.get_feeds()
        if not feeds:
            logger.warning("未配置任何公众号")
            return []

        # 测试模式过滤
        if test_feeds:
            # 优先使用指定的公众号列表
            feeds = [f for f in feeds if f.name in test_feeds]
            logger.info(f"🧪 测试模式：仅处理指定的 {len(feeds)} 个公众号")
        elif feed_limit:
            # 使用数量限制
            feeds = feeds[:feed_limit]
            logger.info(f"🧪 测试模式：仅处理前 {feed_limit} 个公众号")

        logger.info(f"开始采集 {len(feeds)} 个公众号")
        
        all_articles: List[Article] = []
        
        for feed in feeds:
            try:
                articles = self._collect_feed(feed)
                all_articles.extend(articles)
                
                # 请求间隔
                time.sleep(self.collector_config.request_interval)
                
            except Exception as e:
                logger.error(f"采集 {feed.name} 失败: {e}")
                continue
        
        # 保存到数据库
        new_count = 0
        for article in all_articles:
            if self.storage.save_article(article):
                new_count += 1
        
        logger.info(f"采集完成: 总计 {len(all_articles)} 篇，新增 {new_count} 篇")
        
        return all_articles
    
    def _collect_feed(self, feed: WechatFeed) -> List[Article]:
        """
        采集单个公众号的文章
        
        Args:
            feed: 公众号配置
        
        Returns:
            文章列表
        """
        logger.info(f"采集公众号: {feed.name} ({feed.wewe_feed_id})")
        
        # 开发环境：使用 tRPC 缓存 API，不触发同步
        if not self.is_production:
            try:
                articles = self._fetch_cached_articles(feed)
                logger.info(f"  [开发] 从缓存获取 {len(articles)} 篇文章")
                return articles
            except Exception as e:
                logger.warning(f"  [开发] 缓存获取失败，降级到 feeds API: {e}")
        
        # 生产环境：使用 JSON/RSS feed
        # 构建 Wewe-RSS 的 feed URL
        feed_url = f"{self.wewe_config.base_url}/feeds/{feed.wewe_feed_id}.json"
        
        try:
            # 尝试 JSON 格式（更完整的数据）
            articles = self._fetch_json_feed(feed, feed_url)
        except Exception as e:
            logger.warning(f"JSON 格式获取失败，尝试 RSS: {e}")
            # 降级到 RSS 格式
            feed_url = f"{self.wewe_config.base_url}/feeds/{feed.wewe_feed_id}.rss"
            articles = self._fetch_rss_feed(feed, feed_url)
        
        # 过滤旧文章
        cutoff_date = datetime.now() - timedelta(days=self.collector_config.max_age_days)
        filtered_articles = []
        for a in articles:
            if a.published_at is None:
                filtered_articles.append(a)
            else:
                # 确保比较时都是 naive datetime
                pub_date = a.published_at
                if pub_date.tzinfo is not None:
                    pub_date = pub_date.replace(tzinfo=None)
                if pub_date >= cutoff_date:
                    filtered_articles.append(a)
        articles = filtered_articles
        
        # 限制数量
        articles = articles[:self.collector_config.max_articles_per_feed]
        
        logger.info(f"  获取 {len(articles)} 篇文章")
        
        return articles
    
    def _fetch_cached_articles(self, feed: WechatFeed) -> List[Article]:
        """
        从 tRPC 缓存 API 获取文章（开发环境使用，不触发账号同步）
        
        Args:
            feed: 公众号配置
        
        Returns:
            文章列表
        """
        import urllib.parse
        import json
        
        # 构建 tRPC 请求
        input_data = json.dumps({"feedId": feed.wewe_feed_id})
        encoded_input = urllib.parse.quote(input_data)
        url = f"{self.wewe_config.base_url}/trpc/article.list?input={encoded_input}"
        
        headers = {}
        if self.wewe_config.auth_code:
            headers['Authorization'] = self.wewe_config.auth_code
        
        response = self.session.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        
        # tRPC 响应格式: {"result":{"data":{"items":[...]}}}
        result_data = data.get("result", {}).get("data", {})
        items = result_data.get("items", [])
        
        articles = []
        cutoff_date = datetime.now() - timedelta(days=self.collector_config.max_age_days)
        
        for item in items[:self.collector_config.max_articles_per_feed]:
            try:
                # 解析发布时间
                published_at = None
                pub_time = item.get("publishTime")
                if pub_time:
                    # publishTime 是 Unix 时间戳（秒）
                    published_at = datetime.fromtimestamp(pub_time)
                    
                    # 过滤旧文章
                    if published_at < cutoff_date:
                        continue
                
                article = Article(
                    id=self._generate_id(item.get("link", "")),
                    feed_id=feed.id,
                    feed_name=feed.name,
                    feed_type=feed.feed_type,
                    title=item.get("title", ""),
                    url=item.get("link", ""),
                    content=item.get("content", ""),
                    summary=item.get("summary", ""),
                    published_at=published_at
                )
                articles.append(article)
            except Exception as e:
                logger.warning(f"解析缓存文章失败: {e}")
                continue
        
        return articles
    
    def _fetch_json_feed(self, feed: WechatFeed, url: str) -> List[Article]:
        """
        从 JSON 格式的 feed 获取文章
        """
        params = {
            'limit': self.collector_config.max_articles_per_feed
        }
        
        response = self.session.get(url, params=params, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        articles = []
        
        items = data.get('items', [])
        for item in items:
            article = self._parse_json_item(feed, item)
            if article:
                articles.append(article)
        
        return articles
    
    def _fetch_rss_feed(self, feed: WechatFeed, url: str) -> List[Article]:
        """
        从 RSS 格式的 feed 获取文章
        """
        response = self.session.get(url, timeout=30)
        response.raise_for_status()
        
        parsed = feedparser.parse(response.content)
        articles = []
        
        for entry in parsed.entries[:self.collector_config.max_articles_per_feed]:
            article = self._parse_rss_entry(feed, entry)
            if article:
                articles.append(article)
        
        return articles
    
    def _parse_json_item(self, feed: WechatFeed, item: Dict[str, Any]) -> Optional[Article]:
        """解析 JSON 格式的文章"""
        try:
            url = item.get('url', '')
            if not url:
                return None
            
            # 生成唯一 ID
            article_id = self._generate_id(url)
            
            # 解析发布时间
            published_at = None
            date_str = item.get('date_published') or item.get('date_modified')
            if date_str:
                try:
                    published_at = date_parser.parse(date_str)
                except:
                    pass
            
            return Article(
                id=article_id,
                feed_id=feed.id,
                feed_name=feed.name,
                feed_type=feed.feed_type,
                title=item.get('title', ''),
                url=url,
                content=item.get('content_html', item.get('content_text', '')),
                summary=item.get('summary', ''),
                published_at=published_at
            )
        except Exception as e:
            logger.warning(f"解析 JSON 文章失败: {e}")
            return None
    
    def _parse_rss_entry(self, feed: WechatFeed, entry: Any) -> Optional[Article]:
        """解析 RSS 格式的文章"""
        try:
            url = entry.get('link', '')
            if not url:
                return None
            
            # 生成唯一 ID
            article_id = self._generate_id(url)
            
            # 解析发布时间（转为 naive datetime）
            published_at = None
            try:
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    published_at = datetime(*entry.published_parsed[:6])
                elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                    published_at = datetime(*entry.updated_parsed[:6])
            except Exception:
                pass  # 忽略时间解析错误
            
            # 获取内容
            content = ''
            if hasattr(entry, 'content') and entry.content:
                content = entry.content[0].get('value', '')
            elif hasattr(entry, 'summary'):
                content = entry.summary
            
            return Article(
                id=article_id,
                feed_id=feed.id,
                feed_name=feed.name,
                feed_type=feed.feed_type,
                title=entry.get('title', ''),
                url=url,
                content=content,
                summary=entry.get('summary', ''),
                published_at=published_at
            )
        except Exception as e:
            logger.warning(f"解析 RSS 文章失败: {e}")
            return None
    
    def _generate_id(self, url: str) -> str:
        """根据 URL 生成唯一 ID"""
        return hashlib.md5(url.encode()).hexdigest()
