# coding=utf-8
"""
投资板块主处理器

协调数据收集、AI 分析和通知推送的完整流程
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from .collector import InvestmentCollector, CollectedData
from .analyzer import InvestmentAnalyzer, AnalysisResult
from .notifier import InvestmentNotifier, NotifyResult

logger = logging.getLogger(__name__)


@dataclass
class ProcessResult:
    """处理结果"""
    success: bool
    market_type: str              # cn 或 us
    data: Optional[CollectedData] = None
    analysis: Optional[AnalysisResult] = None
    notify_results: Dict[str, NotifyResult] = None
    error: str = ""
    duration_seconds: float = 0


class InvestmentProcessor:
    """
    投资板块处理器

    负责协调完整的处理流程：
    1. 收集行情数据和财经新闻
    2. AI 分析生成投资简报
    3. 推送邮件通知
    """

    def __init__(
        self,
        config: Dict[str, Any],
        storage_manager=None,
    ):
        """
        初始化处理器

        Args:
            config: 完整配置字典
            storage_manager: 存储管理器（用于获取热榜数据）
        """
        self.config = config
        self.investment_config = config.get("INVESTMENT", config.get("investment", {}))
        self.enabled = self.investment_config.get("ENABLED", self.investment_config.get("enabled", False))

        # 初始化子模块
        self.collector = InvestmentCollector.from_config(config, storage_manager)
        self.analyzer = InvestmentAnalyzer.from_config(config)
        self.notifier = InvestmentNotifier.from_config(config)

        # 调度配置（支持大写和小写键）
        raw_schedule = self.investment_config.get("SCHEDULE", self.investment_config.get("schedule", {}))
        # 统一转换为小写键
        self.schedule_config = {}
        for key, value in raw_schedule.items():
            lower_key = key.lower()
            if isinstance(value, dict):
                self.schedule_config[lower_key] = {k.lower(): v for k, v in value.items()}
            else:
                self.schedule_config[lower_key] = value

    def run(self, market_type: str = "cn") -> ProcessResult:
        """
        运行投资板块处理流程

        Args:
            market_type: 市场类型（cn=A股/港股，us=美股）

        Returns:
            ProcessResult: 处理结果
        """
        start_time = datetime.now()
        market_name = "A股/港股" if market_type == "cn" else "美股"

        logger.info(f"{'='*50}")
        logger.info(f"开始处理投资简报 ({market_name})")
        logger.info(f"{'='*50}")

        if not self.enabled:
            logger.info("投资板块未启用，跳过处理")
            return ProcessResult(
                success=False,
                market_type=market_type,
                error="投资板块未启用"
            )

        # 检查该市场档次是否启用
        schedule = self.schedule_config.get(market_type, {})
        if not schedule.get("enabled", False):
            logger.info(f"{market_name} 档未启用，跳过处理")
            return ProcessResult(
                success=False,
                market_type=market_type,
                error=f"{market_name} 档未启用"
            )

        try:
            # 1. 收集数据
            logger.info("步骤 1/3: 收集行情数据和财经新闻...")
            data = self.collector.collect()
            logger.info(f"数据收集完成")

            # 2. AI 分析
            logger.info("步骤 2/3: AI 分析生成投资简报...")
            analysis = self.analyzer.analyze(data)
            if analysis.success:
                logger.info(f"AI 分析完成，内容长度: {len(analysis.content)} 字符")
            else:
                logger.warning(f"AI 分析失败: {analysis.error}")

            # 3. 推送通知
            logger.info("步骤 3/3: 推送投资简报邮件...")
            notify_results = self.notifier.notify(data, analysis, market_type)

            # 统计结果
            success_count = sum(1 for r in notify_results.values() if r.success)
            total_count = len(notify_results)
            logger.info(f"推送完成: {success_count}/{total_count} 成功")

            # 计算耗时
            duration = (datetime.now() - start_time).total_seconds()

            logger.info(f"{'='*50}")
            logger.info(f"投资简报处理完成 ({market_name})")
            logger.info(f"总耗时: {duration:.1f} 秒")
            logger.info(f"{'='*50}")

            return ProcessResult(
                success=True,
                market_type=market_type,
                data=data,
                analysis=analysis,
                notify_results=notify_results,
                duration_seconds=duration,
            )

        except Exception as e:
            logger.error(f"投资简报处理失败: {e}")
            import traceback
            traceback.print_exc()

            duration = (datetime.now() - start_time).total_seconds()
            return ProcessResult(
                success=False,
                market_type=market_type,
                error=str(e),
                duration_seconds=duration,
            )

    def run_cn(self) -> ProcessResult:
        """运行 A股/港股 档处理"""
        return self.run(market_type="cn")

    def run_us(self) -> ProcessResult:
        """运行美股档处理"""
        return self.run(market_type="us")

    def should_run(self, market_type: str = "cn") -> bool:
        """
        检查是否应该运行

        Args:
            market_type: 市场类型

        Returns:
            bool: 是否应该运行
        """
        if not self.enabled:
            return False

        schedule = self.schedule_config.get(market_type, {})
        return schedule.get("enabled", False)

    def get_schedule_time(self, market_type: str = "cn") -> Optional[str]:
        """
        获取调度时间

        Args:
            market_type: 市场类型

        Returns:
            str: 调度时间（如 "11:50"）
        """
        schedule = self.schedule_config.get(market_type, {})
        return schedule.get("time")

    @classmethod
    def from_config(cls, config: Dict[str, Any], storage_manager=None) -> "InvestmentProcessor":
        """
        从配置创建处理器实例

        Args:
            config: 完整配置字典
            storage_manager: 存储管理器

        Returns:
            InvestmentProcessor: 处理器实例
        """
        return cls(config, storage_manager)
