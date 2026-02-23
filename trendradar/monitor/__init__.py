# coding=utf-8
"""
TrendRadar 监控模块

提供：
- Web 仪表板（基于 Python 内置 http.server）
- 健康检查
- 告警管理
"""

from .health import HealthChecker

__all__ = ["HealthChecker"]

# 延迟导入，避免循环依赖
def create_app(system_config=None):
    from .web import create_app as _create_app
    return _create_app(system_config)

def start_server(port=8088, host="127.0.0.1"):
    from .web import start_server as _start_server
    return _start_server(port, host)
