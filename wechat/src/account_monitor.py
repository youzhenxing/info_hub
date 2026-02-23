"""
账号监控模块 - 检查 Wewe-RSS 账号登录状态
"""

import logging
import requests
from typing import Optional, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class AccountStatus(Enum):
    """账号状态"""
    VALID = "valid"           # 有效
    EXPIRED = "expired"       # 已过期
    UNKNOWN = "unknown"       # 未知
    ERROR = "error"           # 检查出错


@dataclass
class AccountCheckResult:
    """账号检查结果"""
    status: AccountStatus
    message: str
    account_name: Optional[str] = None
    feeds_count: int = 0


class AccountMonitor:
    """Wewe-RSS 账号监控器"""
    
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
    
    def check_status(self) -> AccountCheckResult:
        """
        检查 Wewe-RSS 账号登录状态
        
        Returns:
            AccountCheckResult 包含状态和详细信息
        """
        try:
            # 1. 检查服务是否可用
            try:
                response = requests.get(f"{self.base_url}/feeds", timeout=10)
            except requests.exceptions.ConnectionError:
                return AccountCheckResult(
                    status=AccountStatus.ERROR,
                    message="无法连接到 Wewe-RSS 服务，请确保服务已启动"
                )
            except requests.exceptions.Timeout:
                return AccountCheckResult(
                    status=AccountStatus.ERROR,
                    message="连接 Wewe-RSS 服务超时"
                )
            
            # 2. 检查 feeds 数量
            feeds_count = 0
            if response.status_code == 200:
                data = response.json()
                feeds = data if isinstance(data, list) else data.get('data', [])
                feeds_count = len(feeds)
            
            # 3. 检查账号状态
            try:
                acc_response = requests.get(f"{self.base_url}/accounts", timeout=10)
                if acc_response.status_code == 200:
                    accounts = acc_response.json()
                    if isinstance(accounts, dict) and 'data' in accounts:
                        accounts = accounts['data']
                    
                    if not accounts:
                        return AccountCheckResult(
                            status=AccountStatus.EXPIRED,
                            message="未找到任何微信读书账号，请登录",
                            feeds_count=feeds_count
                        )
                    
                    # 检查是否有有效账号
                    for acc in accounts:
                        status = acc.get('status', '').lower()
                        name = acc.get('name', acc.get('vid', 'Unknown'))
                        
                        # 根据状态判断
                        if status in ['enable', 'enabled', 'active', 'valid', '1', 'true']:
                            return AccountCheckResult(
                                status=AccountStatus.VALID,
                                message=f"账号 {name} 登录有效",
                                account_name=name,
                                feeds_count=feeds_count
                            )
                    
                    # 所有账号都无效
                    return AccountCheckResult(
                        status=AccountStatus.EXPIRED,
                        message="所有微信读书账号已失效，请重新登录",
                        feeds_count=feeds_count
                    )
            except Exception as e:
                logger.warning(f"检查账号状态失败: {e}")
            
            # 4. 如果无法获取账号信息，尝试通过 feeds 判断
            if feeds_count > 0:
                # 尝试获取一个 feed 的文章来验证
                try:
                    test_response = requests.get(
                        f"{self.base_url}/feeds",
                        timeout=10
                    )
                    if test_response.status_code == 200:
                        feeds = test_response.json()
                        if isinstance(feeds, dict):
                            feeds = feeds.get('data', [])
                        
                        if feeds:
                            # 有 feeds 说明账号可能有效
                            return AccountCheckResult(
                                status=AccountStatus.VALID,
                                message=f"检测到 {feeds_count} 个公众号订阅",
                                feeds_count=feeds_count
                            )
                except:
                    pass
            
            return AccountCheckResult(
                status=AccountStatus.UNKNOWN,
                message="无法确定账号状态",
                feeds_count=feeds_count
            )
            
        except Exception as e:
            logger.error(f"检查账号状态出错: {e}")
            return AccountCheckResult(
                status=AccountStatus.ERROR,
                message=f"检查出错: {str(e)}"
            )
    
    def is_valid(self) -> Tuple[bool, str]:
        """
        快速检查账号是否有效
        
        Returns:
            (is_valid, message)
        """
        result = self.check_status()
        is_valid = result.status == AccountStatus.VALID
        return is_valid, result.message
