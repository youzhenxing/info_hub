"""
配置加载器
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from .models import WechatFeed, FeedType


@dataclass
class WeweRssConfig:
    """Wewe-RSS 配置"""
    base_url: str
    external_url: str
    auth_code: str


@dataclass
class AIConfig:
    """AI 配置"""
    model: str
    api_key: str
    api_base: str
    timeout: int
    max_tokens: int
    temperature: float


@dataclass
class EmailConfig:
    """邮件配置"""
    from_addr: str
    password: str
    to_addr: str
    smtp_server: str
    smtp_port: str


@dataclass
class CollectorConfig:
    """采集器配置"""
    max_articles_per_feed: int
    max_age_days: int
    request_interval: int


@dataclass
class StorageConfig:
    """存储配置"""
    data_dir: str
    db_name: str
    output_dir: str
    retention_days: int


class ConfigLoader:
    """配置加载器"""

    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = Path(config_path)
        self._config: Dict[str, Any] = {}
        self._load_config()

    def _load_config(self):
        """加载配置文件（支持 system.yaml 和本地 config.yaml）"""
        # 1. 先加载 system.yaml（如果存在）
        system_config = {}
        system_config_paths = [
            Path("../config/system.yaml"),  # 相对于 wechat 目录
            Path("config/system.yaml"),     # 如果从项目根目录运行
        ]

        for system_path in system_config_paths:
            if system_path.exists():
                try:
                    with open(system_path, 'r', encoding='utf-8') as f:
                        system_config = yaml.safe_load(f) or {}
                    break
                except Exception as e:
                    pass  # 忽略错误，继续尝试其他路径

        # 2. 加载本地 config.yaml
        if not self.config_path.exists():
            raise FileNotFoundError(f"配置文件不存在: {self.config_path}")

        with open(self.config_path, 'r', encoding='utf-8') as f:
            local_config = yaml.safe_load(f) or {}

        # 3. 合并配置（local_config 为基础，system_config 覆盖）
        #    优先级：环境变量 > system.yaml > wechat/config.yaml
        self._config = self._merge_configs(local_config, system_config)

    def _merge_configs(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """
        合并两个配置字典（override 覆盖 base）

        Args:
            base: 基础配置（来自 wechat/config.yaml）
            override: 覆盖配置（来自 config/system.yaml）

        Returns:
            合并后的配置

        优先级：环境变量 > config/system.yaml (override) > wechat/config.yaml (base)
        """
        result = base.copy()

        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                # 递归合并嵌套字典
                result[key] = self._merge_configs(result[key], value)
            else:
                # 直接覆盖
                result[key] = value

        return result
    
    def _get_env_or_config(self, env_key: str, config_path: str, default: str = "") -> str:
        """
        优先从环境变量读取，否则从配置文件读取

        Args:
            env_key: 环境变量键名
            config_path: 配置文件路径（支持点分隔，如 'notification.channels.email.from'）
            default: 默认值

        Returns:
            配置值
        """
        # 1. 优先从环境变量读取
        env_value = os.environ.get(env_key)
        if env_value:
            return env_value

        # 2. 从配置文件读取（支持点分隔路径）
        keys = config_path.split('.')
        value = self._config
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key, {})
            else:
                return default

        return str(value) if value else default
    
    @property
    def timezone(self) -> str:
        """获取时区"""
        return self._config.get('app', {}).get('timezone', 'Asia/Shanghai')
    
    @property
    def debug(self) -> bool:
        """是否调试模式"""
        return self._config.get('app', {}).get('debug', False)
    
    @property
    def environment(self) -> str:
        """
        获取运行环境
        
        Returns:
            'production' 或 'development'
        """
        # 优先从环境变量读取
        env = os.environ.get('WECHAT_ENV', '')
        if env in ['production', 'development']:
            return env
        
        # 从配置文件读取
        return self._config.get('app', {}).get('environment', 'production')
    
    @property
    def is_production(self) -> bool:
        """是否为生产环境"""
        return self.environment == 'production'
    
    @property
    def is_development(self) -> bool:
        """是否为开发环境"""
        return self.environment == 'development'
    
    @property
    def schedule_interval_days(self) -> int:
        """调度间隔（天）"""
        return self._config.get('schedule', {}).get('interval_days', 1)
    
    @property
    def wewe_rss(self) -> WeweRssConfig:
        """Wewe-RSS 配置"""
        cfg = self._config.get('wewe_rss', {})
        return WeweRssConfig(
            base_url=os.environ.get('WEWE_RSS_URL', cfg.get('base_url', 'http://wewe-rss:4000')),
            external_url=cfg.get('external_url', 'http://localhost:4000'),
            auth_code=self._get_env_or_config('WEWE_AUTH_CODE', 'wewe_rss.auth_code', '123456')
        )
    
    @property
    def account_monitor_enabled(self) -> bool:
        """是否启用账号监控"""
        return self._config.get('account_monitor', {}).get('enabled', True)
    
    @property
    def account_monitor_interval(self) -> int:
        """账号监控间隔（小时）"""
        return self._config.get('account_monitor', {}).get('check_interval_hours', 6)
    
    @property
    def account_monitor_alert(self) -> bool:
        """账号失效时是否发送提醒"""
        return self._config.get('account_monitor', {}).get('alert_on_expire', True)
    
    @property
    def daily_report_time(self) -> str:
        """每日报告推送时间"""
        return self._config.get('schedule', {}).get('daily_report_time', '23:00')
    
    @property
    def ai(self) -> AIConfig:
        """AI 配置"""
        cfg = self._config.get('ai', {})
        return AIConfig(
            model=self._get_env_or_config('AI_MODEL', 'ai.model', 'deepseek/deepseek-chat'),
            api_key=self._get_env_or_config('AI_API_KEY', 'ai.api_key'),
            api_base=self._get_env_or_config('AI_API_BASE', 'ai.api_base'),
            timeout=cfg.get('timeout', 120),
            max_tokens=cfg.get('max_tokens', 4000),
            temperature=cfg.get('temperature', 0.7)
        )

    @property
    def email(self) -> EmailConfig:
        """邮件配置"""
        # 支持两种路径：system.yaml 的 notification.channels.email 或 wechat/config.yaml 的 email
        email_cfg = self._config.get('notification', {}).get('channels', {}).get('email', {})
        if not email_cfg:
            email_cfg = self._config.get('email', {})

        return EmailConfig(
            from_addr=self._get_env_or_config('EMAIL_FROM', 'notification.channels.email.from', email_cfg.get('from', '')),
            password=self._get_env_or_config('EMAIL_PASSWORD', 'notification.channels.email.password', email_cfg.get('password', '')),
            to_addr=self._get_env_or_config('EMAIL_TO', 'notification.channels.email.to', email_cfg.get('to', '')),
            smtp_server=self._get_env_or_config('EMAIL_SMTP_SERVER', 'notification.channels.email.smtp_server', email_cfg.get('smtp_server', '')),
            smtp_port=self._get_env_or_config('EMAIL_SMTP_PORT', 'notification.channels.email.smtp_port', str(email_cfg.get('smtp_port', '')))
        )
    
    @property
    def collector(self) -> CollectorConfig:
        """采集器配置"""
        cfg = self._config.get('collector', {})
        return CollectorConfig(
            max_articles_per_feed=cfg.get('max_articles_per_feed', 10),
            max_age_days=cfg.get('max_age_days', 1),
            request_interval=cfg.get('request_interval', 2)
        )
    
    @property
    def storage(self) -> StorageConfig:
        """存储配置"""
        cfg = self._config.get('storage', {})
        return StorageConfig(
            data_dir=cfg.get('data_dir', 'data'),
            db_name=cfg.get('db_name', 'wechat.db'),
            output_dir=cfg.get('output_dir', 'data/output'),
            retention_days=cfg.get('retention_days', 30)
        )
    
    @property
    def batch_mode(self) -> bool:
        """是否启用分批采集模式"""
        return self._config.get('schedule', {}).get('batch_mode', False)
    
    @property
    def batch_a_days(self) -> List[int]:
        """批次 A 的星期几（0=周日, 1=周一, ...）"""
        return self._config.get('schedule', {}).get('batch_a_days', [1, 3, 5, 0])
    
    @property
    def batch_b_days(self) -> List[int]:
        """批次 B 的星期几"""
        return self._config.get('schedule', {}).get('batch_b_days', [2, 4, 6])
    
    def get_current_batch(self) -> str:
        """
        获取当前应采集的批次
        返回: 'a', 'b', 或 'all'（非分批模式）
        """
        if not self.batch_mode:
            return 'all'
        
        from datetime import datetime
        weekday = datetime.now().weekday()  # 0=周一, 6=周日
        # 转换为配置中的格式 (0=周日, 1=周一, ...)
        weekday_config = (weekday + 1) % 7
        
        if weekday_config in self.batch_a_days:
            return 'a'
        elif weekday_config in self.batch_b_days:
            return 'b'
        else:
            return 'all'
    
    def get_feeds(self, batch: Optional[str] = None) -> List[WechatFeed]:
        """
        获取公众号列表
        
        Args:
            batch: 指定批次 ('a', 'b', 'all', None)
                   None 表示根据当前日期自动选择批次
        """
        feeds = []
        feeds_config = self._config.get('feeds', {}) or {}
        
        # 确定要采集的批次
        if batch is None:
            batch = self.get_current_batch()
        
        # 第一类：关键信息（不分批，始终采集）
        for feed_cfg in (feeds_config.get('critical') or []):
            if feed_cfg.get('enabled', True):
                feeds.append(WechatFeed(
                    id=feed_cfg['id'],
                    name=feed_cfg['name'],
                    wewe_feed_id=feed_cfg['wewe_feed_id'],
                    feed_type=FeedType.CRITICAL,
                    enabled=True
                ))
        
        # 分批模式：根据批次采集
        if self.batch_mode and batch != 'all':
            batch_key = f'batch_{batch}'
            for feed_cfg in (feeds_config.get(batch_key) or []):
                if feed_cfg.get('enabled', True):
                    feeds.append(WechatFeed(
                        id=feed_cfg['id'],
                        name=feed_cfg['name'],
                        wewe_feed_id=feed_cfg['wewe_feed_id'],
                        feed_type=FeedType.NORMAL,
                        enabled=True
                    ))
        else:
            # 非分批模式或获取全部：采集所有普通公众号
            # 兼容旧格式 (normal) 和新格式 (batch_a, batch_b)
            for feed_cfg in (feeds_config.get('normal') or []):
                if feed_cfg.get('enabled', True):
                    feeds.append(WechatFeed(
                        id=feed_cfg['id'],
                        name=feed_cfg['name'],
                        wewe_feed_id=feed_cfg['wewe_feed_id'],
                        feed_type=FeedType.NORMAL,
                        enabled=True
                    ))
            
            # 新格式的批次 A
            for feed_cfg in (feeds_config.get('batch_a') or []):
                if feed_cfg.get('enabled', True):
                    feeds.append(WechatFeed(
                        id=feed_cfg['id'],
                        name=feed_cfg['name'],
                        wewe_feed_id=feed_cfg['wewe_feed_id'],
                        feed_type=FeedType.NORMAL,
                        enabled=True
                    ))
            
            # 新格式的批次 B
            for feed_cfg in (feeds_config.get('batch_b') or []):
                if feed_cfg.get('enabled', True):
                    feeds.append(WechatFeed(
                        id=feed_cfg['id'],
                        name=feed_cfg['name'],
                        wewe_feed_id=feed_cfg['wewe_feed_id'],
                        feed_type=FeedType.NORMAL,
                        enabled=True
                    ))
        
        return feeds
    
    def get_all_feeds(self) -> List[WechatFeed]:
        """获取所有公众号列表（忽略分批设置）"""
        return self.get_feeds(batch='all')
    
    def get_critical_feeds(self) -> List[WechatFeed]:
        """获取第一类公众号列表"""
        return [f for f in self.get_feeds(batch='all') if f.feed_type == FeedType.CRITICAL]
    
    def get_normal_feeds(self) -> List[WechatFeed]:
        """获取第二类公众号列表"""
        return [f for f in self.get_feeds(batch='all') if f.feed_type == FeedType.NORMAL]
    
    def get_batch_info(self) -> Dict[str, Any]:
        """获取当前批次信息"""
        current_batch = self.get_current_batch()
        feeds = self.get_feeds()
        
        from datetime import datetime
        weekday_names = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
        today = weekday_names[datetime.now().weekday()]
        
        return {
            'batch_mode': self.batch_mode,
            'current_batch': current_batch,
            'today': today,
            'feeds_count': len(feeds),
            'batch_a_days': [weekday_names[(d - 1) % 7] for d in self.batch_a_days if d != 0] + (['周日'] if 0 in self.batch_a_days else []),
            'batch_b_days': [weekday_names[(d - 1) % 7] for d in self.batch_b_days],
        }
