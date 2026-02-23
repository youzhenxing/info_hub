# coding=utf-8
"""
播客 RSS 抓取器

负责从播客 RSS 源抓取节目信息，解析 enclosure 获取音频 URL
"""

import time
import random
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Any

import requests

try:
    import feedparser
    HAS_FEEDPARSER = True
except ImportError:
    HAS_FEEDPARSER = False
    feedparser = None

from trendradar.utils.time import get_configured_time, DEFAULT_TIMEZONE


@dataclass
class PodcastEpisode:
    """播客节目数据模型"""

    # 基础信息
    feed_id: str                        # 播客源 ID
    feed_name: str = ""                 # 播客源名称
    title: str = ""                     # 节目标题
    url: str = ""                       # 节目页面 URL
    guid: str = ""                      # RSS 条目唯一标识

    # 音频信息
    audio_url: str = ""                 # 音频文件 URL
    audio_type: str = ""                # 音频 MIME 类型
    audio_length: int = 0               # 音频文件大小（字节）
    duration: str = ""                  # 音频时长 (来自 itunes:duration)

    # 发布信息
    published_at: str = ""              # 发布时间 (ISO 8601)
    author: str = ""                    # 作者/主播
    summary: str = ""                   # 节目简介

    # 抓取信息
    crawl_time: str = ""                # 抓取时间

    def __post_init__(self):
        """确保 guid 有值"""
        if not self.guid:
            self.guid = self.audio_url or self.url


@dataclass
class PodcastFeedConfig:
    """播客源配置"""
    id: str                             # 源 ID
    name: str                           # 显示名称
    url: str                            # RSS URL
    enabled: bool = True                # 是否启用
    max_items: int = 10                 # 最大条目数（0=不限制）


class PodcastParser:
    """播客 RSS 解析器

    解析播客 RSS，提取 enclosure 音频附件和 iTunes 专有字段
    """

    # 支持的音频 MIME 类型
    AUDIO_MIME_TYPES = [
        "audio/mpeg",
        "audio/mp3",
        "audio/x-m4a",
        "audio/mp4",
        "audio/aac",
        "audio/ogg",
        "audio/wav",
        "audio/x-wav",
    ]

    def __init__(self, max_summary_length: int = 5000):
        """
        初始化解析器
        
        Args:
            max_summary_length: show notes 最大长度（默认 5000 字符）
                               设为 0 表示不限制，保留完整内容
        """
        if not HAS_FEEDPARSER:
            raise ImportError("播客解析需要安装 feedparser: pip install feedparser")
        self.max_summary_length = max_summary_length

    def parse(self, content: str, feed_url: str = "") -> List[Dict[str, Any]]:
        """
        解析播客 RSS 内容

        Args:
            content: RSS 内容
            feed_url: RSS URL（用于错误提示）

        Returns:
            解析后的节目列表（字典格式）
        """
        feed = feedparser.parse(content)

        if feed.bozo and not feed.entries:
            raise ValueError(f"播客 RSS 解析失败 ({feed_url}): {feed.bozo_exception}")

        items = []
        for entry in feed.entries:
            item = self._parse_entry(entry)
            if item and item.get("audio_url"):  # 只保留有音频的条目
                items.append(item)

        return items

    def _parse_entry(self, entry: Any) -> Optional[Dict[str, Any]]:
        """解析单个 RSS 条目"""
        # 提取音频附件
        audio_info = self._find_audio_enclosure(entry)
        if not audio_info:
            return None  # 没有音频附件，跳过

        # 基础信息
        title = self._clean_text(entry.get("title", ""))
        if not title:
            return None

        url = entry.get("link", "")

        # GUID
        guid = entry.get("id") or entry.get("guid", {})
        if isinstance(guid, dict):
            guid = guid.get("value", "")
        guid = guid or audio_info["url"] or url

        # 发布时间
        published_at = self._parse_date(entry)

        # 作者
        author = self._parse_author(entry)

        # 摘要
        summary = self._parse_summary(entry)

        # iTunes 时长
        duration = self._parse_duration(entry)

        return {
            "title": title,
            "url": url,
            "guid": guid,
            "audio_url": audio_info["url"],
            "audio_type": audio_info["type"],
            "audio_length": audio_info["length"],
            "duration": duration,
            "published_at": published_at,
            "author": author,
            "summary": summary,
        }

    def _find_audio_enclosure(self, entry: Any) -> Optional[Dict[str, Any]]:
        """
        从 RSS 条目中查找音频附件

        优先级：
        1. enclosures 中的音频类型
        2. links 中 rel=enclosure 的音频
        3. media_content 中的音频
        """
        # 方式1：标准 enclosures
        enclosures = entry.get("enclosures", [])
        for enc in enclosures:
            mime_type = enc.get("type", "").lower()
            if any(audio_type in mime_type for audio_type in self.AUDIO_MIME_TYPES):
                return {
                    "url": enc.get("href", "") or enc.get("url", ""),
                    "type": mime_type,
                    "length": self._safe_int(enc.get("length", 0)),
                }

        # 方式2：links 中的 enclosure
        links = entry.get("links", [])
        for link in links:
            if link.get("rel") == "enclosure":
                mime_type = link.get("type", "").lower()
                if any(audio_type in mime_type for audio_type in self.AUDIO_MIME_TYPES):
                    return {
                        "url": link.get("href", ""),
                        "type": mime_type,
                        "length": self._safe_int(link.get("length", 0)),
                    }

        # 方式3：media_content（某些播客使用）
        media_content = entry.get("media_content", [])
        for media in media_content:
            mime_type = media.get("type", "").lower()
            if any(audio_type in mime_type for audio_type in self.AUDIO_MIME_TYPES):
                return {
                    "url": media.get("url", ""),
                    "type": mime_type,
                    "length": self._safe_int(media.get("filesize", 0)),
                }

        return None

    def _parse_duration(self, entry: Any) -> str:
        """
        解析播客时长

        支持 iTunes 格式：HH:MM:SS, MM:SS, 或秒数
        """
        # itunes:duration
        duration = entry.get("itunes_duration", "")
        if duration:
            return str(duration)

        # 备用：media:content 中的 duration 属性
        media_content = entry.get("media_content", [])
        for media in media_content:
            if media.get("duration"):
                return str(media.get("duration"))

        return ""

    def _parse_date(self, entry: Any) -> Optional[str]:
        """解析发布日期"""
        from email.utils import parsedate_to_datetime

        # feedparser 会自动解析日期到 published_parsed
        date_struct = entry.get("published_parsed") or entry.get("updated_parsed")

        if date_struct:
            try:
                dt = datetime(*date_struct[:6])
                return dt.isoformat()
            except (ValueError, TypeError):
                pass

        # 尝试手动解析
        date_str = entry.get("published") or entry.get("updated")
        if date_str:
            try:
                dt = parsedate_to_datetime(date_str)
                return dt.isoformat()
            except (ValueError, TypeError):
                pass

            # 尝试 ISO 格式
            try:
                dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                return dt.isoformat()
            except (ValueError, TypeError):
                pass

        return None

    def _parse_author(self, entry: Any) -> Optional[str]:
        """解析作者/主播"""
        # itunes:author
        author = entry.get("itunes_author") or entry.get("author")
        if author:
            return self._clean_text(author)

        # dc:creator
        author = entry.get("dc_creator")
        if author:
            return self._clean_text(author)

        # authors 列表
        authors = entry.get("authors", [])
        if authors:
            names = [a.get("name", "") for a in authors if a.get("name")]
            if names:
                return ", ".join(names)

        return None

    def _parse_summary(self, entry: Any) -> Optional[str]:
        """解析摘要"""
        # itunes:summary 优先
        summary = entry.get("itunes_summary") or entry.get("summary") or entry.get("description", "")

        if not summary:
            # 尝试从 content 获取
            content = entry.get("content", [])
            if content and isinstance(content, list):
                summary = content[0].get("value", "")

        if not summary:
            return None

        summary = self._clean_text(summary)

        # 截断过长的摘要
        if len(summary) > self.max_summary_length:
            summary = summary[:self.max_summary_length] + "..."

        return summary

    def _clean_text(self, text: str) -> str:
        """清理文本（移除 HTML 标签等）"""
        import re
        import html

        if not text:
            return ""

        # 解码 HTML 实体
        text = html.unescape(text)

        # 移除 HTML 标签
        text = re.sub(r'<[^>]+>', '', text)

        # 移除多余空白
        text = re.sub(r'\s+', ' ', text)

        return text.strip()

    def _safe_int(self, value: Any) -> int:
        """安全转换为整数"""
        try:
            return int(value)
        except (ValueError, TypeError):
            return 0


class PodcastFetcher:
    """播客 RSS 抓取器"""

    def __init__(
        self,
        feeds: List[PodcastFeedConfig],
        request_interval: int = 2000,
        timeout: int = 30,
        use_proxy: bool = False,
        proxy_url: str = "",
        timezone: str = DEFAULT_TIMEZONE,
    ):
        """
        初始化抓取器

        Args:
            feeds: 播客源配置列表
            request_interval: 请求间隔（毫秒）
            timeout: 请求超时（秒）
            use_proxy: 是否使用代理
            proxy_url: 代理 URL
            timezone: 时区配置
        """
        self.feeds = [f for f in feeds if f.enabled]
        self.request_interval = request_interval
        self.timeout = timeout
        self.use_proxy = use_proxy
        self.proxy_url = proxy_url
        self.timezone = timezone

        self.parser = PodcastParser()
        self.session = self._create_session()

    def _create_session(self) -> requests.Session:
        """创建请求会话"""
        session = requests.Session()
        session.headers.update({
            "User-Agent": "TrendRadar/2.0 Podcast Reader (https://github.com/trendradar)",
            "Accept": "application/rss+xml, application/xml, text/xml, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        })

        if self.use_proxy and self.proxy_url:
            session.proxies = {
                "http": self.proxy_url,
                "https": self.proxy_url,
            }

        return session

    def fetch_feed(self, feed: PodcastFeedConfig) -> Tuple[List[PodcastEpisode], Optional[str]]:
        """
        抓取单个播客源

        Args:
            feed: 播客源配置

        Returns:
            (节目列表, 错误信息) 元组
        """
        try:
            response = self.session.get(feed.url, timeout=self.timeout)
            response.raise_for_status()

            parsed_items = self.parser.parse(response.text, feed.url)

            # 限制条目数量
            if feed.max_items > 0:
                parsed_items = parsed_items[:feed.max_items]

            # 获取当前时间
            now = get_configured_time(self.timezone)
            crawl_time = now.strftime("%Y-%m-%d %H:%M:%S")

            # 转换为 PodcastEpisode
            episodes = []
            for item in parsed_items:
                episode = PodcastEpisode(
                    feed_id=feed.id,
                    feed_name=feed.name,
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    guid=item.get("guid", ""),
                    audio_url=item.get("audio_url", ""),
                    audio_type=item.get("audio_type", ""),
                    audio_length=item.get("audio_length", 0),
                    duration=item.get("duration", ""),
                    published_at=item.get("published_at", ""),
                    author=item.get("author", ""),
                    summary=item.get("summary", ""),
                    crawl_time=crawl_time,
                )
                episodes.append(episode)

            print(f"[Podcast] {feed.name}: 获取 {len(episodes)} 个节目")
            return episodes, None

        except requests.Timeout:
            error = f"请求超时 ({self.timeout}s)"
            print(f"[Podcast] {feed.name}: {error}")
            return [], error

        except requests.RequestException as e:
            error = f"请求失败: {e}"
            print(f"[Podcast] {feed.name}: {error}")
            return [], error

        except ValueError as e:
            error = f"解析失败: {e}"
            print(f"[Podcast] {feed.name}: {error}")
            return [], error

        except Exception as e:
            error = f"未知错误: {e}"
            print(f"[Podcast] {feed.name}: {error}")
            return [], error

    def fetch_all(self) -> Dict[str, List[PodcastEpisode]]:
        """
        抓取所有播客源

        Returns:
            {feed_id: [PodcastEpisode, ...]} 字典
        """
        all_episodes: Dict[str, List[PodcastEpisode]] = {}

        print(f"[Podcast] 开始抓取 {len(self.feeds)} 个播客源...")

        for i, feed in enumerate(self.feeds):
            # 请求间隔（带随机波动）
            if i > 0:
                interval = self.request_interval / 1000
                jitter = random.uniform(-0.2, 0.2) * interval
                time.sleep(interval + jitter)

            episodes, error = self.fetch_feed(feed)

            if not error and episodes:
                all_episodes[feed.id] = episodes

        total_episodes = sum(len(eps) for eps in all_episodes.values())
        print(f"[Podcast] 抓取完成: {len(all_episodes)} 个源, 共 {total_episodes} 个节目")

        return all_episodes

    @classmethod
    def from_config(cls, config: Dict) -> "PodcastFetcher":
        """
        从配置字典创建抓取器

        Args:
            config: 配置字典（来自 config.yaml 的 podcast 段）

        Returns:
            PodcastFetcher 实例
        """
        feeds = []
        for feed_config in config.get("feeds", []):
            feed = PodcastFeedConfig(
                id=feed_config.get("id", ""),
                name=feed_config.get("name", ""),
                url=feed_config.get("url", ""),
                enabled=feed_config.get("enabled", True),
                max_items=feed_config.get("max_items", 10),
            )
            if feed.id and feed.url and feed.enabled:
                feeds.append(feed)

        return cls(
            feeds=feeds,
            request_interval=config.get("request_interval", 2000),
            timeout=config.get("timeout", 30),
            use_proxy=config.get("use_proxy", False),
            proxy_url=config.get("proxy_url", ""),
            timezone=config.get("timezone", DEFAULT_TIMEZONE),
        )
