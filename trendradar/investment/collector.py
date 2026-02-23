# coding=utf-8
"""
投资数据收集器模块

聚合财经 RSS 新闻和行情数据
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from .market_data import MarketDataFetcher, MarketSnapshot

logger = logging.getLogger(__name__)


@dataclass
class NewsItem:
    """新闻条目"""
    title: str
    source: str
    url: str
    published: str
    summary: str = ""
    matched_concepts: List[str] = field(default_factory=list)


@dataclass
class CollectedData:
    """收集的投资数据"""
    date: str
    timestamp: str
    market_snapshot: Optional[MarketSnapshot]
    news: List[NewsItem] = field(default_factory=list)
    matched_concepts: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式（用于 AI 分析）"""
        result = {
            "date": self.date,
            "timestamp": self.timestamp,
            "market_data": {},
            "money_flow": {},
            "news": [],
            "matched_concepts": list(set(self.matched_concepts)),
        }

        if self.market_snapshot:
            # 指数行情
            result["market_data"]["indices"] = [
                {
                    "name": idx.name,
                    "symbol": idx.symbol,
                    "price": idx.price,
                    "change": idx.change,
                    "change_pct": idx.change_pct,
                    "volume": idx.volume,
                    "amount": idx.amount,
                }
                for idx in self.market_snapshot.indices
            ]

            # 个股行情
            result["market_data"]["watchlist"] = [
                {
                    "name": stock.name,
                    "symbol": stock.symbol,
                    "price": stock.price,
                    "change": stock.change,
                    "change_pct": stock.change_pct,
                    "volume": stock.volume,
                    "turnover": stock.turnover,
                    "pe": stock.pe,
                    "market_cap": stock.market_cap,
                }
                for stock in self.market_snapshot.stocks
            ]

            # 加密货币
            result["market_data"]["crypto"] = [
                {
                    "name": crypto.name,
                    "symbol": crypto.symbol,
                    "price_usd": crypto.price_usd,
                    "price_cny": crypto.price_cny,
                    "change_pct_24h": crypto.change_pct_24h,
                }
                for crypto in self.market_snapshot.crypto
            ]

            # 北向资金
            if self.market_snapshot.northbound:
                nb = self.market_snapshot.northbound
                result["money_flow"]["northbound"] = {
                    "date": nb.date,
                    "sh_connect": nb.sh_connect,
                    "sz_connect": nb.sz_connect,
                    "total": nb.total,
                }

            # 板块资金流向
            result["money_flow"]["sector_flows"] = [
                {
                    "name": sector.name,
                    "change_pct": sector.change_pct,
                    "net_flow": sector.net_flow,
                    "net_flow_pct": sector.net_flow_pct,
                }
                for sector in self.market_snapshot.sector_flows
            ]

        # 新闻
        result["news"] = [
            {
                "title": news.title,
                "source": news.source,
                "url": news.url,
                "published": news.published,
                "summary": news.summary[:200] if news.summary else "",
                "matched_concepts": news.matched_concepts,
            }
            for news in self.news
        ]

        return result


class InvestmentCollector:
    """投资数据收集器"""

    # 宏观经济/政策类关键词（这些新闻可以保留7天）
    MACRO_KEYWORDS = [
        "宏观", "政策", "央行", "美联储", "利率", "货币政策", "财政政策",
        "GDP", "通胀", "CPI", "PPI", "经济", "金融政策", "监管", "降息",
        "加息", "降准", "财政", "国务院", "发改委", "证监会", "银保监",
        "经济工作会议", "政治局", "战略", "规划", "改革", "十四五",
        "宏观经济", "经济数据", "贸易", "关税", "汇率", "人民币", "美元",
    ]

    def __init__(self, config: Dict[str, Any], storage_manager=None):
        """
        初始化数据收集器

        Args:
            config: investment 配置字典
            storage_manager: 存储管理器（用于获取热榜数据）
        """
        self.config = config
        self.storage_manager = storage_manager
        self.market_fetcher = MarketDataFetcher(config)

        # 获取概念关键词
        self.concepts = config.get("concepts", [])

        # 获取代理配置（用于 rsshub.app 等需要代理的 RSS 源）
        proxy_config = config.get("proxy", {})
        self.proxy_enabled = proxy_config.get("enabled", False)
        self.proxy_url = proxy_config.get("url", "") if self.proxy_enabled else None

        if self.proxy_enabled and self.proxy_url:
            logger.info(f"[投资模块] 代理降级策略已启用: {self.proxy_url}")

    def collect(self) -> CollectedData:
        """
        收集所有投资相关数据

        Returns:
            CollectedData: 聚合的投资数据
        """
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        timestamp = now.strftime("%Y-%m-%d %H:%M:%S")

        logger.info(f"开始收集投资数据 - {timestamp}")

        # 获取行情数据
        market_snapshot = None
        try:
            market_snapshot = self.market_fetcher.get_market_snapshot()
            logger.info(f"行情数据收集完成: {len(market_snapshot.indices)} 个指数, "
                       f"{len(market_snapshot.stocks)} 只个股, "
                       f"{len(market_snapshot.crypto)} 个加密货币")
        except Exception as e:
            logger.error(f"获取行情数据失败: {e}")

        # 获取财经新闻
        news_items = []
        all_matched_concepts = []
        try:
            news_items, all_matched_concepts = self._collect_news()
            logger.info(f"新闻收集完成: {len(news_items)} 条, 命中概念: {all_matched_concepts}")
        except Exception as e:
            logger.error(f"获取财经新闻失败: {e}")

        return CollectedData(
            date=date_str,
            timestamp=timestamp,
            market_snapshot=market_snapshot,
            news=news_items,
            matched_concepts=all_matched_concepts,
        )

    def _collect_news(self) -> tuple[List[NewsItem], List[str]]:
        """
        收集财经新闻（支持多来源）

        数据源：
        1. hotlist: 从热榜数据库获取（华尔街见闻、财联社等）
        2. rss: 从 RSS 订阅源获取（金十数据、CoinDesk等）

        Returns:
            tuple: (新闻列表, 命中的概念列表)
        """
        news_items = []
        all_matched_concepts = set()

        sources_config = self.config.get("sources", {})

        # 1. 从热榜数据库获取财经新闻
        hotlist_config = sources_config.get("hotlist", {})
        hotlist_enabled = hotlist_config.get("enabled", False)
        
        if hotlist_enabled:
            max_news = hotlist_config.get("max_news", 30)
            platform_ids = hotlist_config.get("platform_ids", [])
            
            if platform_ids:
                try:
                    items, concepts = self._get_news_from_storage(platform_ids, max_news)
                    news_items.extend(items)
                    all_matched_concepts.update(concepts)
                    logger.info(f"从热榜获取 {len(items)} 条新闻")
                except Exception as e:
                    logger.warning(f"从热榜获取新闻失败: {e}")

        # 2. 从 RSS 订阅源获取新闻
        rss_config = sources_config.get("rss", {})
        rss_enabled = rss_config.get("enabled", False)
        rss_feeds = rss_config.get("feeds", [])
        
        if rss_enabled and rss_feeds:
            try:
                rss_items, rss_concepts = self._get_news_from_rss(rss_config)
                news_items.extend(rss_items)
                all_matched_concepts.update(rss_concepts)
                logger.info(f"从 RSS 获取 {len(rss_items)} 条新闻")
            except Exception as e:
                logger.warning(f"从 RSS 获取新闻失败: {e}")

        return news_items, list(all_matched_concepts)

    def _get_news_from_rss(self, rss_config: Dict[str, Any]) -> tuple[List[NewsItem], set]:
        """从 RSS 订阅源获取新闻（支持代理降级和智能时间过滤）"""
        news_items = []
        all_matched_concepts = set()

        feeds = rss_config.get("feeds", [])
        max_news = rss_config.get("max_news", 20)

        if not feeds:
            return news_items, all_matched_concepts

        # 获取当前时间，用于时间过滤
        from datetime import timedelta
        now = datetime.now()

        # 导入代理降级工具
        try:
            from trendradar.community.utils.request_utils import fetch_with_fallback
            HAS_FALLBACK = True
        except ImportError:
            HAS_FALLBACK = False
            logger.warning("代理降级工具不可用，使用直连模式")

        try:
            from trendradar.crawler.rss import RSSParser
            import requests

            parser = RSSParser()
            session = requests.Session()
            session.headers.update({
                "User-Agent": "TrendRadar/2.0 Investment Reader"
            })

            for feed_config in feeds:
                # 支持大写和小写键
                enabled = feed_config.get("enabled", feed_config.get("ENABLED", True))
                if not enabled:
                    continue

                feed_url = feed_config.get("url", feed_config.get("URL", ""))
                feed_name = feed_config.get("name", feed_config.get("NAME",
                    feed_config.get("id", feed_config.get("ID", "未知来源"))))

                if not feed_url:
                    continue

                try:
                    logger.info(f"正在获取 RSS: {feed_name}")

                    # 使用代理降级策略获取 RSS 内容
                    if HAS_FALLBACK and self.proxy_url:
                        response, mode = fetch_with_fallback(
                            session,
                            feed_url,
                            proxy_url=self.proxy_url,
                            timeout=15
                        )

                        if response is None:
                            logger.warning(f"获取 RSS {feed_name} 失败: 直连和代理都不可用")
                            continue

                        # 解析响应内容
                        items = parser.parse(response.text, feed_url)
                        logger.info(f"从 {feed_name} 获取 {len(items)} 条 (模式: {mode})")
                    else:
                        # 直连模式（无代理降级）
                        items = parser.parse_url(feed_url, timeout=15)
                        logger.info(f"从 {feed_name} 获取 {len(items)} 条 (直连)")

                    for item in items[:10]:  # 每个源最多取 10 条
                        # ParsedRSSItem 是 dataclass，使用属性访问
                        title = item.title if hasattr(item, 'title') else ""
                        summary = item.summary if hasattr(item, 'summary') else ""
                        url = item.url if hasattr(item, 'url') else ""
                        published = item.published_at if hasattr(item, 'published_at') else ""

                        if not title:
                            continue

                        # 智能时间过滤
                        if published:
                            try:
                                pub_time = self._parse_published_time(published)

                                if pub_time:
                                    # 判断是否为宏观经济/政策类新闻
                                    is_macro = self._is_macro_news(title, summary)

                                    if is_macro:
                                        # 宏观政策类：保留7天内
                                        max_age = timedelta(days=7)
                                    else:
                                        # 普通新闻：保留24小时内
                                        max_age = timedelta(hours=24)

                                    if now - pub_time > max_age:
                                        # 超过时间限制，跳过
                                        continue

                            except Exception as e:
                                # 时间解析失败，保留新闻
                                logger.debug(f"时间解析失败: {published}, 错误: {e}")

                        # 匹配关注概念
                        matched = self._match_concepts(title, summary or "")

                        news_item = NewsItem(
                            title=title,
                            source=feed_name,
                            url=url,
                            published=published or "",
                            summary=(summary[:200] if summary else ""),
                            matched_concepts=matched,
                        )
                        news_items.append(news_item)
                        all_matched_concepts.update(matched)

                        if len(news_items) >= max_news:
                            break

                except Exception as e:
                    logger.warning(f"获取 RSS {feed_name} 失败: {e}")

                if len(news_items) >= max_news:
                    break

        except ImportError:
            logger.warning("RSS 解析器不可用，跳过 RSS 数据源")

        return news_items, all_matched_concepts

    def _is_macro_news(self, title: str, summary: str) -> bool:
        """
        判断是否为宏观经济/政策类新闻

        Args:
            title: 新闻标题
            summary: 新闻摘要

        Returns:
            bool: 是否为宏观政策类新闻
        """
        text = f"{title} {summary}".lower()

        for keyword in self.MACRO_KEYWORDS:
            if keyword.lower() in text:
                return True

        return False

    def _parse_published_time(self, published: str) -> Optional[datetime]:
        """
        解析发布时间

        支持多种格式：
        - 2026-02-06T14:30:00+08:00
        - 2026-02-06 14:30:00
        - 14:30:00

        Args:
            published: 发布时间字符串

        Returns:
            datetime对象，解析失败返回None
        """
        if not published:
            return None

        try:
            # ISO格式带时区
            if 'T' in published:
                return datetime.fromisoformat(published.replace("Z", "+00:00"))

            # 日期时间格式
            elif '-' in published and ':' in published:
                return datetime.fromisoformat(published)

            # 只有时间
            elif ':' in published:
                # 假设是今天的某个时间
                now = datetime.now()
                hour, minute = map(int, published.split(':')[:2])
                return now.replace(hour=hour, minute=minute, second=0, microsecond=0)

            else:
                return None
        except Exception as e:
            logger.debug(f"时间解析失败: {published}, {e}")
            return None

    # 平台 ID 到显示名称的映射
    PLATFORM_NAMES = {
        "wallstreetcn-hot": "华尔街见闻",
        "cls-hot": "财联社",
        "weibo": "微博热搜",
        "toutiao": "今日头条",
        "thepaper": "澎湃新闻",
        "baidu": "百度热搜",
        "zhihu": "知乎热榜",
    }

    def _get_news_from_storage(
        self, platform_ids: List[str], max_news: int
    ) -> tuple[List[NewsItem], set]:
        """从存储管理器获取新闻"""
        news_items = []
        all_matched_concepts = set()

        # 获取今日热榜数据
        today = datetime.now().strftime("%Y-%m-%d")

        # 时间过滤：A股/港股只保留今天的，美股放宽到昨天21:00之后
        now = datetime.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        from datetime import timedelta
        yesterday_21pm = (now - timedelta(days=1)).replace(hour=21, minute=0, second=0, microsecond=0)

        for platform_id in platform_ids:
            try:
                # 尝试从数据库获取
                items = self._query_platform_news(platform_id, today)
                source_name = self.PLATFORM_NAMES.get(platform_id, platform_id)

                for item in items:
                    # 时间过滤：只保留今天和昨天21:00之后的新闻
                    published_str = item.get("published", "")
                    if published_str:
                        try:
                            pub_time = self._parse_published_time(published_str)
                            if pub_time:
                                # 检查时间是否符合要求
                                if pub_time >= yesterday_21pm:
                                    # 时间符合要求，保留
                                    pass
                                else:
                                    # 时间太早，跳过
                                    continue
                        except Exception as e:
                            # 时间解析失败，保留新闻
                            logger.debug(f"时间解析失败: {published_str}, 错误: {e}")

                    # 检查是否匹配关注的概念
                    matched = self._match_concepts(item.get("title", ""), item.get("summary", ""))
                    if matched or not self.concepts:  # 如果没有配置概念，则全部保留
                        news_item = NewsItem(
                            title=item.get("title", ""),
                            source=source_name,
                            url=item.get("url", ""),
                            published=published_str or today,
                            summary=item.get("summary", ""),
                            matched_concepts=matched,
                        )
                        news_items.append(news_item)
                        all_matched_concepts.update(matched)

                        if len(news_items) >= max_news:
                            break
            except Exception as e:
                logger.warning(f"获取平台 {platform_id} 新闻失败: {e}")

            if len(news_items) >= max_news:
                break

        return news_items, all_matched_concepts

    def _query_platform_news(self, platform_id: str, date: str) -> List[Dict[str, Any]]:
        """查询平台新闻数据（直接读取热榜数据库）"""
        items = []

        try:
            from pathlib import Path
            import sqlite3
            
            news_dir = Path("output/news")
            if not news_dir.exists():
                logger.debug(f"新闻目录不存在: {news_dir}")
                return items
            
            # 查找可用的数据库文件（优先使用今天的，否则使用最近的）
            db_path = news_dir / f"{date}.db"
            
            # 检查数据库文件是否有效（存在且大小 > 0）
            def is_valid_db(path: Path) -> bool:
                return path.exists() and path.stat().st_size > 1024
            
            if not is_valid_db(db_path):
                # 查找最近的有效数据库
                db_files = sorted(
                    [f for f in news_dir.glob("20*.db") if is_valid_db(f)],
                    key=lambda x: x.name,
                    reverse=True
                )
                if db_files:
                    db_path = db_files[0]
                    logger.info(f"使用最近的新闻数据库: {db_path.name}")
                else:
                    logger.warning(f"没有找到有效的新闻数据库")
                    return items
            
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            
            # 查询热榜新闻（使用created_at获取完整日期时间）
            # created_at包含完整日期，用于时间过滤
            cursor.execute("""
                SELECT title, url, rank, created_at as published
                FROM news_items
                WHERE platform_id = ?
                ORDER BY rank ASC
                LIMIT 50
            """, (platform_id,))

            rows = cursor.fetchall()
            for row in rows:
                items.append({
                    "title": row[0],
                    "url": row[1],
                    "rank": row[2],
                    "published": row[3],
                    "summary": "",
                })
            
            conn.close()
            logger.info(f"从 {platform_id} 获取到 {len(items)} 条新闻")
            
        except Exception as e:
            logger.warning(f"查询数据库失败: {e}")

        return items

    def _match_concepts(self, title: str, summary: str) -> List[str]:
        """
        检查标题和摘要是否包含关注的概念

        Args:
            title: 标题
            summary: 摘要

        Returns:
            List[str]: 匹配到的概念列表
        """
        matched = []
        text = f"{title} {summary}".lower()

        for concept in self.concepts:
            # 简单的关键词匹配
            if concept.lower() in text:
                matched.append(concept)
            # 处理英文大小写
            elif re.search(rf'\b{re.escape(concept)}\b', text, re.IGNORECASE):
                matched.append(concept)

        return matched

    @staticmethod
    def _normalize_config(config: Dict[str, Any]) -> Dict[str, Any]:
        """将配置键名转为小写（支持 load_config 输出的大写键）"""
        def lower_keys(d):
            if isinstance(d, dict):
                return {k.lower(): lower_keys(v) for k, v in d.items()}
            elif isinstance(d, list):
                return [lower_keys(item) for item in d]
            return d
        return lower_keys(config)

    @classmethod
    def from_config(cls, config: Dict[str, Any], storage_manager=None) -> "InvestmentCollector":
        """
        从配置创建收集器实例

        Args:
            config: 完整配置字典（支持大写或小写键）
            storage_manager: 存储管理器

        Returns:
            InvestmentCollector: 收集器实例
        """
        # 获取投资配置（支持大写和小写键）
        investment_config = config.get("INVESTMENT", config.get("investment", {}))
        # 转为小写键以统一处理
        normalized_config = cls._normalize_config(investment_config)
        return cls(normalized_config, storage_manager)
