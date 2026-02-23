# coding=utf-8
"""
统一调度系统

管理所有模块的执行调度，替代分散的 cron 配置。

支持两种调度模式：
- interval: 间隔执行（如每2小时）
- fixed: 固定时间执行（如每天 11:30）

使用方式：
- 作为守护进程运行：python -m trendradar.core.scheduler start
- 单次检查并执行：python -m trendradar.core.scheduler run-due
"""

import time
import signal
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field

from .loader import load_system_config
from .runner import ModuleRunner
from .status import StatusDB


@dataclass
class ScheduleTask:
    """调度任务"""
    module: str                         # 模块名称
    schedule_type: str                  # interval | fixed
    interval_hours: Optional[int] = None  # 间隔小时数
    interval_days: int = 1              # 间隔天数（用于 fixed 类型，默认每天执行）
    fixed_times: List[str] = field(default_factory=list)  # 固定执行时间
    enabled: bool = True                # 是否启用
    last_run: Optional[datetime] = None # 上次执行时间


class Scheduler:
    """
    统一调度器
    
    根据 config/system.yaml 中的 schedule 配置，
    管理所有模块的执行时间。
    """
    
    def __init__(self, system_config: Optional[Dict] = None):
        """
        初始化调度器
        
        Args:
            system_config: 系统配置，如果为 None 则自动加载
        """
        self.system_config = system_config or load_system_config()
        self.tasks: Dict[str, ScheduleTask] = {}
        self._running = False
        self._load_schedule()
    
    @classmethod
    def from_config(cls) -> "Scheduler":
        """从配置文件创建调度器"""
        return cls(load_system_config())
    
    def _load_schedule(self) -> None:
        """从配置加载调度"""
        schedule = self.system_config.get("SCHEDULE", {})
        
        for module, config in schedule.items():
            module_name = module.lower()
            
            task = ScheduleTask(
                module=module_name,
                schedule_type=config.get("TYPE", "fixed"),
                interval_hours=config.get("INTERVAL_HOURS"),
                interval_days=config.get("INTERVAL_DAYS", 1),  # 默认每天执行
                fixed_times=config.get("TIMES", []),
                enabled=config.get("ENABLED", True),
            )
            
            self.tasks[module_name] = task
    
    def get_config(self) -> Dict[str, Dict]:
        """获取调度配置"""
        return {
            module: {
                "type": task.schedule_type,
                "interval_hours": task.interval_hours,
                "interval_days": task.interval_days,
                "times": task.fixed_times,
                "enabled": task.enabled,
            }
            for module, task in self.tasks.items()
        }
    
    def is_task_due(self, task: ScheduleTask, now: datetime = None) -> bool:
        """
        检查任务是否到期需要执行
        
        Args:
            task: 调度任务
            now: 当前时间（用于测试）
        
        Returns:
            是否到期
        """
        if not task.enabled:
            return False
        
        now = now or datetime.now()
        
        if task.schedule_type == "interval":
            # 间隔执行：检查距离上次执行是否超过间隔
            if task.last_run is None:
                return True
            
            elapsed = now - task.last_run
            interval = timedelta(hours=task.interval_hours or 2)
            return elapsed >= interval
        
        elif task.schedule_type == "fixed":
            # 固定时间执行：检查当前是否在执行窗口内
            current_time = now.strftime("%H:%M")
            
            for scheduled_time in task.fixed_times:
                # 检查是否在执行窗口内（±5分钟）
                if self._is_within_window(current_time, scheduled_time, minutes=5):
                    # 检查是否已执行
                    if task.last_run is None:
                        return True
                    
                    # 检查间隔天数
                    days_since_last = (now.date() - task.last_run.date()).days
                    if days_since_last < task.interval_days:
                        # 还没到下次执行日
                        return False
                    
                    if task.last_run.date() < now.date():
                        return True
                    
                    # 检查这个时间点是否已执行
                    last_run_time = task.last_run.strftime("%H:%M")
                    if not self._is_within_window(last_run_time, scheduled_time, minutes=10):
                        return True
            
            return False
        
        return False
    
    def _is_within_window(self, time1: str, time2: str, minutes: int = 5) -> bool:
        """检查两个时间是否在指定分钟数内"""
        t1_parts = time1.split(":")
        t2_parts = time2.split(":")
        
        t1_minutes = int(t1_parts[0]) * 60 + int(t1_parts[1])
        t2_minutes = int(t2_parts[0]) * 60 + int(t2_parts[1])
        
        diff = abs(t1_minutes - t2_minutes)
        return diff <= minutes
    
    def get_due_tasks(self) -> List[ScheduleTask]:
        """获取所有到期任务"""
        return [task for task in self.tasks.values() if self.is_task_due(task)]
    
    def get_next_run(self, module: str) -> Optional[datetime]:
        """
        获取模块下次执行时间
        
        Args:
            module: 模块名称
        
        Returns:
            下次执行时间
        """
        task = self.tasks.get(module.lower())
        if not task or not task.enabled:
            return None
        
        now = datetime.now()
        
        if task.schedule_type == "interval":
            if task.last_run:
                next_run = task.last_run + timedelta(hours=task.interval_hours or 2)
                if next_run < now:
                    return now
                return next_run
            else:
                # 没有执行过，返回下一个整点
                interval = task.interval_hours or 2
                next_hour = (now.hour // interval + 1) * interval
                if next_hour >= 24:
                    return now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
                return now.replace(hour=next_hour, minute=0, second=0, microsecond=0)
        
        elif task.schedule_type == "fixed":
            # 计算下一个执行日期
            if task.last_run:
                next_day = task.last_run.date() + timedelta(days=task.interval_days)
            else:
                next_day = now.date()
            
            # 如果下一个执行日是今天，检查时间
            if next_day == now.date():
                for time_str in sorted(task.fixed_times):
                    hour, minute = map(int, time_str.split(":"))
                    scheduled = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    if scheduled > now:
                        return scheduled
                # 今天时间都过了，推到下一个周期
                next_day = now.date() + timedelta(days=task.interval_days)
            
            # 返回下一执行日的第一个时间
            if task.fixed_times:
                first_time = sorted(task.fixed_times)[0]
                hour, minute = map(int, first_time.split(":"))
                next_date = datetime.combine(next_day, datetime.min.time())
                return next_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        return None
    
    def get_next_runs(self) -> Dict[str, Optional[datetime]]:
        """获取所有模块下次执行时间"""
        return {module: self.get_next_run(module) for module in self.tasks.keys()}
    
    def get_today_schedule(self) -> List[Dict]:
        """
        获取今日调度时间表
        
        Returns:
            按时间排序的今日调度列表
        """
        today = []
        now = datetime.now()
        
        for module, task in self.tasks.items():
            if not task.enabled:
                continue
            
            if task.schedule_type == "interval":
                # 生成今日所有执行时间
                interval = task.interval_hours or 2
                for hour in range(0, 24, interval):
                    scheduled = now.replace(hour=hour, minute=0, second=0, microsecond=0)
                    today.append({
                        "time": f"{hour:02d}:00",
                        "module": module,
                        "type": "interval",
                        "done": scheduled < now,
                    })
            
            elif task.schedule_type == "fixed":
                for time_str in task.fixed_times:
                    hour, minute = map(int, time_str.split(":"))
                    scheduled = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    today.append({
                        "time": time_str,
                        "module": module,
                        "type": "fixed",
                        "done": scheduled < now,
                    })
        
        # 按时间排序
        today.sort(key=lambda x: x["time"])
        return today
    
    def get_week_calendar(self) -> Dict[str, List[Dict]]:
        """
        获取本周日历视图
        
        Returns:
            按日期分组的调度信息
        """
        calendar = {}
        now = datetime.now()
        
        for i in range(7):
            day = now + timedelta(days=i)
            day_str = day.strftime("%Y-%m-%d")
            weekday = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][day.weekday()]
            
            calendar[day_str] = {
                "weekday": weekday,
                "tasks": self.get_today_schedule(),  # 每天调度相同
            }
        
        return calendar
    
    def run_due_tasks(self) -> Dict[str, Any]:
        """
        运行所有到期任务
        
        Returns:
            执行结果
        """
        runner = ModuleRunner(self.system_config)
        results = {}
        
        due_tasks = self.get_due_tasks()
        
        if not due_tasks:
            return {"status": "no_tasks", "message": "没有到期任务"}
        
        for task in due_tasks:
            print(f"执行任务: {task.module}")
            result = runner.run_module(task.module)
            results[task.module] = result.to_dict()
            
            # 更新 last_run
            task.last_run = datetime.now()
        
        return {"status": "completed", "results": results}
    
    def start_daemon(self, check_interval: int = 60) -> None:
        """
        启动调度守护进程
        
        Args:
            check_interval: 检查间隔（秒）
        """
        self._running = True
        
        # 注册信号处理
        def handle_signal(signum, frame):
            print("\n收到停止信号，正在退出...")
            self._running = False
        
        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)
        
        print(f"调度器启动，检查间隔: {check_interval}秒")
        print("按 Ctrl+C 停止")
        print()
        
        # 加载上次执行时间
        self._load_last_runs()
        
        while self._running:
            try:
                # 检查并执行到期任务
                due_tasks = self.get_due_tasks()
                
                if due_tasks:
                    for task in due_tasks:
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] 执行任务: {task.module}")
                        
                        runner = ModuleRunner(self.system_config)
                        result = runner.run_module(task.module)
                        
                        status = "✓" if result.success else "✗"
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] {status} {task.module}: {result.message}")
                        
                        # 更新 last_run
                        task.last_run = datetime.now()
                        self._save_last_run(task.module, task.last_run)
                
                # 等待下一次检查
                time.sleep(check_interval)
                
            except Exception as e:
                print(f"调度器错误: {e}")
                time.sleep(check_interval)
        
        print("调度器已停止")
    
    def _load_last_runs(self) -> None:
        """从状态数据库加载上次执行时间"""
        try:
            status_db = StatusDB(
                self.system_config.get("MONITOR", {}).get("STATUS_DB", "output/system/status.db")
            )
            
            for module, task in self.tasks.items():
                last_run = status_db.get_last_run(module)
                if last_run and last_run.get("started_at"):
                    task.last_run = datetime.fromisoformat(last_run["started_at"])
        except Exception:
            pass
    
    def _save_last_run(self, module: str, last_run: datetime) -> None:
        """保存上次执行时间（由 runner 自动处理）"""
        pass  # runner 已经保存了执行记录


def main():
    """命令行入口"""
    import sys
    
    if len(sys.argv) < 2:
        print("用法: python -m trendradar.core.scheduler <command>")
        print()
        print("命令:")
        print("  start      启动调度守护进程")
        print("  run-due    运行所有到期任务")
        print("  status     显示调度状态")
        return
    
    command = sys.argv[1]
    scheduler = Scheduler.from_config()
    
    if command == "start":
        scheduler.start_daemon()
    
    elif command == "run-due":
        result = scheduler.run_due_tasks()
        print(f"执行结果: {result}")
    
    elif command == "status":
        print("调度配置:")
        for module, config in scheduler.get_config().items():
            enabled = "✓" if config["enabled"] else "✗"
            if config["type"] == "interval":
                trigger = f"每{config['interval_hours']}小时"
            else:
                interval_days = config.get("interval_days", 1)
                times_str = ", ".join(config["times"])
                if interval_days > 1:
                    trigger = f"每{interval_days}天 {times_str}"
                else:
                    trigger = times_str
            print(f"  {module:12} {enabled} {trigger}")
        
        print("\n下次执行:")
        for module, next_run in scheduler.get_next_runs().items():
            if next_run:
                print(f"  {module:12} → {next_run.strftime('%Y-%m-%d %H:%M')}")
            else:
                print(f"  {module:12} → 禁用")
    
    else:
        print(f"未知命令: {command}")


if __name__ == "__main__":
    main()
