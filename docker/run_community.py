#!/usr/bin/env python3
# coding=utf-8
"""
社区监控模块独立运行脚本

用于 cron 定时触发社区热点推送
"""

import sys
import os
import logging

# 添加项目路径
sys.path.insert(0, '/app')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger(__name__)


def main():
    """运行社区监控模块"""
    try:
        from trendradar.core import load_config
        from trendradar.community import CommunityProcessor

        logger.info("=" * 50)
        logger.info("社区监控模块定时任务启动")
        logger.info("=" * 50)

        # 加载配置
        config = load_config()

        # 创建处理器并运行
        processor = CommunityProcessor.from_config(config)
        result = processor.run()

        if result.success:
            logger.info(f"✅ 社区热点推送成功")
            logger.info(f"   收集条目: {result.collected_count}")
            logger.info(f"   AI 分析: {'成功' if result.analyzed else '跳过/失败'}")
            logger.info(f"   邮件发送: {'成功' if result.notified else '失败'}")
            logger.info(f"   总耗时: {result.duration_seconds:.1f} 秒")
        else:
            logger.error(f"❌ 社区热点推送失败: {result.error}")
            sys.exit(1)

    except Exception as e:
        logger.error(f"❌ 社区监控模块运行失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
