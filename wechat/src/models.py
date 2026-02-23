"""
数据模型定义
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List
from enum import Enum


class FeedType(Enum):
    """公众号类型"""
    CRITICAL = "critical"  # 第一类：关键信息
    NORMAL = "normal"      # 第二类：普通信息


class AccountStatus(Enum):
    """Wewe-RSS 账号状态"""
    ACTIVE = "active"           # 正常
    EXPIRED = "expired"         # 失效
    DISABLED = "disabled"       # 禁用
    BLACKLISTED = "blacklisted" # 今日小黑屋


@dataclass
class WechatFeed:
    """公众号配置"""
    id: str                     # 唯一标识
    name: str                   # 显示名称
    wewe_feed_id: str          # Wewe-RSS 中的 feed ID
    feed_type: FeedType        # 公众号类型
    enabled: bool = True


@dataclass
class Article:
    """文章数据"""
    id: str                     # 文章唯一ID（URL hash）
    feed_id: str               # 公众号 ID
    feed_name: str             # 公众号名称
    feed_type: FeedType        # 公众号类型
    title: str                 # 文章标题
    url: str                   # 文章链接
    content: str               # 文章正文（HTML）
    summary: Optional[str] = None      # 文章摘要（RSS 提供的）
    published_at: Optional[datetime] = None  # 发布时间
    collected_at: datetime = field(default_factory=datetime.now)  # 采集时间
    
    # AI 分析结果
    ai_summary: Optional[str] = None   # AI 生成的摘要
    
    def __hash__(self):
        return hash(self.id)


@dataclass
class DataNumber:
    """数据与数字"""
    content: str               # 具体数据内容
    context: str               # 数据背景/含义
    source: str                # 来源文章标题


@dataclass
class EventNews:
    """事件与动态"""
    content: str               # 事件描述
    time: str                  # 时间
    parties: str               # 相关方
    source: str                # 来源文章标题


@dataclass
class InsiderInsight:
    """内幕与洞察"""
    content: str               # 内幕/洞察内容
    insight_type: str          # 类型（内幕消息/独家判断/趋势预测/争议观点）
    source: str                # 来源文章标题


@dataclass
class TopicSource:
    """话题的来源引用"""
    title: str                 # 文章标题
    key_contribution: str      # 核心信息价值
    url: str = ""              # 文章链接（用于跳转）
    feed_name: str = ""        # 公众号名称


@dataclass
class Topic:
    """话题聚合结果"""
    name: str                  # 话题名称
    highlight: str             # 核心动态（一句话）
    articles: List[Article]    # 相关文章列表
    
    # 信息提取
    data_numbers: List[DataNumber] = field(default_factory=list)      # 数据与数字
    events_news: List[EventNews] = field(default_factory=list)        # 事件与动态
    insider_insights: List[InsiderInsight] = field(default_factory=list)  # 内幕与洞察
    sources: List[TopicSource] = field(default_factory=list)          # 来源引用
    
    # 兼容旧字段
    description: str = ""
    ai_analysis: str = ""
    key_dates: List[str] = field(default_factory=list)


@dataclass
class DailyReport:
    """每日报告数据"""
    date: datetime
    
    # 第一类公众号文章（带 AI 摘要）
    critical_articles: List[Article] = field(default_factory=list)
    
    # 第二类公众号话题聚合
    topics: List[Topic] = field(default_factory=list)
    
    # 所有文章（用于完整列表展示）
    all_articles: List[Article] = field(default_factory=list)
    
    # 统计信息
    total_articles: int = 0
    critical_count: int = 0
    normal_count: int = 0


@dataclass
class WeweAccount:
    """Wewe-RSS 账号信息"""
    id: str
    name: str
    status: AccountStatus
    last_update: Optional[datetime] = None
