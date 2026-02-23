# coding=utf-8
"""
社区内容处理器

协调数据收集、AI 分析和邮件推送的完整流程
"""

import time
from typing import Dict, Optional
from dataclasses import dataclass
from datetime import datetime

from .collector import CommunityCollector, CollectedData
from .analyzer import CommunityAnalyzer, AnalysisResult
from .notifier import CommunityNotifier, NotifyResult


@dataclass
class ProcessResult:
    """处理结果"""
    success: bool
    collected_count: int = 0
    analyzed: bool = False
    notified: bool = False
    duration_seconds: float = 0
    error: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "success": self.success,
            "collected_count": self.collected_count,
            "analyzed": self.analyzed,
            "notified": self.notified,
            "duration_seconds": self.duration_seconds,
            "error": self.error,
        }


class CommunityProcessor:
    """
    社区内容处理器
    
    完整流程：
    1. 从各平台收集内容
    2. AI 评分和筛选
    3. AI 深度分析
    4. 生成邮件并发送
    """
    
    def __init__(
        self,
        collector: CommunityCollector,
        analyzer: CommunityAnalyzer,
        notifier: CommunityNotifier,
        enabled: bool = True,
        test_mode: bool = False,
    ):
        """
        初始化处理器

        Args:
            collector: 数据收集器
            analyzer: AI 分析器
            notifier: 邮件通知器
            enabled: 是否启用
            test_mode: 测试模式开关
        """
        self.collector = collector
        self.analyzer = analyzer
        self.notifier = notifier
        self.enabled = enabled
        self.test_mode = test_mode
    
    def run(self) -> ProcessResult:
        """
        执行完整处理流程
        
        Returns:
            ProcessResult 对象
        """
        if not self.enabled:
            print("[CommunityProcessor] 社区监控已禁用")
            return ProcessResult(success=False, error="社区监控已禁用")
        
        start_time = time.time()
        
        try:
            print("=" * 60)
            print(f"[CommunityProcessor] 开始处理 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print("=" * 60)
            
            # 1. 收集数据
            print("\n📥 阶段 1: 数据收集")
            print("-" * 40)
            data = self.collector.collect()
            
            if data.total_items == 0:
                print("[CommunityProcessor] ⚠️ 未收集到任何数据")
                return ProcessResult(
                    success=False,
                    error="未收集到数据",
                    duration_seconds=time.time() - start_time,
                )
            
            print(f"[CommunityProcessor] ✅ 收集完成: {data.total_items} 条")
            
            # 2. AI 分析（逐案例详细分析）
            print("\n🤖 阶段 2: AI 分析（逐案例详细分析）")
            print("-" * 40)
            # quick_mode=False 启用逐案例 AI 分析
            # items_per_source 控制每个来源分析的案例数量
            analysis = self.analyzer.analyze(data, quick_mode=False, items_per_source=10)
            
            if not analysis.success:
                print(f"[CommunityProcessor] ⚠️ AI 分析失败: {analysis.error}")
                # 继续执行，使用空分析结果
                analysis = AnalysisResult(success=False, error=analysis.error)
            else:
                print("[CommunityProcessor] ✅ AI 分析完成")
            
            # 3. 发送通知
            print("\n📧 阶段 3: 邮件推送")
            print("-" * 40)
            notify_results = self.notifier.notify(data, analysis)
            
            notified = any(r.success for r in notify_results.values())
            if notified:
                print("[CommunityProcessor] ✅ 邮件发送成功")
            else:
                errors = [f"{k}: {v.error}" for k, v in notify_results.items() if v.error]
                print(f"[CommunityProcessor] ⚠️ 邮件发送失败: {errors}")
            
            # 完成
            duration = time.time() - start_time
            print("\n" + "=" * 60)
            print(f"[CommunityProcessor] ✅ 处理完成，耗时 {duration:.1f} 秒")
            print("=" * 60)
            
            return ProcessResult(
                success=True,
                collected_count=data.total_items,
                analyzed=analysis.success,
                notified=notified,
                duration_seconds=duration,
            )
            
        except Exception as e:
            duration = time.time() - start_time
            print(f"[CommunityProcessor] ❌ 处理失败: {e}")
            import traceback
            traceback.print_exc()
            
            return ProcessResult(
                success=False,
                error=str(e),
                duration_seconds=duration,
            )
    
    @classmethod
    def from_config(cls, config: dict, test_mode: bool = False) -> "CommunityProcessor":
        """
        从配置创建处理器

        Args:
            config: 完整配置字典
            test_mode: 测试模式开关

        Returns:
            CommunityProcessor 实例
        """
        community_config = config.get("COMMUNITY", config.get("community", {}))
        enabled = community_config.get("enabled", True)

        collector = CommunityCollector.from_config(config)
        analyzer = CommunityAnalyzer.from_config(config)
        notifier = CommunityNotifier.from_config(config)

        return cls(
            collector=collector,
            analyzer=analyzer,
            notifier=notifier,
            enabled=enabled,
            test_mode=test_mode,
        )


def run_community_monitor(config: dict = None) -> ProcessResult:
    """
    运行社区监控（便捷函数）
    
    Args:
        config: 配置字典（可选，不传则自动加载）
        
    Returns:
        ProcessResult 对象
    """
    if config is None:
        from trendradar.core import load_config
        config = load_config()
    
    processor = CommunityProcessor.from_config(config)
    return processor.run()
