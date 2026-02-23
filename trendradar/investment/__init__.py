# coding=utf-8
"""
TrendRadar 投资板块模块

提供行情数据获取、财经新闻聚合、AI 分析和定时推送功能

使用方式：
    from trendradar.investment import InvestmentProcessor

    processor = InvestmentProcessor.from_config(config)
    results = processor.run()
"""

from .market_data import MarketDataFetcher, MarketSnapshot
from .collector import InvestmentCollector, CollectedData
from .analyzer import InvestmentAnalyzer, AnalysisResult
from .notifier import InvestmentNotifier, NotifyResult
from .processor import InvestmentProcessor, ProcessResult

__all__ = [
    # 核心处理器
    "InvestmentProcessor",
    "ProcessResult",
    # 行情数据
    "MarketDataFetcher",
    "MarketSnapshot",
    # 数据收集
    "InvestmentCollector",
    "CollectedData",
    # AI 分析
    "InvestmentAnalyzer",
    "AnalysisResult",
    # 通知推送
    "InvestmentNotifier",
    "NotifyResult",
]
