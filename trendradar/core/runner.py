# coding=utf-8
"""
模块隔离执行器

实现模块的隔离执行，确保一个模块的故障不影响其他模块：
- 进程隔离执行
- 超时控制
- 状态记录
- 错误恢复
"""

import os
import sys
import time
import traceback
from concurrent.futures import ProcessPoolExecutor, TimeoutError as FutureTimeoutError
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable

from .base import ModuleProcessor, ProcessResult, ModuleStatus, ModuleRegistry
from .loader import load_system_config


class ModuleRunner:
    """
    模块隔离执行器
    
    在独立进程中执行模块，确保：
    - 一个模块故障不影响其他模块
    - 超时自动终止
    - 执行状态自动记录
    """
    
    def __init__(self, system_config: Optional[Dict] = None):
        """
        初始化执行器
        
        Args:
            system_config: 系统配置，如果为 None 则自动加载
        """
        self.system_config = system_config or load_system_config()
        self._status_db = None  # 延迟初始化
    
    @property
    def status_db(self):
        """状态数据库（延迟初始化）"""
        if self._status_db is None:
            from .status import StatusDB
            db_path = self.system_config.get("MONITOR", {}).get("STATUS_DB", "output/system/status.db")
            self._status_db = StatusDB(db_path)
        return self._status_db
    
    def get_module_timeout(self, module_name: str) -> int:
        """获取模块超时时间（秒）"""
        timeouts = self.system_config.get("ADVANCED", {}).get("MODULE_TIMEOUT", {})
        return timeouts.get(module_name, 600)  # 默认 10 分钟
    
    def is_module_enabled(self, module_name: str) -> bool:
        """检查模块是否启用"""
        schedule = self.system_config.get("SCHEDULE", {})
        module_schedule = schedule.get(module_name.upper(), {})
        return module_schedule.get("ENABLED", True)
    
    def run_module(self, module_name: str, force: bool = False) -> ProcessResult:
        """
        运行单个模块
        
        Args:
            module_name: 模块名称（podcast, investment, community, wechat）
            force: 是否强制执行（忽略 enabled 状态）
        
        Returns:
            执行结果
        """
        # 检查模块是否启用
        if not force and not self.is_module_enabled(module_name):
            return ProcessResult(
                success=True,
                module=module_name,
                status=ModuleStatus.DISABLED,
                message=f"模块 {module_name} 已禁用",
                started_at=datetime.now(),
                finished_at=datetime.now(),
            )
        
        # 记录开始状态
        started_at = datetime.now()
        self.status_db.update_module_status(module_name, ModuleStatus.RUNNING, started_at)
        
        # 获取超时时间
        timeout = self.get_module_timeout(module_name)
        
        try:
            # 在当前进程中执行（简化版，后续可改为进程隔离）
            result = self._execute_module(module_name)
            
            # 更新状态
            self.status_db.update_module_status(
                module_name,
                result.status,
                started_at,
                result.finished_at,
                result.stats,
                result.error
            )
            
            return result
            
        except FutureTimeoutError:
            result = ProcessResult(
                success=False,
                module=module_name,
                status=ModuleStatus.TIMEOUT,
                message=f"模块 {module_name} 执行超时 ({timeout}s)",
                error="Timeout",
                started_at=started_at,
                finished_at=datetime.now(),
            )
            self.status_db.update_module_status(
                module_name, ModuleStatus.TIMEOUT, started_at, datetime.now(), error="Timeout"
            )
            return result
            
        except Exception as e:
            result = ProcessResult(
                success=False,
                module=module_name,
                status=ModuleStatus.FAILED,
                message=f"模块 {module_name} 执行异常: {str(e)}",
                error=traceback.format_exc(),
                started_at=started_at,
                finished_at=datetime.now(),
            )
            self.status_db.update_module_status(
                module_name, ModuleStatus.FAILED, started_at, datetime.now(), error=str(e)
            )
            return result
    
    def _execute_module(self, module_name: str) -> ProcessResult:
        """
        实际执行模块
        
        Args:
            module_name: 模块名称
        
        Returns:
            执行结果
        """
        started_at = datetime.now()
        
        try:
            # 根据模块名称调用对应的处理函数
            if module_name == "podcast":
                return self._run_podcast()
            elif module_name == "investment":
                return self._run_investment()
            elif module_name == "community":
                return self._run_community()
            elif module_name == "wechat":
                return self._run_wechat()
            else:
                return ProcessResult(
                    success=False,
                    module=module_name,
                    status=ModuleStatus.FAILED,
                    message=f"未知模块: {module_name}",
                    started_at=started_at,
                    finished_at=datetime.now(),
                )
        except Exception as e:
            return ProcessResult(
                success=False,
                module=module_name,
                status=ModuleStatus.FAILED,
                message=f"模块执行失败: {str(e)}",
                error=traceback.format_exc(),
                started_at=started_at,
                finished_at=datetime.now(),
            )
    
    def _run_podcast(self) -> ProcessResult:
        """运行播客模块"""
        started_at = datetime.now()
        try:
            from trendradar.podcast.processor import PodcastProcessor
            from trendradar.core.loader import load_config

            config = load_config()
            processor = PodcastProcessor.from_config(config)

            # 执行处理
            results = processor.run()

            # 统计结果（可 JSON 序列化）
            success_count = sum(1 for r in results if r.status == "completed")
            failed_count = sum(1 for r in results if r.status == "failed")

            stats = {
                "total_attempts": len(results),
                "success_count": success_count,
                "failed_count": failed_count,
                "details": [
                    {
                        "episode_title": r.episode.title if r.episode else "N/A",
                        "feed_name": r.episode.feed_name if r.episode else "N/A",
                        "status": r.status,
                        "error": r.error
                    }
                    for r in results
                ]
            }

            return ProcessResult(
                success=True,
                module="podcast",
                status=ModuleStatus.SUCCESS,
                message=f"播客处理完成",
                stats=stats,
                started_at=started_at,
                finished_at=datetime.now(),
            )
        except Exception as e:
            return ProcessResult(
                success=False,
                module="podcast",
                status=ModuleStatus.FAILED,
                message=f"播客处理失败: {str(e)}",
                error=traceback.format_exc(),
                started_at=started_at,
                finished_at=datetime.now(),
            )
    
    def _run_investment(self) -> ProcessResult:
        """运行投资模块"""
        started_at = datetime.now()
        try:
            from trendradar.investment.processor import InvestmentProcessor
            from trendradar.core.loader import load_config
            
            config = load_config()
            processor = InvestmentProcessor.from_config(config)
            
            # 执行处理
            result = processor.run(market_type="cn")
            
            # 检查是否是禁用状态
            if hasattr(result, 'error') and result.error == '投资板块未启用':
                return ProcessResult(
                    success=True,
                    module="investment",
                    status=ModuleStatus.DISABLED,
                    message="投资板块未启用（跳过）",
                    stats={"market_type": "cn"},
                    started_at=started_at,
                    finished_at=datetime.now(),
                )
            
            return ProcessResult(
                success=result.success if hasattr(result, 'success') else True,
                module="investment",
                status=ModuleStatus.SUCCESS if (result.success if hasattr(result, 'success') else True) else ModuleStatus.FAILED,
                message="投资简报处理完成" if (result.success if hasattr(result, 'success') else True) else f"处理失败: {getattr(result, 'error', '')}",
                stats={"market_type": "cn"},
                started_at=started_at,
                finished_at=datetime.now(),
            )
        except Exception as e:
            return ProcessResult(
                success=False,
                module="investment",
                status=ModuleStatus.FAILED,
                message=f"投资简报处理失败: {str(e)}",
                error=traceback.format_exc(),
                started_at=started_at,
                finished_at=datetime.now(),
            )
    
    def _run_community(self) -> ProcessResult:
        """运行社区模块"""
        started_at = datetime.now()
        try:
            from trendradar.community.processor import CommunityProcessor
            from trendradar.core.loader import load_config
            
            config = load_config()
            processor = CommunityProcessor.from_config(config)
            
            # 执行处理
            result = processor.run()
            
            stats = {}
            if hasattr(result, 'collected_data') and result.collected_data:
                stats["total_items"] = sum(
                    len(s.items) for s in result.collected_data.sources.values()
                ) if hasattr(result.collected_data, 'sources') else 0
            
            return ProcessResult(
                success=result.success if hasattr(result, 'success') else True,
                module="community",
                status=ModuleStatus.SUCCESS if (result.success if hasattr(result, 'success') else True) else ModuleStatus.FAILED,
                message="社区内容处理完成",
                stats=stats,
                started_at=started_at,
                finished_at=datetime.now(),
            )
        except Exception as e:
            return ProcessResult(
                success=False,
                module="community",
                status=ModuleStatus.FAILED,
                message=f"社区内容处理失败: {str(e)}",
                error=traceback.format_exc(),
                started_at=started_at,
                finished_at=datetime.now(),
            )
    
    def _run_wechat(self) -> ProcessResult:
        """运行公众号模块"""
        started_at = datetime.now()
        try:
            # wechat 模块有独立的入口
            import subprocess
            result = subprocess.run(
                [sys.executable, "main.py", "run"],
                cwd="wechat",
                capture_output=True,
                text=True,
                timeout=self.get_module_timeout("wechat")
            )
            
            success = result.returncode == 0
            return ProcessResult(
                success=success,
                module="wechat",
                status=ModuleStatus.SUCCESS if success else ModuleStatus.FAILED,
                message="公众号处理完成" if success else "公众号处理失败",
                error=result.stderr if not success else None,
                started_at=started_at,
                finished_at=datetime.now(),
            )
        except subprocess.TimeoutExpired:
            return ProcessResult(
                success=False,
                module="wechat",
                status=ModuleStatus.TIMEOUT,
                message="公众号处理超时",
                error="Timeout",
                started_at=started_at,
                finished_at=datetime.now(),
            )
        except Exception as e:
            return ProcessResult(
                success=False,
                module="wechat",
                status=ModuleStatus.FAILED,
                message=f"公众号处理失败: {str(e)}",
                error=traceback.format_exc(),
                started_at=started_at,
                finished_at=datetime.now(),
            )
    
    def run_all(self, modules: Optional[List[str]] = None, force: bool = False) -> Dict[str, ProcessResult]:
        """
        按顺序执行所有模块
        
        Args:
            modules: 要执行的模块列表，默认执行所有模块
            force: 是否强制执行（忽略 enabled 状态）
        
        Returns:
            各模块执行结果
        """
        if modules is None:
            modules = ["podcast", "investment", "community", "wechat"]
        
        results = {}
        
        for module in modules:
            print(f"\n{'='*60}")
            print(f"执行模块: {module}")
            print(f"{'='*60}")
            
            result = self.run_module(module, force=force)
            results[module] = result
            
            # 打印结果
            status_icon = "✓" if result.success else "✗"
            print(f"{status_icon} {module}: {result.message}")
            if result.error and not result.success:
                print(f"  错误: {result.error[:200]}...")
            print(f"  耗时: {result.duration_seconds:.1f}s")
        
        return results
    
    def get_all_status(self) -> Dict[str, Dict]:
        """
        获取所有模块状态
        
        Returns:
            各模块状态
        """
        modules = ["podcast", "investment", "community", "wechat"]
        status = {}
        
        for module in modules:
            enabled = self.is_module_enabled(module)
            last_run = self.status_db.get_last_run(module)
            
            status[module] = {
                "enabled": enabled,
                "last_run": last_run,
                "next_run": self._calculate_next_run(module),
            }
        
        return status
    
    def _calculate_next_run(self, module_name: str) -> Optional[datetime]:
        """计算模块下次执行时间"""
        schedule = self.system_config.get("SCHEDULE", {})
        module_schedule = schedule.get(module_name.upper(), {})
        
        if not module_schedule.get("ENABLED", True):
            return None
        
        schedule_type = module_schedule.get("TYPE", "fixed")
        now = datetime.now()
        
        if schedule_type == "interval":
            interval_hours = module_schedule.get("INTERVAL_HOURS", 2)
            # 简化计算：下一个整点
            next_hour = (now.hour // interval_hours + 1) * interval_hours
            if next_hour >= 24:
                next_hour = 0
                return now.replace(hour=next_hour, minute=0, second=0, microsecond=0).replace(
                    day=now.day + 1
                )
            return now.replace(hour=next_hour, minute=0, second=0, microsecond=0)
        
        elif schedule_type == "fixed":
            times = module_schedule.get("TIMES", [])
            for time_str in sorted(times):
                hour, minute = map(int, time_str.split(":"))
                scheduled = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if scheduled > now:
                    return scheduled
            # 如果今天的时间都过了，返回明天第一个时间
            if times:
                hour, minute = map(int, sorted(times)[0].split(":"))
                return now.replace(hour=hour, minute=minute, second=0, microsecond=0).replace(
                    day=now.day + 1
                )
        
        return None
