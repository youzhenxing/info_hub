# coding=utf-8
"""
健康检查模块

定期检查系统依赖服务的健康状态：
- AI 服务
- 邮件服务
- 数据库
- Wewe-RSS（公众号服务）
"""

import os
import time
from datetime import datetime
from typing import Dict, Any, Optional

from ..core.loader import load_system_config
from ..core.status import StatusDB


class HealthChecker:
    """
    健康检查器
    
    检查系统依赖服务的健康状态，并记录结果。
    """
    
    def __init__(self, system_config: Optional[Dict] = None):
        """
        初始化健康检查器
        
        Args:
            system_config: 系统配置，如果为 None 则自动加载
        """
        self.system_config = system_config or load_system_config()
        self._status_db = None
    
    @property
    def status_db(self) -> StatusDB:
        """状态数据库（延迟初始化）"""
        if self._status_db is None:
            db_path = self.system_config.get("MONITOR", {}).get("STATUS_DB", "output/system/status.db")
            self._status_db = StatusDB(db_path)
        return self._status_db
    
    def check_all(self) -> Dict[str, Any]:
        """
        执行所有健康检查
        
        Returns:
            检查结果
        """
        checks = {}
        
        # AI 服务检查
        checks["ai_service"] = self._check_ai_service()
        
        # 邮件服务检查
        checks["email_service"] = self._check_email_service()
        
        # 数据库检查
        checks["databases"] = self._check_databases()
        
        # Wewe-RSS 检查（公众号数据源）
        checks["wewe_rss"] = self._check_wewe_rss()
        
        # 微信读书登录状态检查
        checks["wewe_login"] = self._check_wewe_login()
        
        # 计算总体状态
        error_count = sum(1 for c in checks.values() if c.get("status") == "error")
        warning_count = sum(1 for c in checks.values() if c.get("status") == "warning")
        
        if error_count > 0:
            overall = "error"
        elif warning_count > 0:
            overall = "warning"
        else:
            overall = "ok"
        
        result = {
            "overall": overall,
            "checks": checks,
            "checked_at": datetime.now().isoformat(),
        }
        
        # 保存检查结果
        self.status_db.save_health_check(result)
        
        # 如果有错误，添加告警
        if overall == "error":
            for name, check in checks.items():
                if check.get("status") == "error":
                    self.status_db.add_alert(
                        module=None,
                        level="error",
                        message=f"健康检查失败: {name}",
                        details=check.get("message")
                    )
        
        return result
    
    def _check_ai_service(self) -> Dict[str, Any]:
        """检查 AI 服务"""
        ai_config = self.system_config.get("AI", {})
        
        if not ai_config.get("API_KEY") and not ai_config.get("MODEL"):
            return {"status": "warning", "message": "未配置 AI 服务"}
        
        # 只检查配置是否存在，不实际调用 API
        if ai_config.get("MODEL") and ai_config.get("API_BASE"):
            return {"status": "ok", "message": "配置正常"}
        
        return {"status": "warning", "message": "配置不完整"}
    
    def _check_email_service(self) -> Dict[str, Any]:
        """检查邮件服务"""
        email = self.system_config.get("NOTIFICATION", {}).get("CHANNELS", {}).get("EMAIL", {})
        
        if not email.get("FROM") or not email.get("PASSWORD"):
            return {"status": "warning", "message": "未配置邮件服务"}
        
        # 检查 SMTP 连接
        try:
            import smtplib
            
            from_addr = email.get("FROM", "")
            smtp_server = email.get("SMTP_SERVER", "")
            smtp_port = email.get("SMTP_PORT", "")
            
            # 如果没有配置 SMTP 服务器，根据邮箱域名推断
            if not smtp_server:
                if "163.com" in from_addr:
                    smtp_server = "smtp.163.com"
                    smtp_port = smtp_port or "465"
                elif "qq.com" in from_addr:
                    smtp_server = "smtp.qq.com"
                    smtp_port = smtp_port or "465"
                elif "gmail.com" in from_addr:
                    smtp_server = "smtp.gmail.com"
                    smtp_port = smtp_port or "587"
                else:
                    return {"status": "warning", "message": "无法推断 SMTP 服务器"}
            
            # 尝试连接（不发送邮件）
            # 注意：这里只检查配置，不实际建立连接以避免超时
            return {"status": "ok", "message": f"配置正常 ({smtp_server})"}
            
        except Exception as e:
            return {"status": "error", "message": f"连接失败: {str(e)}"}
    
    def _check_databases(self) -> Dict[str, Any]:
        """检查数据库"""
        databases = self.system_config.get("DATABASES", {})
        
        ok_count = 0
        pending_count = 0
        errors = []
        
        # 按需创建的数据库（不存在时不报错）
        optional_dbs = ["SYSTEM", "INVESTMENT", "COMMUNITY"]
        
        for name, path in databases.items():
            if os.path.exists(path):
                ok_count += 1
            elif name.upper() in optional_dbs:
                # 可选数据库可能还未创建
                pending_count += 1
            else:
                errors.append(f"{name}: {path}")
        
        total = len(databases)
        
        if errors:
            return {
                "status": "warning",
                "message": f"{ok_count}/{total} 正常",
                "errors": errors
            }
        
        if pending_count > 0:
            return {"status": "ok", "message": f"{ok_count}/{total} 正常 ({pending_count} 待创建)"}
        
        return {"status": "ok", "message": f"{ok_count}/{total} 正常"}
    
    def _check_wewe_rss(self) -> Dict[str, Any]:
        """检查 Wewe-RSS 服务（公众号数据源）"""
        try:
            import requests
            
            wewe_config = self.system_config.get("WEWE_RSS", {})
            base_url = wewe_config.get("BASE_URL", "http://localhost:4000")
            
            # 尝试连接 Wewe-RSS 服务（使用 /feeds 端点，无需认证）
            wewe_url = f"{base_url}/feeds"
            
            response = requests.get(wewe_url, timeout=5)
            
            if response.status_code == 200:
                feeds = response.json()
                return {"status": "ok", "message": f"服务正常 ({len(feeds)} 订阅源)"}
            else:
                return {"status": "warning", "message": f"HTTP {response.status_code}"}
                
        except requests.exceptions.ConnectionError:
            return {"status": "warning", "message": "服务未运行"}
        except Exception as e:
            return {"status": "warning", "message": f"检查失败: {str(e)}"}
    
    def _check_wewe_login(self) -> Dict[str, Any]:
        """检查微信读书登录状态"""
        try:
            import requests
            
            wewe_config = self.system_config.get("WEWE_RSS", {})
            base_url = wewe_config.get("BASE_URL", "http://localhost:4000")
            auth_code = wewe_config.get("AUTH_CODE", "") or os.environ.get("WEWE_AUTH_CODE", "")
            
            # 使用 tRPC API 获取账号列表
            accounts_url = f"{base_url}/trpc/account.list?input=%7B%7D"
            headers = {"Authorization": auth_code} if auth_code else {}
            
            response = requests.get(accounts_url, headers=headers, timeout=10)
            
            if response.status_code == 401:
                return {"status": "warning", "message": "认证失败，请检查 AUTH_CODE"}
            
            if response.status_code != 200:
                return {"status": "warning", "message": f"HTTP {response.status_code}"}
            
            data = response.json()
            
            # tRPC 响应格式: {"result":{"data":{"blocks":[],"items":[...]}}}
            result_data = data.get("result", {}).get("data", {})
            accounts = result_data.get("items", [])
            blocks = result_data.get("blocks", [])  # 今日小黑屋账号 ID 列表
            
            if not accounts:
                return {"status": "warning", "message": "未获取到账号"}
            
            # 检查账号状态
            # status: 1=正常, 2=失效
            active_count = 0
            expired_count = 0
            blacklisted_count = 0
            account_names = []
            
            for account in accounts:
                acc_id = account.get("id", "")
                acc_name = account.get("name", "未知")
                status = account.get("status", 0)
                
                account_names.append(acc_name)
                
                if acc_id in blocks:
                    # 账号在今日小黑屋
                    blacklisted_count += 1
                elif status == 1:
                    # 状态正常
                    active_count += 1
                elif status in [0, 2]:
                    # 状态失效 (0=未知, 2=失效)
                    expired_count += 1
            
            total = len(accounts)
            
            # 判断状态
            if expired_count > 0:
                # 有账号失效，需要重新登录
                external_url = wewe_config.get("EXTERNAL_URL", base_url)
                return {
                    "status": "error",
                    "message": f"登录失效 ({expired_count}/{total})",
                    "details": f"请访问 {external_url}/dash 重新扫码登录",
                    "accounts": {
                        "total": total,
                        "active": active_count,
                        "expired": expired_count,
                        "blacklisted": blacklisted_count,
                        "names": account_names
                    }
                }
            elif blacklisted_count > 0:
                # 有账号在小黑屋
                return {
                    "status": "warning",
                    "message": f"小黑屋 ({blacklisted_count}/{total})",
                    "details": "部分账号暂时受限，请稍后再试",
                    "accounts": {
                        "total": total,
                        "active": active_count,
                        "expired": expired_count,
                        "blacklisted": blacklisted_count,
                        "names": account_names
                    }
                }
            else:
                return {
                    "status": "ok",
                    "message": f"正常 ({active_count}/{total})",
                    "accounts": {
                        "total": total,
                        "active": active_count,
                        "expired": expired_count,
                        "blacklisted": blacklisted_count,
                        "names": account_names
                    }
                }
                
        except requests.exceptions.ConnectionError:
            return {"status": "warning", "message": "服务未运行"}
        except Exception as e:
            return {"status": "warning", "message": f"检查失败: {str(e)}"}


def run_health_check():
    """命令行运行健康检查"""
    checker = HealthChecker()
    result = checker.check_all()
    
    print(f"健康检查结果: {result['overall']}")
    print()
    
    for name, check in result["checks"].items():
        status = check.get("status", "unknown")
        message = check.get("message", "")
        
        if status == "ok":
            icon = "✓"
        elif status == "warning":
            icon = "⚠"
        else:
            icon = "✗"
        
        print(f"  {icon} {name:15} {message}")


if __name__ == "__main__":
    run_health_check()
