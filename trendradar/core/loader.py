# coding=utf-8
"""
配置加载模块

负责从 YAML 配置文件和环境变量加载配置。

支持两层配置结构：
1. 系统配置 (config/system.yaml) - 架构层面，所有模块共享
2. 业务配置 (各模块独立配置) - 业务层面，模块特定

向后兼容：如果 system.yaml 不存在，从 config.yaml 加载所有配置
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

import yaml

from .config import parse_multi_account_config, validate_paired_configs


def _load_env_files():
    """加载 .env 文件到环境变量"""
    # 可能的 .env 文件位置（按优先级排序）
    env_files = [
        "agents/.env",
        "docker/.env",
        ".env",
    ]
    
    for env_file in env_files:
        path = Path(env_file)
        if path.exists():
            with open(path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip()
                        # 只设置尚未设置的环境变量
                        if key and key not in os.environ:
                            os.environ[key] = value
            break  # 只加载第一个找到的 .env 文件


# 在模块加载时自动加载 .env 文件
_load_env_files()


# ═══════════════════════════════════════════════════════════════
# 系统配置加载（新增）
# ═══════════════════════════════════════════════════════════════

def load_system_config(system_config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    加载系统架构配置 (config/system.yaml)
    
    系统配置包含所有模块共享的架构层面配置：
    - app: 基础设置（时区、数据目录）
    - ai: AI 服务配置
    - notification: 通知服务配置
    - schedule: 调度配置
    - monitor: 监控配置
    - databases: 模块数据库路径
    - storage: 存储配置
    
    Args:
        system_config_path: 系统配置文件路径，默认 config/system.yaml
    
    Returns:
        系统配置字典
    """
    if system_config_path is None:
        system_config_path = os.environ.get("SYSTEM_CONFIG_PATH", "config/system.yaml")
    
    path = Path(system_config_path)
    if not path.exists():
        # 向后兼容：如果 system.yaml 不存在，返回空字典
        # 调用方会 fallback 到 config.yaml
        return {}
    
    with open(path, "r", encoding="utf-8") as f:
        config_data = yaml.safe_load(f) or {}
    
    # 处理环境变量覆盖
    system_config = _process_system_config(config_data)
    
    print(f"系统配置加载成功: {system_config_path}")
    return system_config


def _get_environment(app_config: Dict) -> str:
    """
    获取当前运行环境
    
    优先级：
    1. 环境变量 TRENDRADAR_ENV
    2. 配置文件 app.environment
    3. 根据工作目录自动检测
    """
    # 优先使用环境变量
    env = os.environ.get("TRENDRADAR_ENV", "").lower()
    if env in ["production", "prod"]:
        return "production"
    if env in ["development", "dev"]:
        return "development"
    
    # 从配置文件读取
    config_env = app_config.get("environment", "").lower()
    if config_env in ["production", "prod"]:
        return "production"
    if config_env in ["development", "dev"]:
        return "development"
    
    # 根据工作目录自动检测
    cwd = os.getcwd()
    if "/install/trendradar" in cwd:
        return "production"
    
    return "development"


def _get_env_config(config: Any, environment: str, default: Any = None) -> Any:
    """
    根据环境获取配置值
    
    支持两种格式：
    1. 简单值：直接返回
    2. 环境映射：{ "development": value1, "production": value2 }
    """
    if isinstance(config, dict):
        if "development" in config or "production" in config:
            return config.get(environment, config.get("development", default))
    return config if config is not None else default


def _process_system_config(config_data: Dict) -> Dict[str, Any]:
    """处理系统配置，支持环境变量覆盖和环境感知"""
    app = config_data.get("app", {})
    ai = config_data.get("ai", {})
    notification = config_data.get("notification", {})
    schedule = config_data.get("schedule", {})
    monitor = config_data.get("monitor", {})
    wewe_rss = config_data.get("wewe_rss", {})
    databases = config_data.get("databases", {})
    storage = config_data.get("storage", {})
    advanced = config_data.get("advanced", {})
    
    # 获取当前环境
    environment = _get_environment(app)
    
    # 根据环境获取监控配置
    web_port = _get_env_config(monitor.get("web_port"), environment, 8088)
    status_db = _get_env_config(monitor.get("status_db"), environment, "output/system/status.db")
    
    return {
        # 基础设置
        "APP": {
            "TIMEZONE": _get_env_str("TIMEZONE") or app.get("timezone", "Asia/Shanghai"),
            "DATA_ROOT": app.get("data_root", "output"),
            "SHOW_VERSION_UPDATE": app.get("show_version_update", True),
            "ENVIRONMENT": environment,
        },
        # AI 服务配置
        "AI": {
            "MODEL": _get_env_str("AI_MODEL") or ai.get("model", ""),
            "API_BASE": _get_env_str("AI_API_BASE") or ai.get("api_base", ""),
            "API_KEY": _get_env_str("AI_API_KEY") or ai.get("api_key", ""),
            "TIMEOUT": ai.get("TIMEOUT") or ai.get("timeout", 900),
            "MAX_TOKENS": ai.get("MAX_TOKENS") or ai.get("max_tokens", 160000),
            "TEMPERATURE": ai.get("temperature", 1.0),
        },
        # 通知服务配置
        "NOTIFICATION": _process_notification_config(notification),
        # 调度配置
        "SCHEDULE": _process_schedule_config(schedule),
        # 监控配置
        "MONITOR": {
            "WEB_PORT": web_port,
            "HEALTH_CHECK": {
                "ENABLED": monitor.get("health_check", {}).get("enabled", True),
                "INTERVAL_MINUTES": monitor.get("health_check", {}).get("interval_minutes", 30),
                "ALERT_ON_FAILURE": monitor.get("health_check", {}).get("alert_on_failure", True),
            },
            "STATUS_DB": status_db,
        },
        # Wewe-RSS 配置（微信读书）
        "WEWE_RSS": {
            "BASE_URL": wewe_rss.get("base_url", "http://localhost:4000"),
            "EXTERNAL_URL": wewe_rss.get("external_url", wewe_rss.get("base_url", "http://localhost:4000")),
            "AUTH_CODE": _get_env_str("WEWE_AUTH_CODE") or wewe_rss.get("auth_code", ""),
        },
        # 数据库路径
        "DATABASES": {
            "PODCAST": databases.get("podcast", "output/podcast/podcast.db"),
            "INVESTMENT": databases.get("investment", "output/investment/investment.db"),
            "COMMUNITY": databases.get("community", "output/community/community.db"),
            "WECHAT": databases.get("wechat", "wechat/data/wechat.db"),
            "SYSTEM": status_db,
        },
        # 存储配置
        "STORAGE": {
            "BACKEND": storage.get("backend", "local"),
            "FORMATS": storage.get("formats", {"sqlite": True, "txt": False, "html": True}),
            "LOCAL": storage.get("local", {"data_dir": "output", "retention_days": 0}),
        },
        # 高级设置
        "ADVANCED": {
            "DEBUG": advanced.get("debug", False),
            "MODULE_TIMEOUT": advanced.get("module_timeout", {
                "podcast": 1800,
                "investment": 300,
                "community": 600,
                "wechat": 600,
            }),
        },
    }


def _process_notification_config(notification: Dict) -> Dict:
    """处理通知配置"""
    channels = notification.get("channels", {})
    email = channels.get("email", {})
    
    return {
        "ENABLED": notification.get("enabled", True),
        "CHANNELS": {
            "EMAIL": {
                "ENABLED": email.get("enabled", True),
                "FROM": _get_env_str("EMAIL_FROM") or email.get("from", ""),
                "PASSWORD": _get_env_str("EMAIL_PASSWORD") or email.get("password", ""),
                "TO": _get_env_str("EMAIL_TO") or email.get("to", ""),
                "SMTP_SERVER": _get_env_str("EMAIL_SMTP_SERVER") or email.get("smtp_server", ""),
                "SMTP_PORT": _get_env_str("EMAIL_SMTP_PORT") or email.get("smtp_port", ""),
            },
            "FEISHU": {
                "WEBHOOK_URL": _get_env_str("FEISHU_WEBHOOK_URL") or channels.get("feishu", {}).get("webhook_url", ""),
            },
            "DINGTALK": {
                "WEBHOOK_URL": _get_env_str("DINGTALK_WEBHOOK_URL") or channels.get("dingtalk", {}).get("webhook_url", ""),
            },
            "WEWORK": {
                "WEBHOOK_URL": _get_env_str("WEWORK_WEBHOOK_URL") or channels.get("wework", {}).get("webhook_url", ""),
            },
            "TELEGRAM": {
                "BOT_TOKEN": _get_env_str("TELEGRAM_BOT_TOKEN") or channels.get("telegram", {}).get("bot_token", ""),
                "CHAT_ID": _get_env_str("TELEGRAM_CHAT_ID") or channels.get("telegram", {}).get("chat_id", ""),
            },
        },
    }


def _process_schedule_config(schedule: Dict) -> Dict:
    """处理调度配置"""
    return {
        "PODCAST": {
            "TYPE": schedule.get("podcast", {}).get("type", "interval"),
            "INTERVAL_HOURS": schedule.get("podcast", {}).get("interval_hours", 2),
            "INTERVAL_DAYS": schedule.get("podcast", {}).get("interval_days", 1),
            "ENABLED": schedule.get("podcast", {}).get("enabled", True),
        },
        "INVESTMENT": {
            "TYPE": schedule.get("investment", {}).get("type", "fixed"),
            "TIMES": schedule.get("investment", {}).get("times", ["11:30", "23:30"]),
            "INTERVAL_DAYS": schedule.get("investment", {}).get("interval_days", 1),
            "ENABLED": schedule.get("investment", {}).get("enabled", True),
        },
        "COMMUNITY": {
            "TYPE": schedule.get("community", {}).get("type", "fixed"),
            "TIMES": schedule.get("community", {}).get("times", ["05:00"]),
            "INTERVAL_DAYS": schedule.get("community", {}).get("interval_days", 1),
            "ENABLED": schedule.get("community", {}).get("enabled", True),
        },
        "WECHAT": {
            "TYPE": schedule.get("wechat", {}).get("type", "fixed"),
            "TIMES": schedule.get("wechat", {}).get("times", ["23:00"]),
            "INTERVAL_DAYS": schedule.get("wechat", {}).get("interval_days", 2),  # 默认每2天
            "ENABLED": schedule.get("wechat", {}).get("enabled", True),
        },
        "DAILY_LOG": {
            "TYPE": schedule.get("daily_log", {}).get("type", "fixed"),
            "TIMES": schedule.get("daily_log", {}).get("times", ["23:30"]),
            "INTERVAL_DAYS": schedule.get("daily_log", {}).get("interval_days", 1),
            "ENABLED": schedule.get("daily_log", {}).get("enabled", True),
        },
    }


def get_schedule_summary() -> Dict[str, Any]:
    """
    获取调度配置摘要（用于 trend info 命令显示）
    
    Returns:
        调度配置摘要
    """
    system_config = load_system_config()
    schedule = system_config.get("SCHEDULE", {})
    
    summary = {
        "modules": [],
        "next_runs": {},
    }
    
    # 播客
    podcast = schedule.get("PODCAST", {})
    summary["modules"].append({
        "name": "podcast",
        "type": podcast.get("TYPE", "interval"),
        "trigger": f"每{podcast.get('INTERVAL_HOURS', 2)}小时",
        "enabled": podcast.get("ENABLED", True),
    })
    
    # 投资
    investment = schedule.get("INVESTMENT", {})
    summary["modules"].append({
        "name": "investment",
        "type": investment.get("TYPE", "fixed"),
        "trigger": ", ".join(investment.get("TIMES", [])),
        "enabled": investment.get("ENABLED", True),
    })
    
    # 社区
    community = schedule.get("COMMUNITY", {})
    summary["modules"].append({
        "name": "community",
        "type": community.get("TYPE", "fixed"),
        "trigger": ", ".join(community.get("TIMES", [])),
        "enabled": community.get("ENABLED", True),
    })
    
    # 公众号
    wechat = schedule.get("WECHAT", {})
    summary["modules"].append({
        "name": "wechat",
        "type": wechat.get("TYPE", "fixed"),
        "trigger": ", ".join(wechat.get("TIMES", [])),
        "enabled": wechat.get("ENABLED", True),
    })
    
    return summary


# ═══════════════════════════════════════════════════════════════
# 原有配置加载函数（保持向后兼容）
# ═══════════════════════════════════════════════════════════════


def _get_env_bool(key: str, default: bool = False) -> Optional[bool]:
    """从环境变量获取布尔值，如果未设置返回 None"""
    value = os.environ.get(key, "").strip().lower()
    if not value:
        return None
    return value in ("true", "1")


def _get_env_int(key: str, default: int = 0) -> int:
    """从环境变量获取整数值"""
    value = os.environ.get(key, "").strip()
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _get_env_int_or_none(key: str) -> Optional[int]:
    """从环境变量获取整数值，未设置时返回 None"""
    value = os.environ.get(key, "").strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _get_env_str(key: str, default: str = "") -> str:
    """从环境变量获取字符串值"""
    return os.environ.get(key, "").strip() or default


def _load_app_config(config_data: Dict) -> Dict:
    """加载应用配置"""
    app_config = config_data.get("app", {})
    advanced = config_data.get("advanced", {})
    return {
        "VERSION_CHECK_URL": advanced.get("version_check_url", ""),
        "CONFIGS_VERSION_CHECK_URL": advanced.get("configs_version_check_url", ""),
        "SHOW_VERSION_UPDATE": app_config.get("show_version_update", True),
        "TIMEZONE": _get_env_str("TIMEZONE") or app_config.get("timezone", "Asia/Shanghai"),
        "DEBUG": _get_env_bool("DEBUG") if _get_env_bool("DEBUG") is not None else advanced.get("debug", False),
    }


def _load_crawler_config(config_data: Dict) -> Dict:
    """加载爬虫配置"""
    advanced = config_data.get("advanced", {})
    crawler_config = advanced.get("crawler", {})
    platforms_config = config_data.get("platforms", {})
    return {
        "REQUEST_INTERVAL": crawler_config.get("request_interval", 100),
        "USE_PROXY": crawler_config.get("use_proxy", False),
        "DEFAULT_PROXY": crawler_config.get("default_proxy", ""),
        "ENABLE_CRAWLER": platforms_config.get("enabled", True),
    }


def _load_report_config(config_data: Dict) -> Dict:
    """加载报告配置"""
    report_config = config_data.get("report", {})

    # 环境变量覆盖
    sort_by_position_env = _get_env_bool("SORT_BY_POSITION_FIRST")
    max_news_env = _get_env_int("MAX_NEWS_PER_KEYWORD")

    return {
        "REPORT_MODE": report_config.get("mode", "daily"),
        "DISPLAY_MODE": report_config.get("display_mode", "keyword"),
        "RANK_THRESHOLD": report_config.get("rank_threshold", 10),
        "SORT_BY_POSITION_FIRST": sort_by_position_env if sort_by_position_env is not None else report_config.get("sort_by_position_first", False),
        "MAX_NEWS_PER_KEYWORD": max_news_env or report_config.get("max_news_per_keyword", 0),
    }


def _load_notification_config(config_data: Dict) -> Dict:
    """加载通知配置"""
    notification = config_data.get("notification", {})
    advanced = config_data.get("advanced", {})
    batch_size = advanced.get("batch_size", {})

    return {
        "ENABLE_NOTIFICATION": notification.get("enabled", True),
        "MESSAGE_BATCH_SIZE": batch_size.get("default", 4000),
        "DINGTALK_BATCH_SIZE": batch_size.get("dingtalk", 20000),
        "FEISHU_BATCH_SIZE": batch_size.get("feishu", 29000),
        "BARK_BATCH_SIZE": batch_size.get("bark", 3600),
        "SLACK_BATCH_SIZE": batch_size.get("slack", 4000),
        "BATCH_SEND_INTERVAL": advanced.get("batch_send_interval", 1.0),
        "FEISHU_MESSAGE_SEPARATOR": advanced.get("feishu_message_separator", "---"),
        "MAX_ACCOUNTS_PER_CHANNEL": _get_env_int("MAX_ACCOUNTS_PER_CHANNEL") or advanced.get("max_accounts_per_channel", 3),
    }


def _load_push_window_config(config_data: Dict) -> Dict:
    """加载推送窗口配置"""
    notification = config_data.get("notification", {})
    push_window = notification.get("push_window", {})

    enabled_env = _get_env_bool("PUSH_WINDOW_ENABLED")
    once_per_day_env = _get_env_bool("PUSH_WINDOW_ONCE_PER_DAY")

    return {
        "ENABLED": enabled_env if enabled_env is not None else push_window.get("enabled", False),
        "TIME_RANGE": {
            "START": _get_env_str("PUSH_WINDOW_START") or push_window.get("start", "08:00"),
            "END": _get_env_str("PUSH_WINDOW_END") or push_window.get("end", "22:00"),
        },
        "ONCE_PER_DAY": once_per_day_env if once_per_day_env is not None else push_window.get("once_per_day", True),
    }


def _load_weight_config(config_data: Dict) -> Dict:
    """加载权重配置"""
    advanced = config_data.get("advanced", {})
    weight = advanced.get("weight", {})
    return {
        "RANK_WEIGHT": weight.get("rank", 0.6),
        "FREQUENCY_WEIGHT": weight.get("frequency", 0.3),
        "HOTNESS_WEIGHT": weight.get("hotness", 0.1),
    }


def _load_rss_config(config_data: Dict) -> Dict:
    """加载 RSS 配置"""
    rss = config_data.get("rss", {})
    advanced = config_data.get("advanced", {})
    advanced_rss = advanced.get("rss", {})
    advanced_crawler = advanced.get("crawler", {})

    # RSS 代理配置：优先使用 RSS 专属代理，否则复用 crawler 的 default_proxy
    rss_proxy_url = advanced_rss.get("proxy_url", "") or advanced_crawler.get("default_proxy", "")

    # 新鲜度过滤配置
    freshness_filter = rss.get("freshness_filter", {})

    # 验证并设置 max_age_days 默认值
    raw_max_age = freshness_filter.get("max_age_days", 3)
    try:
        max_age_days = int(raw_max_age)
        if max_age_days < 0:
            print(f"[警告] RSS freshness_filter.max_age_days 为负数 ({max_age_days})，使用默认值 3")
            max_age_days = 3
    except (ValueError, TypeError):
        print(f"[警告] RSS freshness_filter.max_age_days 格式错误 ({raw_max_age})，使用默认值 3")
        max_age_days = 3

    # RSS 配置直接从 config.yaml 读取，不再支持环境变量
    return {
        "ENABLED": rss.get("enabled", False),
        "REQUEST_INTERVAL": advanced_rss.get("request_interval", 2000),
        "TIMEOUT": advanced_rss.get("timeout", 15),
        "USE_PROXY": advanced_rss.get("use_proxy", False),
        "PROXY_URL": rss_proxy_url,
        "FEEDS": rss.get("feeds", []),
        "FRESHNESS_FILTER": {
            "ENABLED": freshness_filter.get("enabled", True),  # 默认启用
            "MAX_AGE_DAYS": max_age_days,
        },
    }


def _load_display_config(config_data: Dict) -> Dict:
    """加载推送内容显示配置"""
    display = config_data.get("display", {})
    regions = display.get("regions", {})
    standalone = display.get("standalone", {})

    # 默认区域顺序
    default_region_order = ["hotlist", "rss", "new_items", "standalone", "ai_analysis"]
    region_order = display.get("region_order", default_region_order)

    # 验证 region_order 中的值是否合法
    valid_regions = {"hotlist", "rss", "new_items", "standalone", "ai_analysis"}
    region_order = [r for r in region_order if r in valid_regions]

    # 如果过滤后为空，使用默认顺序
    if not region_order:
        region_order = default_region_order

    return {
        # 区域显示顺序
        "REGION_ORDER": region_order,
        # 区域开关
        "REGIONS": {
            "HOTLIST": regions.get("hotlist", True),
            "NEW_ITEMS": regions.get("new_items", True),
            "RSS": regions.get("rss", True),
            "STANDALONE": regions.get("standalone", False),
            "AI_ANALYSIS": regions.get("ai_analysis", True),
        },
        # 独立展示区配置
        "STANDALONE": {
            "PLATFORMS": standalone.get("platforms", []),
            "RSS_FEEDS": standalone.get("rss_feeds", []),
            "MAX_ITEMS": standalone.get("max_items", 20),
        },
    }


def _load_ai_config(config_data: Dict) -> Dict:
    """加载 AI 模型配置（LiteLLM 格式）"""
    ai_config = config_data.get("ai", {})

    timeout_env = _get_env_int_or_none("AI_TIMEOUT")

    return {
        # LiteLLM 核心配置
        "MODEL": _get_env_str("AI_MODEL") or ai_config.get("model", "deepseek/deepseek-chat"),
        "API_KEY": _get_env_str("AI_API_KEY") or ai_config.get("api_key", ""),
        "API_BASE": _get_env_str("AI_API_BASE") or ai_config.get("api_base", ""),

        # 生成参数（优先读取大写，兼容小写）
        "TIMEOUT": timeout_env if timeout_env is not None else ai_config.get("TIMEOUT") or ai_config.get("timeout", 900),
        "TEMPERATURE": ai_config.get("temperature", 1.0),
        "MAX_TOKENS": ai_config.get("MAX_TOKENS") or ai_config.get("max_tokens", 160000),

        # LiteLLM 高级选项
        "NUM_RETRIES": ai_config.get("num_retries", 2),
        "FALLBACK_MODELS": ai_config.get("fallback_models", []),
        "EXTRA_PARAMS": ai_config.get("extra_params", {}),
    }


def _load_ai_analysis_config(config_data: Dict) -> Dict:
    """加载 AI 分析配置（功能配置，模型配置见 _load_ai_config）"""
    ai_config = config_data.get("ai_analysis", {})
    analysis_window = ai_config.get("analysis_window", {})

    enabled_env = _get_env_bool("AI_ANALYSIS_ENABLED")
    window_enabled_env = _get_env_bool("AI_ANALYSIS_WINDOW_ENABLED")
    window_once_per_day_env = _get_env_bool("AI_ANALYSIS_WINDOW_ONCE_PER_DAY")

    return {
        "ENABLED": enabled_env if enabled_env is not None else ai_config.get("enabled", False),
        "LANGUAGE": ai_config.get("language", "Chinese"),
        "PROMPT_FILE": ai_config.get("prompt_file", "ai_analysis_prompt.txt"),
        "MODE": ai_config.get("mode", "follow_report"),
        "MAX_NEWS_FOR_ANALYSIS": ai_config.get("max_news_for_analysis", 50),
        "INCLUDE_RSS": ai_config.get("include_rss", True),
        "INCLUDE_RANK_TIMELINE": ai_config.get("include_rank_timeline", False),
        "ANALYSIS_WINDOW": {
            "ENABLED": window_enabled_env if window_enabled_env is not None else analysis_window.get("enabled", False),
            "TIME_RANGE": {
                "START": _get_env_str("AI_ANALYSIS_WINDOW_START") or analysis_window.get("start", "09:00"),
                "END": _get_env_str("AI_ANALYSIS_WINDOW_END") or analysis_window.get("end", "22:00"),
            },
            "ONCE_PER_DAY": window_once_per_day_env if window_once_per_day_env is not None else analysis_window.get("once_per_day", False),
        },
    }


def _load_ai_translation_config(config_data: Dict) -> Dict:
    """加载 AI 翻译配置（功能配置，模型配置见 _load_ai_config）"""
    trans_config = config_data.get("ai_translation", {})

    enabled_env = _get_env_bool("AI_TRANSLATION_ENABLED")

    return {
        "ENABLED": enabled_env if enabled_env is not None else trans_config.get("enabled", False),
        "LANGUAGE": _get_env_str("AI_TRANSLATION_LANGUAGE") or trans_config.get("language", "English"),
        "PROMPT_FILE": trans_config.get("prompt_file", "ai_translation_prompt.txt"),
    }


def _load_podcast_config(config_data: Dict) -> Dict:
    """加载播客配置"""
    podcast = config_data.get("podcast", {})
    asr = podcast.get("asr", {})
    assemblyai = asr.get("assemblyai", {})
    analysis = podcast.get("analysis", {})
    notification = podcast.get("notification", {})
    download = podcast.get("download", {})
    proxy = download.get("proxy", {})
    segment = podcast.get("segment", {})

    enabled_env = _get_env_bool("PODCAST_ENABLED")

    return {
        "ENABLED": enabled_env if enabled_env is not None else podcast.get("enabled", False),
        "POLL_INTERVAL_MINUTES": podcast.get("poll_interval_minutes", 30),
        # 简化后的处理参数
        "MAX_EPISODES_PER_RUN": podcast.get("max_episodes_per_run", 3),
        "NEW_EPISODE_THRESHOLD_DAYS": podcast.get("new_episode_threshold_days", 2),
        # ASR 配置
        "ASR": {
            "BACKEND": asr.get("backend", "assemblyai"),
            "API_BASE": _get_env_str("SILICONFLOW_API_BASE") or asr.get("api_base", "https://api.siliconflow.cn/v1/audio/transcriptions"),
            "API_KEY": _get_env_str("SILICONFLOW_API_KEY") or asr.get("api_key", ""),
            "MODEL": asr.get("model", "FunAudioLLM/SenseVoiceSmall"),
            "LANGUAGE": asr.get("language", "zh"),
            "ASSEMBLYAI": {
                "API_KEY": _get_env_str("ASSEMBLYAI_API_KEY") or assemblyai.get("api_key", ""),
                "SPEAKER_LABELS": assemblyai.get("speaker_labels", True),
            },
        },
        # 分析配置（支持播客专用 AI 模型）
        "ANALYSIS": {
            "ENABLED": analysis.get("enabled", True),
            "PROMPT_FILE": analysis.get("prompt_file", "podcast_prompts.txt"),
            "LANGUAGE": analysis.get("language", "Chinese"),
            "MODEL": _get_env_str("PODCAST_AI_MODEL") or analysis.get("model", ""),
            "API_BASE": _get_env_str("PODCAST_AI_API_BASE") or analysis.get("api_base", ""),
            "API_KEY": _get_env_str("PODCAST_AI_API_KEY") or analysis.get("api_key", ""),
        },
        # 通知配置
        "NOTIFICATION": {
            "ENABLED": notification.get("enabled", True),
            "CHANNELS": notification.get("channels", {"email": True}),
        },
        # 下载配置（补全 timeout 和 proxy，之前遗漏导致 segmenter/代理不生效）
        "DOWNLOAD": {
            "TEMP_DIR": download.get("temp_dir", "output/podcast/audio"),
            "MAX_FILE_SIZE_MB": download.get("max_file_size_mb", 500),
            "CLEANUP_AFTER_TRANSCRIBE": download.get("cleanup_after_transcribe", True),
            "DOWNLOAD_TIMEOUT": download.get("download_timeout", 1800),
            "PROXY": {
                "ENABLED": _get_env_bool("PODCAST_PROXY_ENABLED") if _get_env_bool("PODCAST_PROXY_ENABLED") is not None else proxy.get("enabled", False),
                "URL": _get_env_str("PODCAST_PROXY_URL") or proxy.get("url", ""),
            },
        },
        # 音频分段配置（之前遗漏，导致 segmenter 永远不初始化）
        "SEGMENT": {
            "ENABLED": segment.get("enabled", False),
            "DURATION_THRESHOLD": segment.get("duration_threshold", 7200),
            "OVERLAP_SECONDS": segment.get("overlap_seconds", 120),
            "TEMP_DIR": segment.get("temp_dir", "output/podcast/audio/segments"),
        },
        # 播客源
        "FEEDS": podcast.get("feeds", []),
    }


def _load_community_config(config_data: Dict) -> Dict:
    """加载社区监控模块配置"""
    community = config_data.get("community", {})
    schedule = community.get("schedule", {})
    proxy = community.get("proxy", {})
    sources = community.get("sources", {})
    analysis = community.get("analysis", {})
    notification = community.get("notification", {})

    enabled_env = _get_env_bool("COMMUNITY_ENABLED")

    return {
        "ENABLED": enabled_env if enabled_env is not None else community.get("enabled", False),
        # 代理配置
        "PROXY": {
            "ENABLED": _get_env_bool("COMMUNITY_PROXY_ENABLED") if _get_env_bool("COMMUNITY_PROXY_ENABLED") is not None else proxy.get("enabled", False),
            "URL": _get_env_str("COMMUNITY_PROXY_URL") or proxy.get("url", ""),
        },
        # 调度配置
        "SCHEDULE": {
            "ENABLED": schedule.get("enabled", True),
            "TIMES": schedule.get("times", ["18:00"]),
        },
        # 关注话题
        "TOPICS": community.get("topics", ["AI", "LLM", "robotics", "startup"]),
        # 数据源配置
        "SOURCES": {
            "hackernews": {
                "enabled": sources.get("hackernews", {}).get("enabled", True),
                "max_items": sources.get("hackernews", {}).get("max_items", 30),
                "min_score": sources.get("hackernews", {}).get("min_score", 10),
                "max_age_hours": sources.get("hackernews", {}).get("max_age_hours", 24),
                "search_keywords": sources.get("hackernews", {}).get("search_keywords", []),
            },
            "reddit": {
                "enabled": sources.get("reddit", {}).get("enabled", True),
                "max_items": sources.get("reddit", {}).get("max_items", 50),
                "min_score": sources.get("reddit", {}).get("min_score", 5),
                "search_time": sources.get("reddit", {}).get("search_time", "day"),
                "sort": sources.get("reddit", {}).get("sort", "hot"),
                "subreddits": sources.get("reddit", {}).get("subreddits", []),
                "search_keywords": sources.get("reddit", {}).get("search_keywords", []),
            },
            "twitter": {
                "enabled": sources.get("twitter", {}).get("enabled", False),
                "bridge_url": sources.get("twitter", {}).get("bridge_url", ""),
                "accounts": sources.get("twitter", {}).get("accounts", []),
                "max_items": sources.get("twitter", {}).get("max_items", 30),
                "search_queries": sources.get("twitter", {}).get("search_queries", []),
            },
            "kickstarter": {
                "enabled": sources.get("kickstarter", {}).get("enabled", False),
                "max_items": sources.get("kickstarter", {}).get("max_items", 20),
                "sort": sources.get("kickstarter", {}).get("sort", "magic"),
                "categories": sources.get("kickstarter", {}).get("categories", ["technology", "robots"]),
                "search_keywords": sources.get("kickstarter", {}).get("search_keywords", []),
            },
            "github": {
                "enabled": sources.get("github", {}).get("enabled", True),
                "max_items": sources.get("github", {}).get("max_items", 30),
                "min_stars": sources.get("github", {}).get("min_stars", 10),
                "created_days": sources.get("github", {}).get("created_days", 7),
                "topics": sources.get("github", {}).get("topics", ["ai", "llm", "machine-learning"]),
                "api_token": _get_env_str("GITHUB_TOKEN") or sources.get("github", {}).get("api_token", ""),
            },
            "producthunt": {
                "enabled": sources.get("producthunt", {}).get("enabled", True),
                "max_items": sources.get("producthunt", {}).get("max_items", 20),
            },
        },
        # 分析配置
        "ANALYSIS": {
            "ENABLED": analysis.get("enabled", True),
            "PROMPT_FILE": analysis.get("prompt_file", "community_prompts.txt"),
            "LANGUAGE": analysis.get("language", "Chinese"),
            "TOP_N": analysis.get("top_n", 30),
            "MODEL": _get_env_str("COMMUNITY_AI_MODEL") or analysis.get("model", ""),
            "API_BASE": _get_env_str("COMMUNITY_AI_API_BASE") or analysis.get("api_base", ""),
            "API_KEY": _get_env_str("COMMUNITY_AI_API_KEY") or analysis.get("api_key", ""),
        },
        # 通知配置
        "NOTIFICATION": {
            "ENABLED": notification.get("enabled", True),
            "CHANNELS": notification.get("channels", {"email": True}),
        },
    }


def _load_investment_config(config_data: Dict) -> Dict:
    """加载投资模块配置"""
    investment = config_data.get("investment", {})
    schedule = investment.get("schedule", {})
    sources = investment.get("sources", {})
    analysis = investment.get("analysis", {})
    notification = investment.get("notification", {})

    enabled_env = _get_env_bool("INVESTMENT_ENABLED")

    return {
        "ENABLED": enabled_env if enabled_env is not None else investment.get("enabled", False),
        # 调度配置
        "SCHEDULE": {
            "CN": {
                "ENABLED": schedule.get("cn", {}).get("enabled", True),
                "TIME": schedule.get("cn", {}).get("time", "11:50"),
            },
            "US": {
                "ENABLED": schedule.get("us", {}).get("enabled", False),
                "TIME": schedule.get("us", {}).get("time", "23:00"),
            },
        },
        # 指数配置
        "INDICES": investment.get("indices", []),
        # 概念配置
        "CONCEPTS": investment.get("concepts", []),
        # 个股配置
        "WATCHLIST": investment.get("watchlist", []),
        # 加密货币配置
        "CRYPTO": {
            "ENABLED": investment.get("crypto", {}).get("enabled", False),
            "SYMBOLS": investment.get("crypto", {}).get("symbols", []),
        },
        # 数据源配置
        "SOURCES": {
            # 热榜数据（从热榜数据库读取）
            "HOTLIST": {
                "ENABLED": sources.get("hotlist", {}).get("enabled", True),
                "PLATFORM_IDS": sources.get("hotlist", {}).get("platform_ids", []),
                "MAX_NEWS": sources.get("hotlist", {}).get("max_news", 30),
            },
            # RSS 订阅源（独立爬取）
            "RSS": {
                "ENABLED": sources.get("rss", {}).get("enabled", False),
                "MAX_NEWS": sources.get("rss", {}).get("max_news", 20),
                "MAX_AGE_DAYS": sources.get("rss", {}).get("max_age_days", 1),
                "FEEDS": sources.get("rss", {}).get("feeds", []),
            },
            # AKShare 行情数据
            "AKSHARE": {
                "ENABLED": sources.get("akshare", {}).get("enabled", True),
                "MONEY_FLOW": {
                    "NORTHBOUND": sources.get("akshare", {}).get("money_flow", {}).get("northbound", True),
                    "SECTOR_FLOW": sources.get("akshare", {}).get("money_flow", {}).get("sector_flow", True),
                },
            },
        },
        # 分析配置
        "ANALYSIS": {
            "ENABLED": analysis.get("enabled", True),
            "PROMPT_FILE": analysis.get("prompt_file", "investment_daily.txt"),
            "LANGUAGE": analysis.get("language", "Chinese"),
            "MODEL": _get_env_str("INVESTMENT_AI_MODEL") or analysis.get("model", ""),
            "API_BASE": _get_env_str("INVESTMENT_AI_API_BASE") or analysis.get("api_base", ""),
            "API_KEY": _get_env_str("INVESTMENT_AI_API_KEY") or analysis.get("api_key", ""),
            # 分级处理配置（新增）
            "FETCH_CONTENT": analysis.get("fetch_content", True),
            "MAX_ARTICLES": analysis.get("max_articles", 10),
            "CONTENT_FETCH_DELAY": analysis.get("content_fetch_delay", 1.0),
        },
        # 通知配置
        "NOTIFICATION": {
            "ENABLED": notification.get("enabled", True),
            "CHANNELS": notification.get("channels", {"email": True}),
        },
    }


def _load_storage_config(config_data: Dict) -> Dict:
    """加载存储配置"""
    storage = config_data.get("storage", {})
    formats = storage.get("formats", {})
    local = storage.get("local", {})
    remote = storage.get("remote", {})
    pull = storage.get("pull", {})

    txt_enabled_env = _get_env_bool("STORAGE_TXT_ENABLED")
    html_enabled_env = _get_env_bool("STORAGE_HTML_ENABLED")
    pull_enabled_env = _get_env_bool("PULL_ENABLED")

    return {
        "BACKEND": _get_env_str("STORAGE_BACKEND") or storage.get("backend", "auto"),
        "FORMATS": {
            "SQLITE": formats.get("sqlite", True),
            "TXT": txt_enabled_env if txt_enabled_env is not None else formats.get("txt", True),
            "HTML": html_enabled_env if html_enabled_env is not None else formats.get("html", True),
        },
        "LOCAL": {
            "DATA_DIR": local.get("data_dir", "output"),
            "RETENTION_DAYS": _get_env_int("LOCAL_RETENTION_DAYS") or local.get("retention_days", 0),
        },
        "REMOTE": {
            "ENDPOINT_URL": _get_env_str("S3_ENDPOINT_URL") or remote.get("endpoint_url", ""),
            "BUCKET_NAME": _get_env_str("S3_BUCKET_NAME") or remote.get("bucket_name", ""),
            "ACCESS_KEY_ID": _get_env_str("S3_ACCESS_KEY_ID") or remote.get("access_key_id", ""),
            "SECRET_ACCESS_KEY": _get_env_str("S3_SECRET_ACCESS_KEY") or remote.get("secret_access_key", ""),
            "REGION": _get_env_str("S3_REGION") or remote.get("region", ""),
            "RETENTION_DAYS": _get_env_int("REMOTE_RETENTION_DAYS") or remote.get("retention_days", 0),
        },
        "PULL": {
            "ENABLED": pull_enabled_env if pull_enabled_env is not None else pull.get("enabled", False),
            "DAYS": _get_env_int("PULL_DAYS") or pull.get("days", 7),
        },
    }


def _load_webhook_config(config_data: Dict) -> Dict:
    """加载 Webhook 配置"""
    notification = config_data.get("notification", {})
    channels = notification.get("channels", {})

    # 各渠道配置
    feishu = channels.get("feishu", {})
    dingtalk = channels.get("dingtalk", {})
    wework = channels.get("wework", {})
    telegram = channels.get("telegram", {})
    email = channels.get("email", {})
    ntfy = channels.get("ntfy", {})
    bark = channels.get("bark", {})
    slack = channels.get("slack", {})
    generic = channels.get("generic_webhook", {})

    return {
        # 飞书
        "FEISHU_WEBHOOK_URL": _get_env_str("FEISHU_WEBHOOK_URL") or feishu.get("webhook_url", ""),
        # 钉钉
        "DINGTALK_WEBHOOK_URL": _get_env_str("DINGTALK_WEBHOOK_URL") or dingtalk.get("webhook_url", ""),
        # 企业微信
        "WEWORK_WEBHOOK_URL": _get_env_str("WEWORK_WEBHOOK_URL") or wework.get("webhook_url", ""),
        "WEWORK_MSG_TYPE": _get_env_str("WEWORK_MSG_TYPE") or wework.get("msg_type", "markdown"),
        # Telegram
        "TELEGRAM_BOT_TOKEN": _get_env_str("TELEGRAM_BOT_TOKEN") or telegram.get("bot_token", ""),
        "TELEGRAM_CHAT_ID": _get_env_str("TELEGRAM_CHAT_ID") or telegram.get("chat_id", ""),
        # 邮件
        "EMAIL_FROM": _get_env_str("EMAIL_FROM") or email.get("from", ""),
        "EMAIL_PASSWORD": _get_env_str("EMAIL_PASSWORD") or email.get("password", ""),
        "EMAIL_TO": _get_env_str("EMAIL_TO") or email.get("to", ""),
        "EMAIL_SMTP_SERVER": _get_env_str("EMAIL_SMTP_SERVER") or email.get("smtp_server", ""),
        "EMAIL_SMTP_PORT": _get_env_str("EMAIL_SMTP_PORT") or email.get("smtp_port", ""),
        # ntfy
        "NTFY_SERVER_URL": _get_env_str("NTFY_SERVER_URL") or ntfy.get("server_url") or "https://ntfy.sh",
        "NTFY_TOPIC": _get_env_str("NTFY_TOPIC") or ntfy.get("topic", ""),
        "NTFY_TOKEN": _get_env_str("NTFY_TOKEN") or ntfy.get("token", ""),
        # Bark
        "BARK_URL": _get_env_str("BARK_URL") or bark.get("url", ""),
        # Slack
        "SLACK_WEBHOOK_URL": _get_env_str("SLACK_WEBHOOK_URL") or slack.get("webhook_url", ""),
        # 通用 Webhook
        "GENERIC_WEBHOOK_URL": _get_env_str("GENERIC_WEBHOOK_URL") or generic.get("webhook_url", ""),
        "GENERIC_WEBHOOK_TEMPLATE": _get_env_str("GENERIC_WEBHOOK_TEMPLATE") or generic.get("payload_template", ""),
    }


def _print_notification_sources(config: Dict) -> None:
    """打印通知渠道配置来源信息"""
    notification_sources = []
    max_accounts = config["MAX_ACCOUNTS_PER_CHANNEL"]

    if config["FEISHU_WEBHOOK_URL"]:
        accounts = parse_multi_account_config(config["FEISHU_WEBHOOK_URL"])
        count = min(len(accounts), max_accounts)
        source = "环境变量" if os.environ.get("FEISHU_WEBHOOK_URL") else "配置文件"
        notification_sources.append(f"飞书({source}, {count}个账号)")

    if config["DINGTALK_WEBHOOK_URL"]:
        accounts = parse_multi_account_config(config["DINGTALK_WEBHOOK_URL"])
        count = min(len(accounts), max_accounts)
        source = "环境变量" if os.environ.get("DINGTALK_WEBHOOK_URL") else "配置文件"
        notification_sources.append(f"钉钉({source}, {count}个账号)")

    if config["WEWORK_WEBHOOK_URL"]:
        accounts = parse_multi_account_config(config["WEWORK_WEBHOOK_URL"])
        count = min(len(accounts), max_accounts)
        source = "环境变量" if os.environ.get("WEWORK_WEBHOOK_URL") else "配置文件"
        notification_sources.append(f"企业微信({source}, {count}个账号)")

    if config["TELEGRAM_BOT_TOKEN"] and config["TELEGRAM_CHAT_ID"]:
        tokens = parse_multi_account_config(config["TELEGRAM_BOT_TOKEN"])
        chat_ids = parse_multi_account_config(config["TELEGRAM_CHAT_ID"])
        valid, count = validate_paired_configs(
            {"bot_token": tokens, "chat_id": chat_ids},
            "Telegram",
            required_keys=["bot_token", "chat_id"]
        )
        if valid and count > 0:
            count = min(count, max_accounts)
            token_source = "环境变量" if os.environ.get("TELEGRAM_BOT_TOKEN") else "配置文件"
            notification_sources.append(f"Telegram({token_source}, {count}个账号)")

    if config["EMAIL_FROM"] and config["EMAIL_PASSWORD"] and config["EMAIL_TO"]:
        from_source = "环境变量" if os.environ.get("EMAIL_FROM") else "配置文件"
        notification_sources.append(f"邮件({from_source})")

    if config["NTFY_SERVER_URL"] and config["NTFY_TOPIC"]:
        topics = parse_multi_account_config(config["NTFY_TOPIC"])
        tokens = parse_multi_account_config(config["NTFY_TOKEN"])
        if tokens:
            valid, count = validate_paired_configs(
                {"topic": topics, "token": tokens},
                "ntfy"
            )
            if valid and count > 0:
                count = min(count, max_accounts)
                server_source = "环境变量" if os.environ.get("NTFY_SERVER_URL") else "配置文件"
                notification_sources.append(f"ntfy({server_source}, {count}个账号)")
        else:
            count = min(len(topics), max_accounts)
            server_source = "环境变量" if os.environ.get("NTFY_SERVER_URL") else "配置文件"
            notification_sources.append(f"ntfy({server_source}, {count}个账号)")

    if config["BARK_URL"]:
        accounts = parse_multi_account_config(config["BARK_URL"])
        count = min(len(accounts), max_accounts)
        bark_source = "环境变量" if os.environ.get("BARK_URL") else "配置文件"
        notification_sources.append(f"Bark({bark_source}, {count}个账号)")

    if config["SLACK_WEBHOOK_URL"]:
        accounts = parse_multi_account_config(config["SLACK_WEBHOOK_URL"])
        count = min(len(accounts), max_accounts)
        slack_source = "环境变量" if os.environ.get("SLACK_WEBHOOK_URL") else "配置文件"
        notification_sources.append(f"Slack({slack_source}, {count}个账号)")

    if config.get("GENERIC_WEBHOOK_URL"):
        accounts = parse_multi_account_config(config["GENERIC_WEBHOOK_URL"])
        count = min(len(accounts), max_accounts)
        source = "环境变量" if os.environ.get("GENERIC_WEBHOOK_URL") else "配置文件"
        notification_sources.append(f"通用Webhook({source}, {count}个账号)")

    if notification_sources:
        print(f"通知渠道配置来源: {', '.join(notification_sources)}")
        print(f"每个渠道最大账号数: {max_accounts}")
    else:
        print("未配置任何通知渠道")


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    加载配置文件

    Args:
        config_path: 配置文件路径，默认从环境变量 CONFIG_PATH 获取或使用 config/config.yaml

    Returns:
        包含所有配置的字典

    Raises:
        FileNotFoundError: 配置文件不存在
    """
    if config_path is None:
        config_path = os.environ.get("CONFIG_PATH", "config/config.yaml")

    if not Path(config_path).exists():
        raise FileNotFoundError(f"配置文件 {config_path} 不存在")

    with open(config_path, "r", encoding="utf-8") as f:
        config_data = yaml.safe_load(f)

    print(f"配置文件加载成功: {config_path}")

    # 合并所有配置
    config = {}

    # 应用配置
    config.update(_load_app_config(config_data))

    # 爬虫配置
    config.update(_load_crawler_config(config_data))

    # 报告配置
    config.update(_load_report_config(config_data))

    # 通知配置
    config.update(_load_notification_config(config_data))

    # 推送窗口配置
    config["PUSH_WINDOW"] = _load_push_window_config(config_data)

    # 权重配置
    config["WEIGHT_CONFIG"] = _load_weight_config(config_data)

    # 平台配置
    platforms_config = config_data.get("platforms", {})
    config["PLATFORMS"] = platforms_config.get("sources", [])

    # RSS 配置
    config["RSS"] = _load_rss_config(config_data)

    # AI 模型共享配置
    config["AI"] = _load_ai_config(config_data)

    # AI 分析配置
    config["AI_ANALYSIS"] = _load_ai_analysis_config(config_data)

    # AI 翻译配置
    config["AI_TRANSLATION"] = _load_ai_translation_config(config_data)

    # 播客配置
    config["PODCAST"] = _load_podcast_config(config_data)

    # 投资模块配置
    config["INVESTMENT"] = _load_investment_config(config_data)

    # 社区监控模块配置
    config["COMMUNITY"] = _load_community_config(config_data)

    # 推送内容显示配置
    config["DISPLAY"] = _load_display_config(config_data)

    # 存储配置
    config["STORAGE"] = _load_storage_config(config_data)

    # Webhook 配置
    config.update(_load_webhook_config(config_data))

    # 打印通知渠道配置来源
    _print_notification_sources(config)

    return config
