"""
账号监控器 - 检查 Wewe-RSS 账号状态
"""

import logging
from typing import List, Optional
from datetime import datetime

import requests

from .models import WeweAccount, AccountStatus
from .config_loader import ConfigLoader
from .notifier import WechatNotifier

logger = logging.getLogger(__name__)


class AccountMonitor:
    """Wewe-RSS 账号监控器"""
    
    def __init__(self, config: ConfigLoader, notifier: WechatNotifier):
        self.config = config
        self.notifier = notifier
        self.wewe_config = config.wewe_rss
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'WechatMonitor/1.0'
        })
    
    def check_accounts(self) -> List[WeweAccount]:
        """
        检查所有账号状态
        
        Returns:
            账号列表
        """
        logger.info("检查 Wewe-RSS 账号状态")
        
        try:
            accounts = self._fetch_accounts()
            
            # 检查是否有失效的账号
            expired_accounts = [
                a for a in accounts
                if a.status == AccountStatus.EXPIRED
            ]
            
            if expired_accounts and self.config.account_monitor_alert:
                self._send_alerts(expired_accounts)
            
            return accounts
            
        except Exception as e:
            logger.error(f"检查账号状态失败: {e}")
            return []
    
    def _fetch_accounts(self) -> List[WeweAccount]:
        """从 Wewe-RSS API 获取账号列表"""
        # Wewe-RSS 的账号 API
        url = f"{self.wewe_config.base_url}/api/accounts"
        
        params = {}
        if self.wewe_config.auth_code:
            params['code'] = self.wewe_config.auth_code
        
        try:
            response = self.session.get(url, params=params, timeout=30)
            
            # 如果 API 不存在，尝试其他方式
            if response.status_code == 404:
                logger.warning("Wewe-RSS 账号 API 不可用，跳过状态检查")
                return []
            
            response.raise_for_status()
            data = response.json()
            
            accounts = []
            for item in data.get('data', data.get('accounts', [])):
                status = self._parse_status(item.get('status', ''))
                
                accounts.append(WeweAccount(
                    id=str(item.get('id', '')),
                    name=item.get('name', item.get('nickname', '未知账号')),
                    status=status,
                    last_update=self._parse_datetime(item.get('updateTime', item.get('updated_at')))
                ))
            
            logger.info(f"获取到 {len(accounts)} 个账号")
            return accounts
            
        except requests.exceptions.RequestException as e:
            logger.warning(f"获取账号列表失败: {e}")
            return []
    
    def _parse_status(self, status_str: str) -> AccountStatus:
        """解析账号状态"""
        status_str = status_str.lower()
        
        if status_str in ['active', 'normal', '正常']:
            return AccountStatus.ACTIVE
        elif status_str in ['expired', 'invalid', '失效']:
            return AccountStatus.EXPIRED
        elif status_str in ['disabled', '禁用']:
            return AccountStatus.DISABLED
        elif status_str in ['blacklisted', 'blocked', '小黑屋', '今日小黑屋']:
            return AccountStatus.BLACKLISTED
        else:
            # 默认认为是正常
            return AccountStatus.ACTIVE
    
    def _parse_datetime(self, dt_str: Optional[str]) -> Optional[datetime]:
        """解析日期时间"""
        if not dt_str:
            return None
        
        try:
            from dateutil import parser
            return parser.parse(dt_str)
        except:
            return None
    
    def _send_alerts(self, expired_accounts: List[WeweAccount]):
        """发送账号失效提醒"""
        for account in expired_accounts:
            logger.warning(f"账号失效: {account.name}")
            
            # 发送邮件提醒
            self.notifier.send_account_alert(
                account_name=account.name,
                external_url=self.wewe_config.external_url
            )
    
    def get_status_summary(self) -> str:
        """获取账号状态摘要"""
        accounts = self._fetch_accounts()
        
        if not accounts:
            return "未获取到账号信息"
        
        status_counts = {}
        for account in accounts:
            status_name = account.status.value
            status_counts[status_name] = status_counts.get(status_name, 0) + 1
        
        parts = [f"{status}: {count}" for status, count in status_counts.items()]
        return f"共 {len(accounts)} 个账号 - " + ", ".join(parts)
