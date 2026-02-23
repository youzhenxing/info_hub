# coding=utf-8
"""
TrendRadar 主程序

热点新闻聚合与分析工具
支持: python -m trendradar
"""

import os
import re
import webbrowser
from pathlib import Path
from typing import Dict, List, Tuple, Optional

import requests

from trendradar.context import AppContext
from trendradar import __version__
from trendradar.core import load_config
from trendradar.core.analyzer import convert_keyword_stats_to_platform_stats
from trendradar.crawler import DataFetcher
from trendradar.storage import convert_crawl_results_to_news_data
from trendradar.utils.time import is_within_days
from trendradar.ai import AIAnalyzer, AIAnalysisResult


def _parse_version(version_str: str) -> Tuple[int, int, int]:
    """解析版本号字符串为元组"""
    try:
        parts = version_str.strip().split(".")
        if len(parts) >= 3:
            return int(parts[0]), int(parts[1]), int(parts[2])
        return 0, 0, 0
    except:
        return 0, 0, 0


def _compare_version(local: str, remote: str) -> str:
    """比较版本号，返回状态文字"""
    local_tuple = _parse_version(local)
    remote_tuple = _parse_version(remote)

    if local_tuple < remote_tuple:
        return "⚠️ 需要更新"
    elif local_tuple > remote_tuple:
        return "🔮 超前版本"
    else:
        return "✅ 已是最新"


def _fetch_remote_version(version_url: str, proxy_url: Optional[str] = None) -> Optional[str]:
    """获取远程版本号"""
    try:
        proxies = None
        if proxy_url:
            proxies = {"http": proxy_url, "https": proxy_url}

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/plain, */*",
            "Cache-Control": "no-cache",
        }

        response = requests.get(version_url, proxies=proxies, headers=headers, timeout=10)
        response.raise_for_status()
        return response.text.strip()
    except Exception as e:
        print(f"[版本检查] 获取远程版本失败: {e}")
        return None


def _parse_config_versions(content: str) -> Dict[str, str]:
    """解析配置文件版本内容为字典"""
    versions = {}
    try:
        if not content:
            return versions
        for line in content.splitlines():
            line = line.strip()
            if not line or "=" not in line:
                continue
            name, version = line.split("=", 1)
            versions[name.strip()] = version.strip()
    except Exception as e:
        print(f"[版本检查] 解析配置版本失败: {e}")
    return versions


def check_all_versions(
    version_url: str,
    configs_version_url: Optional[str] = None,
    proxy_url: Optional[str] = None
) -> Tuple[bool, Optional[str]]:
    """
    统一版本检查：程序版本 + 配置文件版本

    Args:
        version_url: 远程程序版本检查 URL
        configs_version_url: 远程配置文件版本检查 URL (返回格式: filename=version)
        proxy_url: 代理 URL

    Returns:
        (need_update, remote_version): 程序是否需要更新及远程版本号
    """
    # 获取远程版本
    remote_version = _fetch_remote_version(version_url, proxy_url)

    # 获取远程配置版本（如果有提供 URL）
    remote_config_versions = {}
    if configs_version_url:
        content = _fetch_remote_version(configs_version_url, proxy_url)
        if content:
            remote_config_versions = _parse_config_versions(content)

    print("=" * 60)
    print("版本检查")
    print("=" * 60)

    if remote_version:
        print(f"远程程序版本: {remote_version}")
    else:
        print("远程程序版本: 获取失败")

    if configs_version_url:
        if remote_config_versions:
            print(f"远程配置清单: 获取成功 ({len(remote_config_versions)} 个文件)")
        else:
            print("远程配置清单: 获取失败或为空")

    print("-" * 60)

    program_status = _compare_version(__version__, remote_version) if remote_version else "(无法比较)"
    print(f"  主程序版本: {__version__} {program_status}")

    config_files = [
        Path("config/config.yaml"),
        Path("config/frequency_words.txt"),
        Path("config/ai_analysis_prompt.txt"),
        Path("config/ai_translation_prompt.txt"),
    ]

    version_pattern = re.compile(r"Version:\s*(\d+\.\d+\.\d+)", re.IGNORECASE)

    for config_file in config_files:
        if not config_file.exists():
            print(f"  {config_file.name}: 文件不存在")
            continue

        try:
            with open(config_file, "r", encoding="utf-8") as f:
                local_version = None
                for i, line in enumerate(f):
                    if i >= 20:
                        break
                    match = version_pattern.search(line)
                    if match:
                        local_version = match.group(1)
                        break

                # 获取该文件的远程版本
                target_remote_version = remote_config_versions.get(config_file.name)

                if local_version:
                    if target_remote_version:
                        status = _compare_version(local_version, target_remote_version)
                        print(f"  {config_file.name}: {local_version} {status}")
                    else:
                        print(f"  {config_file.name}: {local_version} (未找到远程版本)")
                else:
                    print(f"  {config_file.name}: 未找到本地版本号")
        except Exception as e:
            print(f"  {config_file.name}: 读取失败 - {e}")

    print("=" * 60)

    # 返回程序版本的更新状态
    if remote_version:
        need_update = _parse_version(__version__) < _parse_version(remote_version)
        return need_update, remote_version if need_update else None
    return False, None


# === 主分析器 ===
class NewsAnalyzer:
    """新闻分析器"""

    # 模式策略定义
    MODE_STRATEGIES = {
        "incremental": {
            "mode_name": "增量模式",
            "description": "增量模式（只关注新增新闻，无新增时不推送）",
            "report_type": "增量分析",
            "should_send_notification": True,
        },
        "current": {
            "mode_name": "当前榜单模式",
            "description": "当前榜单模式（当前榜单匹配新闻 + 新增新闻区域 + 按时推送）",
            "report_type": "当前榜单",
            "should_send_notification": True,
        },
        "daily": {
            "mode_name": "全天汇总模式",
            "description": "全天汇总模式（所有匹配新闻 + 新增新闻区域 + 按时推送）",
            "report_type": "全天汇总",
            "should_send_notification": True,
        },
    }

    def __init__(self, config: Optional[Dict] = None):
        # 使用传入的配置或加载新配置
        if config is None:
            print("正在加载配置...")
            config = load_config()
        print(f"TrendRadar v{__version__} 配置加载完成")
        print(f"监控平台数量: {len(config['PLATFORMS'])}")
        print(f"时区: {config.get('TIMEZONE', 'Asia/Shanghai')}")

        # 创建应用上下文
        self.ctx = AppContext(config)

        self.request_interval = self.ctx.config["REQUEST_INTERVAL"]
        self.report_mode = self.ctx.config["REPORT_MODE"]
        self.rank_threshold = self.ctx.rank_threshold
        self.is_github_actions = os.environ.get("GITHUB_ACTIONS") == "true"
        self.is_docker_container = self._detect_docker_environment()
        self.update_info = None
        self.proxy_url = None
        self._setup_proxy()
        self.data_fetcher = DataFetcher(self.proxy_url)

        # 初始化存储管理器（使用 AppContext）
        self._init_storage_manager()
        # 注意：update_info 由 main() 函数设置，避免重复请求远程版本

    def _init_storage_manager(self) -> None:
        """初始化存储管理器（使用 AppContext）"""
        # 获取数据保留天数（支持环境变量覆盖）
        env_retention = os.environ.get("STORAGE_RETENTION_DAYS", "").strip()
        if env_retention:
            # 环境变量覆盖配置
            self.ctx.config["STORAGE"]["RETENTION_DAYS"] = int(env_retention)

        self.storage_manager = self.ctx.get_storage_manager()
        print(f"存储后端: {self.storage_manager.backend_name}")

        retention_days = self.ctx.config.get("STORAGE", {}).get("RETENTION_DAYS", 0)
        if retention_days > 0:
            print(f"数据保留天数: {retention_days} 天")

    def _detect_docker_environment(self) -> bool:
        """检测是否运行在 Docker 容器中"""
        try:
            if os.environ.get("DOCKER_CONTAINER") == "true":
                return True

            if os.path.exists("/.dockerenv"):
                return True

            return False
        except Exception:
            return False

    def _should_open_browser(self) -> bool:
        """判断是否应该打开浏览器"""
        return not self.is_github_actions and not self.is_docker_container

    def _setup_proxy(self) -> None:
        """设置代理配置"""
        if not self.is_github_actions and self.ctx.config["USE_PROXY"]:
            self.proxy_url = self.ctx.config["DEFAULT_PROXY"]
            print("本地环境，使用代理")
        elif not self.is_github_actions and not self.ctx.config["USE_PROXY"]:
            print("本地环境，未启用代理")
        else:
            print("GitHub Actions环境，不使用代理")

    def _set_update_info_from_config(self) -> None:
        """从已缓存的远程版本设置更新信息（不再重复请求）"""
        try:
            version_url = self.ctx.config.get("VERSION_CHECK_URL", "")
            if not version_url:
                return

            remote_version = _fetch_remote_version(version_url, self.proxy_url)
            if remote_version:
                need_update = _parse_version(__version__) < _parse_version(remote_version)
                if need_update:
                    self.update_info = {
                        "current_version": __version__,
                        "remote_version": remote_version,
                    }
        except Exception as e:
            print(f"版本检查出错: {e}")

    def _get_mode_strategy(self) -> Dict:
        """获取当前模式的策略配置"""
        return self.MODE_STRATEGIES.get(self.report_mode, self.MODE_STRATEGIES["daily"])

    def _has_notification_configured(self) -> bool:
        """检查是否配置了任何通知渠道"""
        cfg = self.ctx.config
        return any(
            [
                cfg["FEISHU_WEBHOOK_URL"],
                cfg["DINGTALK_WEBHOOK_URL"],
                cfg["WEWORK_WEBHOOK_URL"],
                (cfg["TELEGRAM_BOT_TOKEN"] and cfg["TELEGRAM_CHAT_ID"]),
                (
                    cfg["EMAIL_FROM"]
                    and cfg["EMAIL_PASSWORD"]
                    and cfg["EMAIL_TO"]
                ),
                (cfg["NTFY_SERVER_URL"] and cfg["NTFY_TOPIC"]),
                cfg["BARK_URL"],
                cfg["SLACK_WEBHOOK_URL"],
                cfg["GENERIC_WEBHOOK_URL"],
            ]
        )

    def _has_valid_content(
        self, stats: List[Dict], new_titles: Optional[Dict] = None
    ) -> bool:
        """检查是否有有效的新闻内容"""
        if self.report_mode == "incremental":
            # 增量模式：只要有匹配的新闻就推送
            # count_word_frequency 已经确保只处理新增的新闻（包括当天第一次爬取的情况）
            has_matched_news = any(stat["count"] > 0 for stat in stats)
            return has_matched_news
        elif self.report_mode == "current":
            # current模式：只要stats有内容就说明有匹配的新闻
            return any(stat["count"] > 0 for stat in stats)
        else:
            # 当日汇总模式下，检查是否有匹配的频率词新闻或新增新闻
            has_matched_news = any(stat["count"] > 0 for stat in stats)
            has_new_news = bool(
                new_titles and any(len(titles) > 0 for titles in new_titles.values())
            )
            return has_matched_news or has_new_news

    def _prepare_ai_analysis_data(
        self,
        ai_mode: str,
        current_results: Optional[Dict] = None,
        current_id_to_name: Optional[Dict] = None,
    ) -> Tuple[List[Dict], Optional[Dict]]:
        """
        为 AI 分析准备指定模式的数据

        Args:
            ai_mode: AI 分析模式 (daily/current/incremental)
            current_results: 当前抓取的结果（用于 incremental 模式）
            current_id_to_name: 当前的平台映射（用于 incremental 模式）

        Returns:
            Tuple[stats, id_to_name]: 统计数据和平台映射
        """
        try:
            word_groups, filter_words, global_filters = self.ctx.load_frequency_words()

            if ai_mode == "incremental":
                # incremental 模式：使用当前抓取的数据
                if not current_results or not current_id_to_name:
                    print("[AI] incremental 模式需要当前抓取数据，但未提供")
                    return [], None

                # 准备当前时间信息
                time_info = self.ctx.format_time()
                title_info = self._prepare_current_title_info(current_results, time_info)

                # 检测新增标题
                new_titles = self.ctx.detect_new_titles(list(current_results.keys()))

                # 统计计算
                stats, _ = self.ctx.count_frequency(
                    current_results,
                    word_groups,
                    filter_words,
                    current_id_to_name,
                    title_info,
                    new_titles,
                    mode="incremental",
                    global_filters=global_filters,
                    quiet=True,
                )

                # 如果是 platform 模式，转换数据结构
                if self.ctx.display_mode == "platform" and stats:
                    from trendradar.core.stats import convert_keyword_stats_to_platform_stats
                    stats = convert_keyword_stats_to_platform_stats(
                        stats,
                        self.ctx.weight_config,
                        self.ctx.rank_threshold,
                    )

                return stats, current_id_to_name

            elif ai_mode in ["daily", "current"]:
                # 加载历史数据
                analysis_data = self._load_analysis_data(quiet=True)
                if not analysis_data:
                    print(f"[AI] 无法加载历史数据用于 {ai_mode} 模式分析")
                    return [], None

                (
                    all_results,
                    id_to_name,
                    title_info,
                    new_titles,
                    _,
                    _,
                    _,
                ) = analysis_data

                # 统计计算
                stats, _ = self.ctx.count_frequency(
                    all_results,
                    word_groups,
                    filter_words,
                    id_to_name,
                    title_info,
                    new_titles,
                    mode=ai_mode,
                    global_filters=global_filters,
                    quiet=True,
                )

                # 如果是 platform 模式，转换数据结构
                if self.ctx.display_mode == "platform" and stats:
                    from trendradar.core.stats import convert_keyword_stats_to_platform_stats
                    stats = convert_keyword_stats_to_platform_stats(
                        stats,
                        self.ctx.weight_config,
                        self.ctx.rank_threshold,
                    )

                return stats, id_to_name
            else:
                print(f"[AI] 未知的 AI 模式: {ai_mode}")
                return [], None

        except Exception as e:
            print(f"[AI] 准备 {ai_mode} 模式数据时出错: {e}")
            if self.ctx.config.get("DEBUG", False):
                import traceback
                traceback.print_exc()
            return [], None

    def _run_ai_analysis(
        self,
        stats: List[Dict],
        rss_items: Optional[List[Dict]],
        mode: str,
        report_type: str,
        id_to_name: Optional[Dict],
        current_results: Optional[Dict] = None,
    ) -> Optional[AIAnalysisResult]:
        """执行 AI 分析"""
        analysis_config = self.ctx.config.get("AI_ANALYSIS", {})
        if not analysis_config.get("ENABLED", False):
            return None

        # AI 分析时间窗口控制
        analysis_window = analysis_config.get("ANALYSIS_WINDOW", {})
        if analysis_window.get("ENABLED", False):
            push_manager = self.ctx.create_push_manager()
            time_range_start = analysis_window["TIME_RANGE"]["START"]
            time_range_end = analysis_window["TIME_RANGE"]["END"]

            if not push_manager.is_in_time_range(time_range_start, time_range_end):
                now = self.ctx.get_time()
                print(
                    f"[AI] 分析窗口控制：当前时间 {now.strftime('%H:%M')} 不在分析时间窗口 {time_range_start}-{time_range_end} 内，跳过 AI 分析"
                )
                return None

            if analysis_window.get("ONCE_PER_DAY", False):
                # 检查今天是否已经进行过 AI 分析
                if push_manager.storage_backend.has_ai_analyzed_today():
                    print(f"[AI] 分析窗口控制：今天已分析过，跳过本次 AI 分析")
                    return None
                else:
                    print(f"[AI] 分析窗口控制：今天首次分析")

        print("[AI] 正在进行 AI 分析...")
        try:
            ai_config = self.ctx.config.get("AI", {})
            debug_mode = self.ctx.config.get("DEBUG", False)
            analyzer = AIAnalyzer(ai_config, analysis_config, self.ctx.get_time, debug=debug_mode)

            # 确定 AI 分析使用的模式
            ai_mode_config = analysis_config.get("MODE", "follow_report")
            if ai_mode_config == "follow_report":
                # 跟随推送报告模式
                ai_mode = mode
                ai_stats = stats
                ai_id_to_name = id_to_name
            elif ai_mode_config in ["daily", "current", "incremental"]:
                # 使用独立配置的模式，需要重新准备数据
                ai_mode = ai_mode_config
                if ai_mode != mode:
                    print(f"[AI] 使用独立分析模式: {ai_mode} (推送模式: {mode})")
                    print(f"[AI] 正在准备 {ai_mode} 模式的数据...")

                    # 根据 AI 模式重新准备数据
                    ai_stats, ai_id_to_name = self._prepare_ai_analysis_data(
                        ai_mode, current_results, id_to_name
                    )
                    if not ai_stats:
                        print(f"[AI] 警告: 无法准备 {ai_mode} 模式的数据，回退到推送模式数据")
                        ai_stats = stats
                        ai_id_to_name = id_to_name
                        ai_mode = mode
                else:
                    ai_stats = stats
                    ai_id_to_name = id_to_name
            else:
                # 配置错误，回退到跟随模式
                print(f"[AI] 警告: 无效的 ai_analysis.mode 配置 '{ai_mode_config}'，使用推送模式 '{mode}'")
                ai_mode = mode
                ai_stats = stats
                ai_id_to_name = id_to_name

            # 提取平台列表
            platforms = list(ai_id_to_name.values()) if ai_id_to_name else []

            # 提取关键词列表
            keywords = [s.get("word", "") for s in ai_stats if s.get("word")] if ai_stats else []

            # 确定报告类型
            if ai_mode != mode:
                # 根据 AI 模式确定报告类型
                ai_report_type = {
                    "daily": "当日汇总",
                    "current": "当前榜单",
                    "incremental": "增量更新"
                }.get(ai_mode, report_type)
            else:
                ai_report_type = report_type

            result = analyzer.analyze(
                stats=ai_stats,
                rss_stats=rss_items,
                report_mode=ai_mode,
                report_type=ai_report_type,
                platforms=platforms,
                keywords=keywords,
            )

            # 设置 AI 分析使用的模式
            if result.success:
                result.ai_mode = ai_mode
                if result.error:
                    # 成功但有警告（如 JSON 解析问题但使用了原始文本）
                    print(f"[AI] 分析完成（有警告: {result.error}）")
                else:
                    print("[AI] 分析完成")

                # 记录 AI 分析（如果启用了 once_per_day）
                if analysis_window.get("ENABLED", False) and analysis_window.get("ONCE_PER_DAY", False):
                    push_manager = self.ctx.create_push_manager()
                    push_manager.storage_backend.record_ai_analysis(ai_mode)
            else:
                print(f"[AI] 分析失败: {result.error}")

            return result
        except Exception as e:
            import traceback
            error_type = type(e).__name__
            error_msg = str(e)
            # 截断过长的错误消息
            if len(error_msg) > 200:
                error_msg = error_msg[:200] + "..."
            print(f"[AI] 分析出错 ({error_type}): {error_msg}")
            # 详细错误日志到 stderr
            import sys
            print(f"[AI] 详细错误堆栈:", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            return AIAnalysisResult(success=False, error=f"{error_type}: {error_msg}")

    def _load_analysis_data(
        self,
        quiet: bool = False,
    ) -> Optional[Tuple[Dict, Dict, Dict, Dict, List, List]]:
        """统一的数据加载和预处理，使用当前监控平台列表过滤历史数据"""
        try:
            # 获取当前配置的监控平台ID列表
            current_platform_ids = self.ctx.platform_ids
            if not quiet:
                print(f"当前监控平台: {current_platform_ids}")

            all_results, id_to_name, title_info = self.ctx.read_today_titles(
                current_platform_ids, quiet=quiet
            )

            if not all_results:
                print("没有找到当天的数据")
                return None

            total_titles = sum(len(titles) for titles in all_results.values())
            if not quiet:
                print(f"读取到 {total_titles} 个标题（已按当前监控平台过滤）")

            new_titles = self.ctx.detect_new_titles(current_platform_ids, quiet=quiet)
            word_groups, filter_words, global_filters = self.ctx.load_frequency_words()

            return (
                all_results,
                id_to_name,
                title_info,
                new_titles,
                word_groups,
                filter_words,
                global_filters,
            )
        except Exception as e:
            print(f"数据加载失败: {e}")
            return None

    def _prepare_current_title_info(self, results: Dict, time_info: str) -> Dict:
        """从当前抓取结果构建标题信息"""
        title_info = {}
        for source_id, titles_data in results.items():
            title_info[source_id] = {}
            for title, title_data in titles_data.items():
                ranks = title_data.get("ranks", [])
                url = title_data.get("url", "")
                mobile_url = title_data.get("mobileUrl", "")

                title_info[source_id][title] = {
                    "first_time": time_info,
                    "last_time": time_info,
                    "count": 1,
                    "ranks": ranks,
                    "url": url,
                    "mobileUrl": mobile_url,
                }
        return title_info

    def _prepare_standalone_data(
        self,
        results: Dict,
        id_to_name: Dict,
        title_info: Optional[Dict] = None,
        rss_items: Optional[List[Dict]] = None,
    ) -> Optional[Dict]:
        """
        从原始数据中提取独立展示区数据

        Args:
            results: 原始爬取结果 {platform_id: {title: title_data}}
            id_to_name: 平台 ID 到名称的映射
            title_info: 标题元信息（含排名历史、时间等）
            rss_items: RSS 条目列表

        Returns:
            独立展示数据字典，如果未启用返回 None
        """
        display_config = self.ctx.config.get("DISPLAY", {})
        regions = display_config.get("REGIONS", {})
        standalone_config = display_config.get("STANDALONE", {})

        if not regions.get("STANDALONE", False):
            return None

        platform_ids = standalone_config.get("PLATFORMS", [])
        rss_feed_ids = standalone_config.get("RSS_FEEDS", [])
        max_items = standalone_config.get("MAX_ITEMS", 20)

        if not platform_ids and not rss_feed_ids:
            return None

        standalone_data = {
            "platforms": [],
            "rss_feeds": [],
        }

        # 找出最新批次时间（类似 current 模式的过滤逻辑）
        latest_time = None
        if title_info:
            for source_titles in title_info.values():
                for title_data in source_titles.values():
                    last_time = title_data.get("last_time", "")
                    if last_time:
                        if latest_time is None or last_time > latest_time:
                            latest_time = last_time

        # 提取热榜平台数据
        for platform_id in platform_ids:
            if platform_id not in results:
                continue

            platform_name = id_to_name.get(platform_id, platform_id)
            platform_titles = results[platform_id]

            items = []
            for title, title_data in platform_titles.items():
                # 获取元信息（如果有 title_info）
                meta = {}
                if title_info and platform_id in title_info and title in title_info[platform_id]:
                    meta = title_info[platform_id][title]

                # 只保留当前在榜的话题（last_time 等于最新时间）
                if latest_time and meta:
                    if meta.get("last_time") != latest_time:
                        continue

                # 使用当前热榜的排名数据（title_data）进行排序
                # title_data 包含的是爬虫返回的当前排名，用于保证独立展示区的顺序与热榜一致
                current_ranks = title_data.get("ranks", [])
                current_rank = current_ranks[-1] if current_ranks else 0

                # 用于显示的排名范围：合并历史排名和当前排名
                historical_ranks = meta.get("ranks", []) if meta else []
                # 合并去重，保持顺序
                all_ranks = historical_ranks.copy()
                for rank in current_ranks:
                    if rank not in all_ranks:
                        all_ranks.append(rank)
                display_ranks = all_ranks if all_ranks else current_ranks

                item = {
                    "title": title,
                    "url": title_data.get("url", ""),
                    "mobileUrl": title_data.get("mobileUrl", ""),
                    "rank": current_rank,  # 用于排序的当前排名
                    "ranks": display_ranks,  # 用于显示的排名范围（历史+当前）
                    "first_time": meta.get("first_time", ""),
                    "last_time": meta.get("last_time", ""),
                    "count": meta.get("count", 1),
                }
                items.append(item)

            # 按当前排名排序
            items.sort(key=lambda x: x["rank"] if x["rank"] > 0 else 9999)

            # 限制条数
            if max_items > 0:
                items = items[:max_items]

            if items:
                standalone_data["platforms"].append({
                    "id": platform_id,
                    "name": platform_name,
                    "items": items,
                })

        # 提取 RSS 数据
        if rss_items and rss_feed_ids:
            # 按 feed_id 分组
            feed_items_map = {}
            for item in rss_items:
                feed_id = item.get("feed_id", "")
                if feed_id in rss_feed_ids:
                    if feed_id not in feed_items_map:
                        feed_items_map[feed_id] = {
                            "name": item.get("feed_name", feed_id),
                            "items": [],
                        }
                    feed_items_map[feed_id]["items"].append({
                        "title": item.get("title", ""),
                        "url": item.get("url", ""),
                        "published_at": item.get("published_at", ""),
                        "author": item.get("author", ""),
                    })

            # 限制条数并添加到结果
            for feed_id in rss_feed_ids:
                if feed_id in feed_items_map:
                    feed_data = feed_items_map[feed_id]
                    items = feed_data["items"]
                    if max_items > 0:
                        items = items[:max_items]
                    if items:
                        standalone_data["rss_feeds"].append({
                            "id": feed_id,
                            "name": feed_data["name"],
                            "items": items,
                        })

        # 如果没有任何数据，返回 None
        if not standalone_data["platforms"] and not standalone_data["rss_feeds"]:
            return None

        return standalone_data

    def _run_analysis_pipeline(
        self,
        data_source: Dict,
        mode: str,
        title_info: Dict,
        new_titles: Dict,
        word_groups: List[Dict],
        filter_words: List[str],
        id_to_name: Dict,
        failed_ids: Optional[List] = None,
        global_filters: Optional[List[str]] = None,
        quiet: bool = False,
        rss_items: Optional[List[Dict]] = None,
        rss_new_items: Optional[List[Dict]] = None,
        standalone_data: Optional[Dict] = None,
    ) -> Tuple[List[Dict], Optional[str], Optional[AIAnalysisResult]]:
        """统一的分析流水线：数据处理 → 统计计算 → AI分析 → HTML生成"""

        # 统计计算（使用 AppContext）
        stats, total_titles = self.ctx.count_frequency(
            data_source,
            word_groups,
            filter_words,
            id_to_name,
            title_info,
            new_titles,
            mode=mode,
            global_filters=global_filters,
            quiet=quiet,
        )

        # 如果是 platform 模式，转换数据结构
        if self.ctx.display_mode == "platform" and stats:
            stats = convert_keyword_stats_to_platform_stats(
                stats,
                self.ctx.weight_config,
                self.ctx.rank_threshold,
            )

        # AI 分析（如果启用，用于 HTML 报告）
        ai_result = None
        ai_config = self.ctx.config.get("AI_ANALYSIS", {})
        if ai_config.get("ENABLED", False) and stats:
            # 获取模式策略来确定报告类型
            mode_strategy = self._get_mode_strategy()
            report_type = mode_strategy["report_type"]
            ai_result = self._run_ai_analysis(
                stats, rss_items, mode, report_type, id_to_name, current_results=data_source
            )

        # HTML生成（如果启用）
        html_file = None
        if self.ctx.config["STORAGE"]["FORMATS"]["HTML"]:
            html_file = self.ctx.generate_html(
                stats,
                total_titles,
                failed_ids=failed_ids,
                new_titles=new_titles,
                id_to_name=id_to_name,
                mode=mode,
                update_info=self.update_info if self.ctx.config["SHOW_VERSION_UPDATE"] else None,
                rss_items=rss_items,
                rss_new_items=rss_new_items,
                ai_analysis=ai_result,
                standalone_data=standalone_data,
            )

        return stats, html_file, ai_result

    def _send_notification_if_needed(
        self,
        stats: List[Dict],
        report_type: str,
        mode: str,
        failed_ids: Optional[List] = None,
        new_titles: Optional[Dict] = None,
        id_to_name: Optional[Dict] = None,
        html_file_path: Optional[str] = None,
        rss_items: Optional[List[Dict]] = None,
        rss_new_items: Optional[List[Dict]] = None,
        standalone_data: Optional[Dict] = None,
        ai_result: Optional[AIAnalysisResult] = None,
        current_results: Optional[Dict] = None,
    ) -> bool:
        """统一的通知发送逻辑，包含所有判断条件，支持热榜+RSS合并推送+AI分析+独立展示区"""
        has_notification = self._has_notification_configured()
        cfg = self.ctx.config

        # 检查是否有有效内容（热榜或RSS）
        has_news_content = self._has_valid_content(stats, new_titles)
        has_rss_content = bool(rss_items and len(rss_items) > 0)
        has_any_content = has_news_content or has_rss_content

        # 计算热榜匹配条数
        news_count = sum(len(stat.get("titles", [])) for stat in stats) if stats else 0
        # rss_items 是统计列表 [{"word": "xx", "count": 5, ...}]，需累加 count
        rss_count = sum(stat.get("count", 0) for stat in rss_items) if rss_items else 0

        if (
            cfg["ENABLE_NOTIFICATION"]
            and has_notification
            and has_any_content
        ):
            # 输出推送内容统计
            content_parts = []
            if news_count > 0:
                content_parts.append(f"热榜 {news_count} 条")
            if rss_count > 0:
                content_parts.append(f"RSS {rss_count} 条")
            total_count = news_count + rss_count
            print(f"[推送] 准备发送：{' + '.join(content_parts)}，合计 {total_count} 条")

            # 推送窗口控制
            if cfg["PUSH_WINDOW"]["ENABLED"]:
                push_manager = self.ctx.create_push_manager()
                time_range_start = cfg["PUSH_WINDOW"]["TIME_RANGE"]["START"]
                time_range_end = cfg["PUSH_WINDOW"]["TIME_RANGE"]["END"]

                if not push_manager.is_in_time_range(time_range_start, time_range_end):
                    now = self.ctx.get_time()
                    print(
                        f"推送窗口控制：当前时间 {now.strftime('%H:%M')} 不在推送时间窗口 {time_range_start}-{time_range_end} 内，跳过推送"
                    )
                    return False

                if cfg["PUSH_WINDOW"]["ONCE_PER_DAY"]:
                    if push_manager.has_pushed_today():
                        print(f"推送窗口控制：今天已推送过，跳过本次推送")
                        return False
                    else:
                        print(f"推送窗口控制：今天首次推送")

            # AI 分析：优先使用传入的结果，避免重复分析
            if ai_result is None:
                ai_config = cfg.get("AI_ANALYSIS", {})
                if ai_config.get("ENABLED", False):
                    ai_result = self._run_ai_analysis(
                        stats, rss_items, mode, report_type, id_to_name, current_results=current_results
                    )

            # 准备报告数据
            report_data = self.ctx.prepare_report(stats, failed_ids, new_titles, id_to_name, mode)

            # 是否发送版本更新信息
            update_info_to_send = self.update_info if cfg["SHOW_VERSION_UPDATE"] else None

            # 使用 NotificationDispatcher 发送到所有渠道（合并热榜+RSS+AI分析+独立展示区）
            dispatcher = self.ctx.create_notification_dispatcher()
            results = dispatcher.dispatch_all(
                report_data=report_data,
                report_type=report_type,
                update_info=update_info_to_send,
                proxy_url=self.proxy_url,
                mode=mode,
                html_file_path=html_file_path,
                rss_items=rss_items,
                rss_new_items=rss_new_items,
                ai_analysis=ai_result,
                standalone_data=standalone_data,
            )

            if not results:
                print("未配置任何通知渠道，跳过通知发送")
                return False

            # 如果成功发送了任何通知，且启用了每天只推一次，则记录推送
            if (
                cfg["PUSH_WINDOW"]["ENABLED"]
                and cfg["PUSH_WINDOW"]["ONCE_PER_DAY"]
                and any(results.values())
            ):
                push_manager = self.ctx.create_push_manager()
                push_manager.record_push(report_type)

            return True

        elif cfg["ENABLE_NOTIFICATION"] and not has_notification:
            print("⚠️ 警告：通知功能已启用但未配置任何通知渠道，将跳过通知发送")
        elif not cfg["ENABLE_NOTIFICATION"]:
            print(f"跳过{report_type}通知：通知功能已禁用")
        elif (
            cfg["ENABLE_NOTIFICATION"]
            and has_notification
            and not has_any_content
        ):
            mode_strategy = self._get_mode_strategy()
            if self.report_mode == "incremental":
                if not has_rss_content:
                    print("跳过通知：增量模式下未检测到匹配的新闻和RSS")
                else:
                    print("跳过通知：增量模式下新闻未匹配到关键词")
            else:
                print(
                    f"跳过通知：{mode_strategy['mode_name']}下未检测到匹配的新闻"
                )

        return False

    def _initialize_and_check_config(self) -> bool:
        """通用初始化和配置检查
        
        Returns:
            bool: True 表示应该继续运行，False 表示应该退出
        """
        now = self.ctx.get_time()
        print(f"当前北京时间: {now.strftime('%Y-%m-%d %H:%M:%S')}")

        if not self.ctx.config["ENABLE_CRAWLER"]:
            print("爬虫功能已禁用（ENABLE_CRAWLER=False），跳过热榜抓取")
            return False

        has_notification = self._has_notification_configured()
        if not self.ctx.config["ENABLE_NOTIFICATION"]:
            print("通知功能已禁用（ENABLE_NOTIFICATION=False），将只进行数据抓取")
        elif not has_notification:
            print("未配置任何通知渠道，将只进行数据抓取，不发送通知")
        else:
            print("通知功能已启用，将发送通知")

        mode_strategy = self._get_mode_strategy()
        print(f"报告模式: {self.report_mode}")
        print(f"运行模式: {mode_strategy['description']}")
        
        return True

    def _crawl_data(self) -> Tuple[Dict, Dict, List]:
        """执行数据爬取"""
        ids = []
        for platform in self.ctx.platforms:
            if "name" in platform:
                ids.append((platform["id"], platform["name"]))
            else:
                ids.append(platform["id"])

        print(
            f"配置的监控平台: {[p.get('name', p['id']) for p in self.ctx.platforms]}"
        )
        print(f"开始爬取数据，请求间隔 {self.request_interval} 毫秒")
        Path("output").mkdir(parents=True, exist_ok=True)

        results, id_to_name, failed_ids = self.data_fetcher.crawl_websites(
            ids, self.request_interval
        )

        # 转换为 NewsData 格式并保存到存储后端
        crawl_time = self.ctx.format_time()
        crawl_date = self.ctx.format_date()
        news_data = convert_crawl_results_to_news_data(
            results, id_to_name, failed_ids, crawl_time, crawl_date
        )

        # 保存到存储后端（SQLite）
        if self.storage_manager.save_news_data(news_data):
            print(f"数据已保存到存储后端: {self.storage_manager.backend_name}")

        # 保存 TXT 快照（如果启用）
        txt_file = self.storage_manager.save_txt_snapshot(news_data)
        if txt_file:
            print(f"TXT 快照已保存: {txt_file}")

        # 兼容：同时保存到原有 TXT 格式（确保向后兼容）
        if self.ctx.config["STORAGE"]["FORMATS"]["TXT"]:
            title_file = self.ctx.save_titles(results, id_to_name, failed_ids)
            print(f"标题已保存到: {title_file}")

        return results, id_to_name, failed_ids

    def _crawl_rss_data(self) -> Tuple[Optional[List[Dict]], Optional[List[Dict]], Optional[List[Dict]]]:
        """
        执行 RSS 数据抓取

        Returns:
            (rss_items, rss_new_items, raw_rss_items) 元组：
            - rss_items: 统计条目列表（按模式处理，用于统计区块）
            - rss_new_items: 新增条目列表（用于新增区块）
            - raw_rss_items: 原始 RSS 条目列表（用于独立展示区）
            如果未启用或失败返回 (None, None, None)
        """
        if not self.ctx.rss_enabled:
            return None, None, None

        rss_feeds = self.ctx.rss_feeds
        if not rss_feeds:
            print("[RSS] 未配置任何 RSS 源")
            return None, None, None

        try:
            from trendradar.crawler.rss import RSSFetcher, RSSFeedConfig

            # 构建 RSS 源配置
            feeds = []
            for feed_config in rss_feeds:
                # 读取并验证单个 feed 的 max_age_days（可选）
                max_age_days_raw = feed_config.get("max_age_days")
                max_age_days = None
                if max_age_days_raw is not None:
                    try:
                        max_age_days = int(max_age_days_raw)
                        if max_age_days < 0:
                            feed_id = feed_config.get("id", "unknown")
                            print(f"[警告] RSS feed '{feed_id}' 的 max_age_days 为负数，将使用全局默认值")
                            max_age_days = None
                    except (ValueError, TypeError):
                        feed_id = feed_config.get("id", "unknown")
                        print(f"[警告] RSS feed '{feed_id}' 的 max_age_days 格式错误：{max_age_days_raw}")
                        max_age_days = None

                feed = RSSFeedConfig(
                    id=feed_config.get("id", ""),
                    name=feed_config.get("name", ""),
                    url=feed_config.get("url", ""),
                    max_items=feed_config.get("max_items", 50),
                    enabled=feed_config.get("enabled", True),
                    max_age_days=max_age_days,  # None=使用全局，0=禁用，>0=覆盖
                )
                if feed.id and feed.url and feed.enabled:
                    feeds.append(feed)

            if not feeds:
                print("[RSS] 没有启用的 RSS 源")
                return None, None, None

            # 创建抓取器
            rss_config = self.ctx.rss_config
            # RSS 代理：优先使用 RSS 专属代理，否则使用爬虫默认代理
            rss_proxy_url = rss_config.get("PROXY_URL", "") or self.proxy_url or ""
            # 获取配置的时区
            timezone = self.ctx.config.get("TIMEZONE", "Asia/Shanghai")
            # 获取新鲜度过滤配置
            freshness_config = rss_config.get("FRESHNESS_FILTER", {})
            freshness_enabled = freshness_config.get("ENABLED", True)
            default_max_age_days = freshness_config.get("MAX_AGE_DAYS", 3)

            fetcher = RSSFetcher(
                feeds=feeds,
                request_interval=rss_config.get("REQUEST_INTERVAL", 2000),
                timeout=rss_config.get("TIMEOUT", 15),
                use_proxy=rss_config.get("USE_PROXY", False),
                proxy_url=rss_proxy_url,
                timezone=timezone,
                freshness_enabled=freshness_enabled,
                default_max_age_days=default_max_age_days,
            )

            # 抓取数据
            rss_data = fetcher.fetch_all()

            # 保存到存储后端
            if self.storage_manager.save_rss_data(rss_data):
                print(f"[RSS] 数据已保存到存储后端")

                # 处理 RSS 数据（按模式过滤）并返回用于合并推送
                return self._process_rss_data_by_mode(rss_data)
            else:
                print(f"[RSS] 数据保存失败")
                return None, None, None

        except ImportError as e:
            print(f"[RSS] 缺少依赖: {e}")
            print("[RSS] 请安装 feedparser: pip install feedparser")
            return None, None, None
        except Exception as e:
            print(f"[RSS] 抓取失败: {e}")
            return None, None, None

    def _process_rss_data_by_mode(self, rss_data) -> Tuple[Optional[List[Dict]], Optional[List[Dict]], Optional[List[Dict]]]:
        """
        按报告模式处理 RSS 数据，返回与热榜相同格式的统计结构

        三种模式：
        - daily: 当日汇总，统计=当天所有条目，新增=本次新增条目
        - current: 当前榜单，统计=当前榜单条目，新增=本次新增条目
        - incremental: 增量模式，统计=新增条目，新增=无

        Args:
            rss_data: 当前抓取的 RSSData 对象

        Returns:
            (rss_stats, rss_new_stats, raw_rss_items) 元组：
            - rss_stats: RSS 关键词统计列表（与热榜 stats 格式一致）
            - rss_new_stats: RSS 新增关键词统计列表（与热榜 stats 格式一致）
            - raw_rss_items: 原始 RSS 条目列表（用于独立展示区）
        """
        from trendradar.core.analyzer import count_rss_frequency

        # 从 display.regions.rss 统一控制 RSS 分析和展示
        rss_display_enabled = self.ctx.config.get("DISPLAY", {}).get("REGIONS", {}).get("RSS", True)

        # 加载关键词配置
        try:
            word_groups, filter_words, global_filters = self.ctx.load_frequency_words()
        except FileNotFoundError:
            word_groups, filter_words, global_filters = [], [], []

        timezone = self.ctx.timezone
        max_news_per_keyword = self.ctx.config.get("MAX_NEWS_PER_KEYWORD", 0)
        sort_by_position_first = self.ctx.config.get("SORT_BY_POSITION_FIRST", False)

        rss_stats = None
        rss_new_stats = None
        raw_rss_items = None  # 原始 RSS 条目列表（用于独立展示区）

        # 1. 首先获取原始条目（用于独立展示区，不受 display.regions.rss 影响）
        # 根据模式获取原始条目
        if self.report_mode == "incremental":
            new_items_dict = self.storage_manager.detect_new_rss_items(rss_data)
            if new_items_dict:
                raw_rss_items = self._convert_rss_items_to_list(new_items_dict, rss_data.id_to_name)
        elif self.report_mode == "current":
            latest_data = self.storage_manager.get_latest_rss_data(rss_data.date)
            if latest_data:
                raw_rss_items = self._convert_rss_items_to_list(latest_data.items, latest_data.id_to_name)
        else:  # daily
            all_data = self.storage_manager.get_rss_data(rss_data.date)
            if all_data:
                raw_rss_items = self._convert_rss_items_to_list(all_data.items, all_data.id_to_name)

        # 如果 RSS 展示未启用，跳过关键词分析，只返回原始条目用于独立展示区
        if not rss_display_enabled:
            return None, None, raw_rss_items

        # 2. 获取新增条目（用于统计）
        new_items_dict = self.storage_manager.detect_new_rss_items(rss_data)
        new_items_list = None
        if new_items_dict:
            new_items_list = self._convert_rss_items_to_list(new_items_dict, rss_data.id_to_name)
            if new_items_list:
                print(f"[RSS] 检测到 {len(new_items_list)} 条新增")

        # 3. 根据模式获取统计条目
        if self.report_mode == "incremental":
            # 增量模式：统计条目就是新增条目
            if not new_items_list:
                print("[RSS] 增量模式：没有新增 RSS 条目")
                return None, None, raw_rss_items

            rss_stats, total = count_rss_frequency(
                rss_items=new_items_list,
                word_groups=word_groups,
                filter_words=filter_words,
                global_filters=global_filters,
                new_items=new_items_list,  # 增量模式所有都是新增
                max_news_per_keyword=max_news_per_keyword,
                sort_by_position_first=sort_by_position_first,
                timezone=timezone,
                rank_threshold=self.rank_threshold,
                quiet=False,
            )
            if not rss_stats:
                print("[RSS] 增量模式：关键词匹配后没有内容")
                # 即使关键词匹配为空，也返回原始条目用于独立展示区
                return None, None, raw_rss_items

        elif self.report_mode == "current":
            # 当前榜单模式：统计=当前榜单所有条目
            # raw_rss_items 已在前面获取
            if not raw_rss_items:
                print("[RSS] 当前榜单模式：没有 RSS 数据")
                return None, None, None

            rss_stats, total = count_rss_frequency(
                rss_items=raw_rss_items,
                word_groups=word_groups,
                filter_words=filter_words,
                global_filters=global_filters,
                new_items=new_items_list,  # 标记新增
                max_news_per_keyword=max_news_per_keyword,
                sort_by_position_first=sort_by_position_first,
                timezone=timezone,
                rank_threshold=self.rank_threshold,
                quiet=False,
            )
            if not rss_stats:
                print("[RSS] 当前榜单模式：关键词匹配后没有内容")
                # 即使关键词匹配为空，也返回原始条目用于独立展示区
                return None, None, raw_rss_items

            # 生成新增统计
            if new_items_list:
                rss_new_stats, _ = count_rss_frequency(
                    rss_items=new_items_list,
                    word_groups=word_groups,
                    filter_words=filter_words,
                    global_filters=global_filters,
                    new_items=new_items_list,
                    max_news_per_keyword=max_news_per_keyword,
                    sort_by_position_first=sort_by_position_first,
                    timezone=timezone,
                    rank_threshold=self.rank_threshold,
                    quiet=True,
                )

        else:
            # daily 模式：统计=当天所有条目
            # raw_rss_items 已在前面获取
            if not raw_rss_items:
                print("[RSS] 当日汇总模式：没有 RSS 数据")
                return None, None, None

            rss_stats, total = count_rss_frequency(
                rss_items=raw_rss_items,
                word_groups=word_groups,
                filter_words=filter_words,
                global_filters=global_filters,
                new_items=new_items_list,  # 标记新增
                max_news_per_keyword=max_news_per_keyword,
                sort_by_position_first=sort_by_position_first,
                timezone=timezone,
                rank_threshold=self.rank_threshold,
                quiet=False,
            )
            if not rss_stats:
                print("[RSS] 当日汇总模式：关键词匹配后没有内容")
                # 即使关键词匹配为空，也返回原始条目用于独立展示区
                return None, None, raw_rss_items

            # 生成新增统计
            if new_items_list:
                rss_new_stats, _ = count_rss_frequency(
                    rss_items=new_items_list,
                    word_groups=word_groups,
                    filter_words=filter_words,
                    global_filters=global_filters,
                    new_items=new_items_list,
                    max_news_per_keyword=max_news_per_keyword,
                    sort_by_position_first=sort_by_position_first,
                    timezone=timezone,
                    rank_threshold=self.rank_threshold,
                    quiet=True,
                )

        return rss_stats, rss_new_stats, raw_rss_items

    def _convert_rss_items_to_list(self, items_dict: Dict, id_to_name: Dict) -> List[Dict]:
        """将 RSS 条目字典转换为列表格式，并应用新鲜度过滤（用于推送）"""
        rss_items = []
        filtered_count = 0

        # 获取新鲜度过滤配置
        rss_config = self.ctx.rss_config
        freshness_config = rss_config.get("FRESHNESS_FILTER", {})
        freshness_enabled = freshness_config.get("ENABLED", True)
        default_max_age_days = freshness_config.get("MAX_AGE_DAYS", 3)
        timezone = self.ctx.config.get("TIMEZONE", "Asia/Shanghai")

        # 构建 feed_id -> max_age_days 的映射
        feed_max_age_map = {}
        for feed_cfg in self.ctx.rss_feeds:
            feed_id = feed_cfg.get("id", "")
            max_age = feed_cfg.get("max_age_days")
            if max_age is not None:
                try:
                    feed_max_age_map[feed_id] = int(max_age)
                except (ValueError, TypeError):
                    pass

        for feed_id, items in items_dict.items():
            # 确定此 feed 的 max_age_days
            max_days = feed_max_age_map.get(feed_id)
            if max_days is None:
                max_days = default_max_age_days

            for item in items:
                # 应用新鲜度过滤（仅在启用时）
                if freshness_enabled and max_days > 0:
                    if item.published_at and not is_within_days(item.published_at, max_days, timezone):
                        filtered_count += 1
                        continue  # 跳过超过指定天数的文章

                rss_items.append({
                    "title": item.title,
                    "feed_id": feed_id,
                    "feed_name": id_to_name.get(feed_id, feed_id),
                    "url": item.url,
                    "published_at": item.published_at,
                    "summary": item.summary,
                    "author": item.author,
                })

        # 输出过滤统计
        if filtered_count > 0:
            print(f"[RSS] 新鲜度过滤：跳过 {filtered_count} 篇超过指定天数的旧文章（仍保留在数据库中）")

        return rss_items

    def _filter_rss_by_keywords(self, rss_items: List[Dict]) -> List[Dict]:
        """使用 frequency_words.txt 过滤 RSS 条目"""
        try:
            word_groups, filter_words, global_filters = self.ctx.load_frequency_words()
            if word_groups or filter_words or global_filters:
                from trendradar.core.frequency import matches_word_groups
                filtered_items = []
                for item in rss_items:
                    title = item.get("title", "")
                    if matches_word_groups(title, word_groups, filter_words, global_filters):
                        filtered_items.append(item)

                original_count = len(rss_items)
                rss_items = filtered_items
                print(f"[RSS] 关键词过滤后剩余 {len(rss_items)}/{original_count} 条")

                if not rss_items:
                    print("[RSS] 关键词过滤后没有匹配内容")
                    return []
        except FileNotFoundError:
            # frequency_words.txt 不存在时跳过过滤
            pass
        return rss_items

    def _generate_rss_html_report(self, rss_items: list, feeds_info: dict) -> str:
        """生成 RSS HTML 报告"""
        try:
            from trendradar.report.rss_html import render_rss_html_content
            from pathlib import Path

            html_content = render_rss_html_content(
                rss_items=rss_items,
                total_count=len(rss_items),
                feeds_info=feeds_info,
                get_time_func=self.ctx.get_time,
            )

            # 保存 HTML 文件（扁平化结构：output/html/日期/）
            date_folder = self.ctx.format_date()
            time_filename = self.ctx.format_time()
            output_dir = Path("output") / "html" / date_folder
            output_dir.mkdir(parents=True, exist_ok=True)

            file_path = output_dir / f"rss_{time_filename}.html"
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(html_content)

            print(f"[RSS] HTML 报告已生成: {file_path}")
            return str(file_path)

        except Exception as e:
            print(f"[RSS] 生成 HTML 报告失败: {e}")
            return None

    def _execute_mode_strategy(
        self, mode_strategy: Dict, results: Dict, id_to_name: Dict, failed_ids: List,
        rss_items: Optional[List[Dict]] = None,
        rss_new_items: Optional[List[Dict]] = None,
        raw_rss_items: Optional[List[Dict]] = None,
    ) -> Optional[str]:
        """执行模式特定逻辑，支持热榜+RSS合并推送

        简化后的逻辑：
        - 每次运行都生成 HTML 报告（时间戳快照 + latest/{mode}.html + index.html）
        - 根据模式发送通知
        """
        # 获取当前监控平台ID列表
        current_platform_ids = self.ctx.platform_ids

        new_titles = self.ctx.detect_new_titles(current_platform_ids)
        time_info = self.ctx.format_time()
        if self.ctx.config["STORAGE"]["FORMATS"]["TXT"]:
            self.ctx.save_titles(results, id_to_name, failed_ids)
        word_groups, filter_words, global_filters = self.ctx.load_frequency_words()

        html_file = None
        stats = []
        ai_result = None
        title_info = None

        # current 模式需要使用完整的历史数据
        if self.report_mode == "current":
            analysis_data = self._load_analysis_data()
            if analysis_data:
                (
                    all_results,
                    historical_id_to_name,
                    historical_title_info,
                    historical_new_titles,
                    _,
                    _,
                    _,
                ) = analysis_data

                print(
                    f"current模式：使用过滤后的历史数据，包含平台：{list(all_results.keys())}"
                )

                # 使用历史数据准备独立展示区数据（包含完整的 title_info）
                standalone_data = self._prepare_standalone_data(
                    all_results, historical_id_to_name, historical_title_info, raw_rss_items
                )

                stats, html_file, ai_result = self._run_analysis_pipeline(
                    all_results,
                    self.report_mode,
                    historical_title_info,
                    historical_new_titles,
                    word_groups,
                    filter_words,
                    historical_id_to_name,
                    failed_ids=failed_ids,
                    global_filters=global_filters,
                    rss_items=rss_items,
                    rss_new_items=rss_new_items,
                    standalone_data=standalone_data,
                )

                combined_id_to_name = {**historical_id_to_name, **id_to_name}
                new_titles = historical_new_titles
                id_to_name = combined_id_to_name
                title_info = historical_title_info
                results = all_results
            else:
                print("❌ 严重错误：无法读取刚保存的数据文件")
                raise RuntimeError("数据一致性检查失败：保存后立即读取失败")
        elif self.report_mode == "daily":
            # daily 模式：使用全天累计数据
            analysis_data = self._load_analysis_data()
            if analysis_data:
                (
                    all_results,
                    historical_id_to_name,
                    historical_title_info,
                    historical_new_titles,
                    _,
                    _,
                    _,
                ) = analysis_data

                # 使用历史数据准备独立展示区数据（包含完整的 title_info）
                standalone_data = self._prepare_standalone_data(
                    all_results, historical_id_to_name, historical_title_info, raw_rss_items
                )

                stats, html_file, ai_result = self._run_analysis_pipeline(
                    all_results,
                    self.report_mode,
                    historical_title_info,
                    historical_new_titles,
                    word_groups,
                    filter_words,
                    historical_id_to_name,
                    failed_ids=failed_ids,
                    global_filters=global_filters,
                    rss_items=rss_items,
                    rss_new_items=rss_new_items,
                    standalone_data=standalone_data,
                )

                combined_id_to_name = {**historical_id_to_name, **id_to_name}
                new_titles = historical_new_titles
                id_to_name = combined_id_to_name
                title_info = historical_title_info
                results = all_results
            else:
                # 没有历史数据时使用当前数据
                title_info = self._prepare_current_title_info(results, time_info)
                standalone_data = self._prepare_standalone_data(
                    results, id_to_name, title_info, raw_rss_items
                )
                stats, html_file, ai_result = self._run_analysis_pipeline(
                    results,
                    self.report_mode,
                    title_info,
                    new_titles,
                    word_groups,
                    filter_words,
                    id_to_name,
                    failed_ids=failed_ids,
                    global_filters=global_filters,
                    rss_items=rss_items,
                    rss_new_items=rss_new_items,
                    standalone_data=standalone_data,
                )
        else:
            # incremental 模式：只使用当前抓取的数据
            title_info = self._prepare_current_title_info(results, time_info)
            standalone_data = self._prepare_standalone_data(
                results, id_to_name, title_info, raw_rss_items
            )
            stats, html_file, ai_result = self._run_analysis_pipeline(
                results,
                self.report_mode,
                title_info,
                new_titles,
                word_groups,
                filter_words,
                id_to_name,
                failed_ids=failed_ids,
                global_filters=global_filters,
                rss_items=rss_items,
                rss_new_items=rss_new_items,
                standalone_data=standalone_data,
            )

        if html_file:
            print(f"HTML报告已生成: {html_file}")
            print(f"最新报告已更新: output/html/latest/{self.report_mode}.html")

        # 发送通知
        if mode_strategy["should_send_notification"]:
            standalone_data = self._prepare_standalone_data(
                results, id_to_name, title_info, raw_rss_items
            )
            self._send_notification_if_needed(
                stats,
                mode_strategy["report_type"],
                self.report_mode,
                failed_ids=failed_ids,
                new_titles=new_titles,
                id_to_name=id_to_name,
                html_file_path=html_file,
                rss_items=rss_items,
                rss_new_items=rss_new_items,
                standalone_data=standalone_data,
                ai_result=ai_result,
                current_results=results,
            )

        # 打开浏览器（仅在非容器环境）
        if self._should_open_browser() and html_file:
            file_url = "file://" + str(Path(html_file).resolve())
            print(f"正在打开HTML报告: {file_url}")
            webbrowser.open(file_url)
        elif self.is_docker_container and html_file:
            print(f"HTML报告已生成（Docker环境）: {html_file}")

        return html_file

    def _run_podcast_processing(
        self,
        test_mode: bool = False,
        test_feed_id: Optional[str] = None,
        test_episode_guid: Optional[str] = None,
    ) -> None:
        """执行播客处理流程"""
        podcast_config = self.ctx.config.get("PODCAST", {})
        if not podcast_config.get("ENABLED", False):
            return

        try:
            from trendradar.podcast import PodcastProcessor

            print("\n" + "=" * 60)
            print("播客处理")
            print("=" * 60)

            processor = PodcastProcessor.from_config(
                config=self.ctx.config,
                test_mode=test_mode,
                test_feed_id=test_feed_id,
                test_episode_guid=test_episode_guid,
            )
            results = processor.run()

            if results:
                success_count = sum(1 for r in results if r.status == "completed")
                print(f"[Podcast] 本次处理: {success_count}/{len(results)} 个节目成功")

        except ImportError as e:
            print(f"[Podcast] 模块导入失败: {e}")
        except Exception as e:
            print(f"[Podcast] 处理出错: {e}")
            if self.ctx.config.get("DEBUG", False):
                import traceback
                traceback.print_exc()

    def _run_investment_processing(self, market_type: str = "cn", force: bool = False) -> None:
        """
        执行投资板块处理流程

        Args:
            market_type: 市场类型（cn=A股/港股，us=美股）
            force: 是否强制运行（忽略时间检查）
        """
        investment_config = self.ctx.config.get("INVESTMENT", {})
        if not investment_config.get("ENABLED", False):
            return

        try:
            from trendradar.investment import InvestmentProcessor

            # 创建处理器
            processor = InvestmentProcessor.from_config(self.ctx.config, self.storage_manager)

            # 检查是否应该运行
            if not force:
                schedule_config = investment_config.get("SCHEDULE", {}).get(market_type.upper(), {})
                if not schedule_config.get("ENABLED", False):
                    return

                # 检查时间（如果配置了定时推送）
                schedule_time = schedule_config.get("TIME", "")
                if schedule_time:
                    now = self.ctx.get_time()
                    current_time = now.strftime("%H:%M")
                    # 允许 5 分钟的时间窗口
                    schedule_hour, schedule_minute = map(int, schedule_time.split(":"))
                    current_hour, current_minute = map(int, current_time.split(":"))
                    time_diff = abs((current_hour * 60 + current_minute) - (schedule_hour * 60 + schedule_minute))
                    if time_diff > 5:
                        # 不在推送时间窗口内
                        return

            print("\n" + "=" * 60)
            market_name = "A股/港股" if market_type == "cn" else "美股"
            print(f"投资简报处理 ({market_name})")
            print("=" * 60)

            result = processor.run(market_type)

            if result.success:
                print(f"[Investment] 处理完成，耗时 {result.duration_seconds:.1f} 秒")
            else:
                print(f"[Investment] 处理失败: {result.error}")

        except ImportError as e:
            print(f"[Investment] 模块导入失败: {e}")
            print("[Investment] 请安装 akshare: pip install akshare")
        except Exception as e:
            print(f"[Investment] 处理出错: {e}")
            if self.ctx.config.get("DEBUG", False):
                import traceback
                traceback.print_exc()

    def _run_community_processing(self, force: bool = False) -> None:
        """
        执行社区监控处理流程

        Args:
            force: 是否强制运行（忽略时间检查）
        """
        community_config = self.ctx.config.get("COMMUNITY", {})
        if not community_config.get("ENABLED", False):
            return

        try:
            from trendradar.community import CommunityProcessor

            print("\n" + "=" * 60)
            print("社区监控处理")
            print("=" * 60)

            # 创建处理器
            processor = CommunityProcessor.from_config(self.ctx.config, test_mode=force)

            # 检查是否应该运行（如果不是强制模式）
            if not force:
                schedule_config = community_config.get("SCHEDULE", {})
                if not schedule_config.get("ENABLED", False):
                    return

                # 检查时间（如果配置了定时推送）
                schedule_times = schedule_config.get("TIMES", [])
                if schedule_times:
                    now = self.ctx.get_time()
                    current_time = now.strftime("%H:%M")

                    # 允许 5 分钟的时间窗口
                    in_window = False
                    for schedule_time in schedule_times:
                        schedule_hour, schedule_minute = map(int, schedule_time.split(":"))
                        current_hour, current_minute = map(int, current_time.split(":"))
                        time_diff = abs((current_hour * 60 + current_minute) - (schedule_hour * 60 + schedule_minute))
                        if time_diff <= 5:
                            in_window = True
                            break

                    if not in_window:
                        return

            # 运行处理流程
            result = processor.run()

            if result:
                print(f"[Community] 处理完成")

        except ImportError as e:
            print(f"[Community] 模块导入失败: {e}")
        except Exception as e:
            print(f"[Community] 处理出错: {e}")
            if self.ctx.config.get("DEBUG", False):
                import traceback
                traceback.print_exc()

    def run(
        self,
        podcast_only: bool = False,
        investment_only: bool = False,
        community_only: bool = False,
        investment_market: str = "cn",
        # 新增测试参数
        test_mode: bool = False,
        test_feed_id: Optional[str] = None,
        test_episode_guid: Optional[str] = None,
    ) -> None:
        """
        执行分析流程

        Args:
            podcast_only: 是否只运行播客处理（跳过热榜和 RSS）
            investment_only: 是否只运行投资处理（跳过热榜、RSS 和播客）
            community_only: 是否只运行社区监控处理（跳过热榜、RSS 和播客）
            investment_market: 投资市场类型（cn=A股/港股，us=美股）
            test_mode: 测试模式开关
            test_feed_id: 测试模式：指定播客源ID
            test_episode_guid: 测试模式：指定节目GUID
        """
        try:
            should_crawl = self._initialize_and_check_config()

            # 如果只运行投资处理
            if investment_only:
                self._run_investment_processing(investment_market, force=True)
                return

            # 如果只运行播客处理
            if podcast_only:
                self._run_podcast_processing(
                    test_mode=test_mode,
                    test_feed_id=test_feed_id,
                    test_episode_guid=test_episode_guid,
                )
                return

            # 如果只运行社区处理
            if community_only:
                self._run_community_processing(force=test_mode)
                return

            # 如果热榜爬虫被禁用，只运行播客和投资处理
            if not should_crawl:
                print("热榜爬虫已禁用，只运行播客和投资处理")
                self._run_podcast_processing(
                    test_mode=test_mode,
                    test_feed_id=test_feed_id,
                    test_episode_guid=test_episode_guid,
                )
                self._run_investment_processing("cn")
                self._run_investment_processing("us")
                return

            mode_strategy = self._get_mode_strategy()

            # 抓取热榜数据
            results, id_to_name, failed_ids = self._crawl_data()

            # 抓取 RSS 数据（如果启用），返回统计条目、新增条目和原始条目
            rss_items, rss_new_items, raw_rss_items = self._crawl_rss_data()

            # 执行模式策略，传递 RSS 数据用于合并推送
            self._execute_mode_strategy(
                mode_strategy, results, id_to_name, failed_ids,
                rss_items=rss_items, rss_new_items=rss_new_items,
                raw_rss_items=raw_rss_items
            )

            # 播客处理（如果启用）
            self._run_podcast_processing(
                test_mode=test_mode,
                test_feed_id=test_feed_id,
                test_episode_guid=test_episode_guid,
            )

            # 投资处理（根据配置的时间自动触发）
            self._run_investment_processing("cn")  # A股/港股
            self._run_investment_processing("us")  # 美股

            # 社区处理（根据配置的时间自动触发）
            self._run_community_processing(force=test_mode)

        except Exception as e:
            print(f"分析流程执行出错: {e}")
            if self.ctx.config.get("DEBUG", False):
                raise
        finally:
            # 清理资源（包括过期数据清理和数据库连接关闭）
            self.ctx.cleanup()


def main():
    """主程序入口"""
    import argparse

    parser = argparse.ArgumentParser(
        description="TrendRadar - 热点新闻聚合与分析工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python -m trendradar                        # 运行完整流程（热榜 + RSS + 播客 + 投资）
  python -m trendradar --podcast-only         # 仅运行播客处理
  python -m trendradar --investment-only      # 仅运行投资简报（A股/港股）
  python -m trendradar --investment-only --market us  # 仅运行投资简报（美股）
        """
    )
    parser.add_argument(
        "--podcast-only",
        action="store_true",
        help="仅运行播客处理（跳过热榜和 RSS 抓取）"
    )
    parser.add_argument(
        "--investment-only",
        action="store_true",
        help="仅运行投资简报处理（跳过热榜、RSS 和播客）"
    )
    parser.add_argument(
        "--community-only",
        action="store_true",
        help="仅运行社区监控处理（跳过热榜、RSS 和播客）"
    )
    parser.add_argument(
        "--market",
        choices=["cn", "us"],
        default="cn",
        help="投资市场类型: cn=A股/港股, us=美股（默认: cn）"
    )
    parser.add_argument(
        "--test-mode",
        action="store_true",
        help="启用测试模式（跳过重复检查，启用过滤）"
    )
    parser.add_argument(
        "--test-feed",
        type=str,
        help="测试模式：指定播客源ID（如: lex-fridman）"
    )
    parser.add_argument(
        "--test-guid",
        type=str,
        help="测试模式：指定节目GUID（如: 49264e2036d4）"
    )
    args = parser.parse_args()

    debug_mode = False
    try:
        # 先加载配置以获取 version_check_url
        config = load_config()
        version_url = config.get("VERSION_CHECK_URL", "")
        configs_version_url = config.get("CONFIGS_VERSION_CHECK_URL", "")

        # 统一版本检查（程序版本 + 配置文件版本，只请求一次远程）
        need_update = False
        remote_version = None
        if version_url:
            need_update, remote_version = check_all_versions(version_url, configs_version_url)

        # 复用已加载的配置，避免重复加载
        analyzer = NewsAnalyzer(config=config)

        # 设置更新信息（复用已获取的远程版本，不再重复请求）
        if analyzer.is_github_actions and need_update and remote_version:
            analyzer.update_info = {
                "current_version": __version__,
                "remote_version": remote_version,
            }

        # 获取 debug 配置
        debug_mode = analyzer.ctx.config.get("DEBUG", False)

        # 运行分析流程
        analyzer.run(
            podcast_only=args.podcast_only,
            investment_only=args.investment_only,
            community_only=args.community_only if hasattr(args, 'community_only') else False,
            investment_market=args.market,
            # 新增测试参数
            test_mode=args.test_mode if hasattr(args, 'test_mode') else False,
            test_feed_id=args.test_feed if hasattr(args, 'test_feed') else None,
            test_episode_guid=args.test_guid if hasattr(args, 'test_guid') else None,
        )

    except FileNotFoundError as e:
        print(f"❌ 配置文件错误: {e}")
        print("\n请确保以下文件存在:")
        print("  • config/config.yaml")
        print("  • config/frequency_words.txt")
        print("\n参考项目文档进行正确配置")
    except Exception as e:
        print(f"❌ 程序运行错误: {e}")
        if debug_mode:
            raise


if __name__ == "__main__":
    main()
