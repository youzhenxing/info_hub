#!/usr/bin/env python3
# coding=utf-8
"""
投资模块独立运行脚本

用于 cron 定时触发投资报告推送
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
    """运行投资模块"""
    try:
        from trendradar.core import load_config
        from trendradar.investment import InvestmentProcessor

        logger.info("=" * 50)
        logger.info("投资模块定时任务启动")
        logger.info("=" * 50)

        # 加载配置
        config = load_config()

        # 强制启用投资模块（cron 触发时忽略 enabled 配置）
        if "investment" not in config:
            config["investment"] = {}
        config["investment"]["enabled"] = True
        
        # 确保 cn 市场启用
        if "schedule" not in config["investment"]:
            config["investment"]["schedule"] = {}
        if "cn" not in config["investment"]["schedule"]:
            config["investment"]["schedule"]["cn"] = {}
        config["investment"]["schedule"]["cn"]["enabled"] = True

        # 创建处理器并运行
        processor = InvestmentProcessor.from_config(config)
        result = processor.run_cn()

        if result.success:
            logger.info(f"✅ 投资报告推送成功，耗时 {result.duration_seconds:.1f} 秒")
        else:
            logger.error(f"❌ 投资报告推送失败: {result.error}")
            sys.exit(1)

    except Exception as e:
        logger.error(f"❌ 投资模块运行失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
