#!/usr/bin/env python3
"""
微信公众号订阅模块 - 主入口

使用方法:
    python main.py run              # 执行完整流程（采集 + 分析 + 推送）
    python main.py scheduler        # 启动定时任务调度器
    python main.py bootstrap        # 版本首次启动引导
    python main.py bootstrap-status # 查询 Bootstrap 状态
    python main.py monitor          # 检查账号状态
    python main.py test-email       # 测试邮件发送
    python main.py config           # 查看配置信息
    python main.py stats            # 查看数据统计
    python main.py export           # 导出历史数据
"""

import sys
import logging
from datetime import datetime
from pathlib import Path

# 添加 src 目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from src.config_loader import ConfigLoader
from src.storage import Storage
from src.collector import WechatCollector
from src.analyzer import WechatAnalyzer
from src.notifier import WechatNotifier
from src.monitor import AccountMonitor

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def init_components():
    """初始化所有组件"""
    config = ConfigLoader("config.yaml")
    
    # 创建数据目录
    storage_config = config.storage
    Path(storage_config.data_dir).mkdir(parents=True, exist_ok=True)
    Path(storage_config.output_dir).mkdir(parents=True, exist_ok=True)
    
    # 初始化组件
    db_path = Path(storage_config.data_dir) / storage_config.db_name
    storage = Storage(str(db_path))
    
    collector = WechatCollector(config, storage)
    analyzer = WechatAnalyzer(config, storage)
    notifier = WechatNotifier(config)
    monitor = AccountMonitor(config, notifier)
    
    return config, storage, collector, analyzer, notifier, monitor


def cmd_run():
    """执行完整流程：采集 + 分析 + 推送"""
    logger.info("=" * 50)
    logger.info("微信公众号订阅 - 开始执行")
    logger.info("=" * 50)
    
    config, storage, collector, analyzer, notifier, monitor = init_components()

    # 读取测试配置
    import os
    test_config = config._config.get('test', {})
    test_mode = test_config.get('enabled', False) or os.getenv('TEST_MODE') == 'true'
    feed_limit = None
    test_feeds = None

    if test_mode:
        feed_limit = test_config.get('feed_limit', 3)
        test_feeds = test_config.get('test_feeds')
        logger.info(f"🧪 测试模式：限制处理 {feed_limit} 个公众号")
        if test_feeds:
            logger.info(f"🧪 测试模式：指定公众号 {test_feeds}")

    # 0. 首先检查账号登录状态
    logger.info("\n[Step 0/5] 检查账号状态")
    if not _check_account_status(config, notifier):
        logger.error("账号状态异常，停止处理")
        return

    # 1. 检查是否已推送（测试模式跳过检查）
    if not test_mode and storage.has_pushed_today():
        logger.info("今日已推送，跳过")
        return

    if test_mode and storage.has_pushed_today():
        logger.info("🧪 测试模式：忽略今日已推送检查，强制执行")

    # 2. 采集文章
    logger.info("\n[Step 1/5] 采集文章")
    articles = collector.collect_all(
        feed_limit=feed_limit,
        test_feeds=test_feeds,
    )
    
    if not articles:
        logger.warning("未获取到任何文章")
        # 仍然继续，可能数据库中有未处理的文章
    
    # 3. AI 分析
    logger.info("\n[Step 2/5] AI 分析")
    report = analyzer.analyze_daily()
    
    if report.total_articles == 0:
        logger.warning("没有文章需要推送")
        return
    
    # 4. 发送邮件
    logger.info("\n[Step 3/5] 发送邮件")
    success = notifier.send_daily_report(report)
    
    # 5. 记录推送
    if success:
        storage.record_push("daily", report.total_articles)
        logger.info("\n[Step 4/5] 推送完成")
    else:
        logger.error("\n[Step 4/5] 推送失败")
    
    # 6. 清理旧数据（改为归档而非删除）
    logger.info("\n[Step 5/5] 数据归档")
    retention_days = config.storage.retention_days
    if retention_days > 0:
        archived = storage.archive_old_data(retention_days)
        if archived > 0:
            logger.info(f"归档了 {archived} 条历史数据")
    
    logger.info("\n" + "=" * 50)
    logger.info("执行完成")
    logger.info("=" * 50)


def _check_account_status(config, notifier) -> bool:
    """
    检查账号登录状态
    
    Returns:
        True 如果账号有效，False 如果账号无效
    """
    import requests
    
    try:
        # 检查 Wewe-RSS 服务是否可用
        base_url = config.wewe_rss.base_url
        
        try:
            response = requests.get(f"{base_url}/feeds", timeout=10)
        except requests.exceptions.ConnectionError:
            logger.error(f"无法连接到 Wewe-RSS 服务: {base_url}")
            notifier.send_account_alert(
                account_name="Wewe-RSS 服务",
                message="无法连接到 Wewe-RSS 服务，请检查服务是否启动",
                external_url=config.wewe_rss.external_url
            )
            return False
        
        if response.status_code != 200:
            logger.error(f"Wewe-RSS 服务异常: HTTP {response.status_code}")
            return False
        
        # 检查是否有 feeds
        feeds = response.json()
        if isinstance(feeds, dict):
            feeds = feeds.get('data', [])
        
        if not feeds:
            logger.warning("Wewe-RSS 中没有配置任何公众号")
        else:
            logger.info(f"Wewe-RSS 账号有效，已配置 {len(feeds)} 个公众号")
        
        # 尝试检查账号状态
        try:
            acc_response = requests.get(f"{base_url}/accounts", timeout=10)
            if acc_response.status_code == 200:
                accounts = acc_response.json()
                if isinstance(accounts, dict):
                    accounts = accounts.get('data', [])
                
                # 检查是否有有效账号
                valid_accounts = [
                    a for a in accounts
                    if a.get('status', '').lower() in ['enable', 'enabled', 'active', 'valid', '1', 'true', 'normal', '正常']
                ]
                
                if not accounts:
                    logger.warning("未找到微信读书账号，发送提醒")
                    notifier.send_account_alert(
                        account_name="微信读书账号",
                        message="未找到任何微信读书账号，请登录 Wewe-RSS 添加账号",
                        external_url=config.wewe_rss.external_url
                    )
                    return False
                
                if not valid_accounts and len(accounts) > 0:
                    logger.warning("所有微信读书账号已失效，发送提醒")
                    notifier.send_account_alert(
                        account_name="微信读书账号",
                        message="所有微信读书账号已失效，请重新登录",
                        external_url=config.wewe_rss.external_url
                    )
                    return False
        except Exception as e:
            # 如果无法检查账号状态，但 feeds 正常，继续执行
            logger.warning(f"无法检查账号详细状态: {e}")
        
        return True
        
    except Exception as e:
        logger.error(f"检查账号状态出错: {e}")
        return False


def cmd_bootstrap():
    """版本首次启动引导：随机扫描3个公众号并触发推送（不保存数据库）"""
    import os
    import random
    import time as time_module
    from datetime import datetime

    # 初始化 bootstrap 专属 logger（双写: stdout + 文件）
    bootstrap_logger = logging.getLogger("wechat.bootstrap")
    bootstrap_logger.setLevel(logging.INFO)
    if not bootstrap_logger.handlers:
        fmt = logging.Formatter('%(asctime)s %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
        sh = logging.StreamHandler()
        sh.setFormatter(fmt)
        bootstrap_logger.addHandler(sh)
        try:
            Path("data").mkdir(parents=True, exist_ok=True)
            fh = logging.FileHandler("data/bootstrap.log")
            fh.setFormatter(fmt)
            bootstrap_logger.addHandler(fh)
        except Exception:
            pass

    app_version = os.getenv("APP_VERSION", "")
    marker_path = Path("data/.wechat_bootstrap_done")

    bootstrap_logger.info("[Wechat][Bootstrap] ═══ 启动引导检查 ═══")
    bootstrap_logger.info(f"[Wechat][Bootstrap] APP_VERSION={app_version}")

    # 版本比较
    marker_version = ""
    if marker_path.exists():
        marker_version = marker_path.read_text().strip()
    bootstrap_logger.info(f"[Wechat][Bootstrap] 标记文件版本={marker_version or '(不存在)'}")

    if app_version and marker_version == app_version:
        bootstrap_logger.info(f"[Wechat][Bootstrap] 当前版本 {app_version} 已完成引导，跳过")
        return

    if not app_version:
        bootstrap_logger.warning("[Wechat][Bootstrap] APP_VERSION 未设置，跳过引导")
        return

    # 初始化组件
    config, storage, collector, analyzer, notifier, monitor = init_components()

    # 获取全部公众号
    all_feeds = config.get_feeds(batch='all')
    bootstrap_logger.info(f"[Wechat][Bootstrap] 全部公众号数: {len(all_feeds)}")

    if not all_feeds:
        bootstrap_logger.warning("[Wechat][Bootstrap] 没有公众号可扫描")
        marker_path.write_text(app_version)
        return

    # 随机选取 3 个
    sample_count = min(3, len(all_feeds))
    selected_feeds = random.sample(all_feeds, sample_count)
    bootstrap_logger.info(
        f"[Wechat][Bootstrap] 随机选取{sample_count}个: "
        + ", ".join(f"{f.name}(id={f.wewe_feed_id})" for f in selected_feeds)
    )

    # ✅ 逐个采集（仅内存中，不保存数据库）
    all_articles = []
    for feed in selected_feeds:
        start = time_module.time()
        try:
            articles = collector._collect_feed(feed)
            all_articles.extend(articles)
            elapsed = time_module.time() - start
            bootstrap_logger.info(
                f"[Wechat][Bootstrap] 采集 {feed.name}: {len(articles)}篇 | 耗时={elapsed:.1f}s"
            )
        except Exception as e:
            elapsed = time_module.time() - start
            bootstrap_logger.error(
                f"[Wechat][Bootstrap] 采集 {feed.name} 失败: {e} | 耗时={elapsed:.1f}s"
            )

    # ✅ 如果采集到文章，直接构造并发送邮件（不保存数据库）
    if all_articles:
        bootstrap_logger.info(f"[Wechat][Bootstrap] 共采集 {len(all_articles)} 篇，触发推送（不保存数据库）...")

        try:
            # ✅ 构造简化的 DailyReport（直接使用内存中的文章）
            from src.models import DailyReport, Article, Topic, FeedType

            # 区分第一类和第二类文章
            critical_articles = [a for a in all_articles if a.feed_type == FeedType.CRITICAL]
            normal_articles = [a for a in all_articles if a.feed_type == FeedType.NORMAL]

            bootstrap_logger.info(f"[Wechat][Bootstrap] 第一类: {len(critical_articles)} 篇，第二类: {len(normal_articles)} 篇")

            # 构造报告
            report = DailyReport(
                date=datetime.now(),
                critical_articles=critical_articles,
                topics=[],  # 跳过话题聚合
                total_articles=len(all_articles),
                critical_count=len(critical_articles),
                normal_count=len(normal_articles)
            )

            # 发送邮件
            bootstrap_logger.info(f"[Wechat][Bootstrap] 发送邮件 ({report.total_articles} 篇)...")
            success = notifier.send_daily_report(report)

            if success:
                # 记录推送（类型为 bootstrap，不与 daily 冲突）
                storage.record_push("bootstrap", report.total_articles)
                bootstrap_logger.info(f"[Wechat][Bootstrap] 推送成功 ✅")
            else:
                bootstrap_logger.error(f"[Wechat][Bootstrap] 推送失败 ❌")

        except Exception as e:
            bootstrap_logger.error(f"[Wechat][Bootstrap] 推送流程失败: {e}")
            import traceback
            bootstrap_logger.error(f"[Wechat][Bootstrap] 错误详情: {traceback.format_exc()}")
    else:
        bootstrap_logger.warning(f"[Wechat][Bootstrap] 未采集到文章，跳过推送")

    # 更新标记文件
    marker_path.write_text(app_version)
    bootstrap_logger.info(f"[Wechat][Bootstrap] 标记更新 → {app_version} ✅")


def cmd_scheduler():
    """启动定时任务调度器"""
    import schedule
    import time
    
    config, storage, collector, analyzer, notifier, monitor = init_components()
    
    # 每日报告时间
    report_time = config.daily_report_time
    
    # 账号监控间隔
    monitor_interval = config.account_monitor_interval
    
    logger.info("=" * 50)
    logger.info("微信公众号订阅 - 定时任务调度器")
    logger.info(f"每日报告时间: {report_time}")
    logger.info(f"账号监控间隔: {monitor_interval} 小时")
    logger.info("=" * 50)
    
    # 定义任务
    def daily_task():
        try:
            cmd_run()
        except Exception as e:
            logger.error(f"每日任务执行失败: {e}")
    
    def monitor_task():
        try:
            logger.info("执行账号状态检查")
            monitor.check_accounts()
        except Exception as e:
            logger.error(f"账号监控执行失败: {e}")
    
    # 设置定时任务
    schedule.every().day.at(report_time).do(daily_task)
    schedule.every(monitor_interval).hours.do(monitor_task)
    
    # 启动时执行引导检查
    try:
        cmd_bootstrap()
    except Exception as e:
        logger.error(f"Bootstrap 执行失败: {e}")

    # 启动时执行一次账号检查
    monitor_task()
    
    logger.info("调度器已启动，等待任务执行...")
    
    # 运行调度器
    while True:
        schedule.run_pending()
        time.sleep(60)  # 每分钟检查一次


def cmd_monitor():
    """检查账号状态"""
    logger.info("检查 Wewe-RSS 账号状态")
    
    config, storage, collector, analyzer, notifier, monitor = init_components()
    
    accounts = monitor.check_accounts()
    
    if not accounts:
        print("\n未获取到账号信息，请检查：")
        print(f"  1. Wewe-RSS 服务是否运行: {config.wewe_rss.base_url}")
        print(f"  2. 授权码是否正确")
        return
    
    print(f"\n找到 {len(accounts)} 个账号：")
    print("-" * 50)
    
    for account in accounts:
        status_emoji = {
            'active': '✅',
            'expired': '❌',
            'disabled': '⏸️',
            'blacklisted': '🚫'
        }.get(account.status.value, '❓')
        
        print(f"  {status_emoji} {account.name}")
        print(f"     状态: {account.status.value}")
        if account.last_update:
            print(f"     更新: {account.last_update.strftime('%Y-%m-%d %H:%M:%S')}")
        print()


def cmd_test_email():
    """测试邮件发送"""
    logger.info("测试邮件发送")
    
    config, storage, collector, analyzer, notifier, monitor = init_components()
    
    # 创建测试报告
    from src.models import DailyReport, Article, Topic, FeedType
    
    test_article = Article(
        id="test_001",
        feed_id="test",
        feed_name="测试公众号",
        feed_type=FeedType.CRITICAL,
        title="测试文章标题 - 这是一篇用于测试邮件发送的文章",
        url="https://example.com/test",
        content="这是测试文章的内容。",
        ai_summary="这是 AI 生成的测试摘要。文章主要讨论了邮件测试的重要性。"
    )
    
    test_topic = Topic(
        name="测试话题",
        description="这是一个用于测试的话题聚合",
        articles=[test_article],
        ai_analysis="这是 AI 对话题的分析。测试邮件功能正常工作。"
    )
    
    test_report = DailyReport(
        date=datetime.now(),
        critical_articles=[test_article],
        topics=[test_topic],
        total_articles=1,
        critical_count=1,
        normal_count=0
    )
    
    print("\n发送测试邮件...")
    success = notifier.send_daily_report(test_report)
    
    if success:
        print("✅ 测试邮件发送成功！")
        print(f"   请检查收件箱: {config.email.to_addr}")
    else:
        print("❌ 测试邮件发送失败")
        print("   请检查邮件配置是否正确")


def cmd_config():
    """查看配置信息"""
    config = ConfigLoader("config.yaml")
    
    print("\n" + "=" * 50)
    print("微信公众号订阅模块 - 配置信息")
    print("=" * 50)
    
    print("\n📌 Wewe-RSS 配置:")
    print(f"   内部地址: {config.wewe_rss.base_url}")
    print(f"   外部地址: {config.wewe_rss.external_url}")
    print(f"   授权码: {'已配置' if config.wewe_rss.auth_code else '未配置'}")
    
    print("\n📌 AI 配置:")
    print(f"   模型: {config.ai.model}")
    print(f"   API Key: {'已配置' if config.ai.api_key else '未配置'}")
    print(f"   API Base: {config.ai.api_base or '默认'}")
    
    print("\n📌 邮件配置:")
    print(f"   发件人: {config.email.from_addr or '未配置'}")
    print(f"   收件人: {config.email.to_addr or '未配置'}")
    print(f"   密码: {'已配置' if config.email.password else '未配置'}")
    
    print("\n📌 推送配置:")
    print(f"   每日推送时间: {config.daily_report_time}")
    print(f"   账号监控: {'启用' if config.account_monitor_enabled else '禁用'}")
    print(f"   监控间隔: {config.account_monitor_interval} 小时")
    
    print("\n📌 公众号列表:")
    feeds = config.get_feeds()
    if feeds:
        critical_feeds = [f for f in feeds if f.feed_type.value == 'critical']
        normal_feeds = [f for f in feeds if f.feed_type.value == 'normal']
        
        print(f"   第一类（关键信息）: {len(critical_feeds)} 个")
        for f in critical_feeds:
            print(f"     - {f.name} ({f.wewe_feed_id})")
        
        print(f"   第二类（普通信息）: {len(normal_feeds)} 个")
        for f in normal_feeds:
            print(f"     - {f.name} ({f.wewe_feed_id})")
    else:
        print("   未配置任何公众号")
    
    print("\n" + "=" * 50)


def cmd_stats():
    """查看数据统计"""
    config, storage, collector, analyzer, notifier, monitor = init_components()
    
    stats = storage.get_article_stats()
    
    print("\n" + "=" * 50)
    print("📊 微信公众号数据统计")
    print("=" * 50)
    
    print(f"\n总文章数: {stats['total_articles']}")
    print(f"已处理: {stats['processed_articles']}")
    print(f"已归档: {stats['archived_articles']}")
    
    print("\n按公众号统计:")
    for feed, count in sorted(stats['articles_by_feed'].items(), key=lambda x: -x[1]):
        print(f"  • {feed}: {count} 篇")
    
    print("\n按日期统计（近30天）:")
    for date, count in list(stats['articles_by_date'].items())[:10]:
        print(f"  • {date}: {count} 篇")
    
    print("\n" + "=" * 50)


def cmd_export():
    """导出数据"""
    config, storage, collector, analyzer, notifier, monitor = init_components()
    
    # 导出目录
    export_dir = Path(config.storage.data_dir) / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    
    # 导出文件名
    filename = f"wechat_articles_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    export_path = export_dir / filename
    
    print(f"\n导出数据到: {export_path}")
    
    count = storage.export_articles_json(str(export_path), include_archived=True)
    
    print(f"✅ 导出完成，共 {count} 篇文章")
    print(f"   文件位置: {export_path}")


def cmd_bootstrap_status():
    """查询 Bootstrap 执行状态"""
    import os

    marker_path = Path("data/.wechat_bootstrap_done")
    app_version = os.getenv("APP_VERSION", "")

    print("\n" + "=" * 50)
    print("📊 Bootstrap 状态查询")
    print("=" * 50)

    print(f"\n当前版本: {app_version or '(未设置)'}")

    if marker_path.exists():
        marker_version = marker_path.read_text().strip()
        print(f"标记版本: {marker_version}")

        if app_version == marker_version:
            print("状态: ✅ 已完成引导")
            print("说明: 当前版本已完成首次启动引导")
        else:
            print(f"状态: ⚠️  版本不匹配")
            print(f"  - 当前版本: {app_version or '(未设置)'}")
            print(f"  - 标记版本: {marker_version}")
            print("建议: 手动执行 bootstrap 命令更新引导")
            print("  命令: python main.py bootstrap")
    else:
        print("标记版本: (不存在)")
        print("状态: ❌ 未完成引导")
        print("说明: 首次启动时会自动执行引导")

    print("\n" + "=" * 50)


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    commands = {
        'run': cmd_run,
        'scheduler': cmd_scheduler,
        'bootstrap': cmd_bootstrap,
        'bootstrap-status': cmd_bootstrap_status,
        'monitor': cmd_monitor,
        'test-email': cmd_test_email,
        'config': cmd_config,
        'stats': cmd_stats,
        'export': cmd_export,
    }
    
    if command in commands:
        commands[command]()
    else:
        print(f"未知命令: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
