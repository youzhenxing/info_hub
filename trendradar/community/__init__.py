# coding=utf-8
"""
TrendRadar 社区内容监控模块

监控 HackerNews、Reddit、Twitter、Kickstarter 等社区平台热点内容
通过 AI 聚合分析后以统一邮件推送

使用方式：
    from trendradar.community import CommunityProcessor

    processor = CommunityProcessor.from_config(config)
    results = processor.run()
"""

from .collector import CommunityCollector, CollectedData, SourceData
from .analyzer import CommunityAnalyzer, AnalysisResult, ItemAnalysis, SourceAnalysis
from .notifier import CommunityNotifier, NotifyResult
from .processor import CommunityProcessor, ProcessResult

__all__ = [
    # 核心处理器
    "CommunityProcessor",
    "ProcessResult",
    # 数据收集
    "CommunityCollector",
    "CollectedData",
    "SourceData",
    # AI 分析
    "CommunityAnalyzer",
    "AnalysisResult",
    # 通知推送
    "CommunityNotifier",
    "NotifyResult",
]
