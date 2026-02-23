# coding=utf-8
"""
TrendRadar 播客模块

提供播客 RSS 监听、音频下载、ASR 转写、AI 分析和即时推送功能

使用方式：
    from trendradar.podcast import PodcastProcessor

    processor = PodcastProcessor.from_config(config)
    results = processor.run()
"""

from .fetcher import PodcastFetcher, PodcastFeedConfig, PodcastEpisode
from .downloader import AudioDownloader, DownloadResult
from .transcriber import ASRTranscriber, TranscribeResult
from .analyzer import PodcastAnalyzer, AnalysisResult
from .notifier import PodcastNotifier, NotifyResult
from .processor import PodcastProcessor, ProcessResult

__all__ = [
    # 核心处理器
    "PodcastProcessor",
    "ProcessResult",
    # RSS 抓取
    "PodcastFetcher",
    "PodcastFeedConfig",
    "PodcastEpisode",
    # 音频下载
    "AudioDownloader",
    "DownloadResult",
    # ASR 转写
    "ASRTranscriber",
    "TranscribeResult",
    # AI 分析
    "PodcastAnalyzer",
    "AnalysisResult",
    # 通知推送
    "PodcastNotifier",
    "NotifyResult",
]
