# coding=utf-8
"""
TrendRadar 命令行工具

提供统一的命令行接口，支持：
- 模块运行（隔离执行）
- 状态查看
- 调度管理
- 健康检查
"""

import argparse
import sys
from datetime import datetime
from typing import Optional

# 颜色定义
GREEN = '\033[0;32m'
RED = '\033[0;31m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
CYAN = '\033[0;36m'
BOLD = '\033[1m'
NC = '\033[0m'  # No Color


def cmd_run(args):
    """运行模块"""
    from .core.runner import ModuleRunner
    
    runner = ModuleRunner()
    
    if args.module == "all":
        print(f"{CYAN}🚀 运行所有模块...{NC}")
        results = runner.run_all(force=args.force)
        
        # 汇总结果
        print(f"\n{BLUE}{'='*60}{NC}")
        print(f"{BOLD}执行结果汇总{NC}")
        print(f"{BLUE}{'='*60}{NC}\n")
        
        success_count = sum(1 for r in results.values() if r.success)
        total_count = len(results)
        
        for module, result in results.items():
            status_icon = "✓" if result.success else "✗"
            status_color = GREEN if result.success else RED
            print(f"{status_color}{status_icon}{NC} {module:12} {result.message} ({result.duration_seconds:.1f}s)")
        
        print(f"\n{CYAN}完成: {success_count}/{total_count} 成功{NC}")
        
    else:
        print(f"{CYAN}🚀 运行模块: {args.module}...{NC}\n")
        result = runner.run_module(args.module, force=args.force)
        
        status_icon = "✓" if result.success else "✗"
        status_color = GREEN if result.success else RED
        print(f"\n{status_color}{status_icon}{NC} {result.message}")
        print(f"{CYAN}耗时: {result.duration_seconds:.1f}s{NC}")
        
        if result.error and not result.success:
            print(f"\n{RED}错误详情:{NC}")
            print(result.error[:500])


def cmd_status(args):
    """查看状态"""
    from .core.runner import ModuleRunner
    from .core.status import StatusDB
    from .core.loader import load_system_config
    
    system_config = load_system_config()
    runner = ModuleRunner(system_config)
    status_db = runner.status_db
    
    print(f"{BLUE}{'═'*70}{NC}")
    print(f"{BOLD}  TrendRadar 模块状态{NC}")
    print(f"{BLUE}{'═'*70}{NC}\n")
    
    # 表头
    print(f"{'模块':<12} {'启用':<6} {'最近执行':<20} {'状态':<10} {'详情':<20}")
    print(f"{'─'*70}")
    
    modules = ["podcast", "investment", "community", "wechat"]
    
    for module in modules:
        enabled = runner.is_module_enabled(module)
        enabled_str = f"{GREEN}✓{NC}" if enabled else f"{YELLOW}✗{NC}"
        
        last_run = status_db.get_last_run(module)
        if last_run:
            last_run_time = last_run.get("started_at", "")[:16].replace("T", " ")
            status = last_run.get("status", "unknown")
            
            if status == "success":
                status_str = f"{GREEN}✓ SUCCESS{NC}"
            elif status == "failed":
                status_str = f"{RED}✗ FAILED{NC}"
            elif status == "timeout":
                status_str = f"{YELLOW}⚠ TIMEOUT{NC}"
            else:
                status_str = status
            
            stats = last_run.get("stats", {})
            details = ""
            if "new_episodes" in stats:
                details = f"{stats['new_episodes']} 新节目"
            elif "total_items" in stats:
                details = f"{stats['total_items']} 条"
        else:
            last_run_time = "-"
            status_str = f"{YELLOW}未执行{NC}"
            details = ""
        
        # 下次执行
        next_run = runner._calculate_next_run(module)
        if next_run:
            next_run_str = next_run.strftime("%H:%M")
            if next_run.date() > datetime.now().date():
                next_run_str = f"明天 {next_run_str}"
        else:
            next_run_str = "-"
        
        print(f"{module:<12} {enabled_str:<15} {last_run_time:<20} {status_str:<19} {details:<20}")
    
    print(f"\n{CYAN}下次执行:{NC}")
    for module in modules:
        next_run = runner._calculate_next_run(module)
        if next_run:
            delta = next_run - datetime.now()
            minutes = int(delta.total_seconds() / 60)
            if minutes < 60:
                time_str = f"{minutes}分钟后"
            else:
                hours = minutes // 60
                mins = minutes % 60
                time_str = f"{hours}小时{mins}分钟后"
            print(f"  {module:<12} → {next_run.strftime('%H:%M')} ({time_str})")


def cmd_schedule(args):
    """显示调度时间表"""
    from .core.loader import load_system_config, get_schedule_summary
    
    print(f"{BLUE}{'═'*70}{NC}")
    print(f"{BOLD}  TrendRadar 调度时间表{NC}")
    print(f"{BLUE}{'═'*70}{NC}\n")
    
    summary = get_schedule_summary()
    
    # 调度配置
    print(f"{CYAN}调度配置:{NC}\n")
    print(f"{'模块':<12} {'类型':<10} {'触发规则':<25} {'状态':<10}")
    print(f"{'─'*60}")
    
    for m in summary["modules"]:
        enabled_str = f"{GREEN}✓ 启用{NC}" if m["enabled"] else f"{YELLOW}✗ 禁用{NC}"
        print(f"{m['name']:<12} {m['type']:<10} {m['trigger']:<25} {enabled_str}")
    
    print(f"\n{CYAN}今日时间线:{NC}\n")
    
    # 生成今日时间线
    timeline = []
    
    # 播客（每2小时）
    for h in range(0, 24, 2):
        timeline.append((f"{h:02d}:00", "播客"))
    
    # 社区
    timeline.append(("05:00", "社区"))
    
    # 投资
    timeline.append(("11:30", "投资"))
    timeline.append(("23:30", "投资"))
    
    # 公众号
    timeline.append(("23:00", "公众号"))
    
    # 日志
    timeline.append(("23:30", "日志"))
    
    # 健康检查（每30分钟）
    for h in range(0, 24):
        timeline.append((f"{h:02d}:00", "健康检查"))
        timeline.append((f"{h:02d}:30", "健康检查"))
    
    # 排序并去重
    timeline.sort(key=lambda x: x[0])
    
    # 只显示关键时间点
    key_times = ["05:00", "06:00", "08:00", "10:00", "11:30", "12:00", 
                 "14:00", "16:00", "18:00", "20:00", "22:00", "23:00", "23:30"]
    
    current_time = datetime.now().strftime("%H:%M")
    
    for time_str in key_times:
        modules = [t[1] for t in timeline if t[0] == time_str and t[1] != "健康检查"]
        if modules:
            is_past = time_str < current_time
            indicator = f"{GREEN}✓{NC}" if is_past else f"{YELLOW}○{NC}"
            module_str = ", ".join(set(modules))
            print(f"  {indicator} {time_str}  {module_str}")


def cmd_daily_log(args):
    """发送每日日志邮件"""
    from .notification.daily_log_notifier import DailyLogNotifier
    from .core.loader import load_config

    print(f"{CYAN}📋 发送每日日志邮件...{NC}\n")

    config = load_config()
    notifier = DailyLogNotifier(config)
    success = notifier.send_daily_log()

    if success:
        print(f"\n{GREEN}✓ 每日日志邮件发送成功{NC}")
    else:
        print(f"\n{RED}✗ 每日日志邮件发送失败{NC}")

    sys.exit(0 if success else 1)


def cmd_health(args):
    """健康检查"""
    from .monitor.health import HealthChecker
    
    print(f"{CYAN}🔍 系统健康检查...{NC}\n")
    
    checker = HealthChecker()
    result = checker.check_all()
    
    # 显示检查项名称映射
    name_map = {
        "ai_service": "AI 服务",
        "email_service": "邮件服务",
        "databases": "数据库",
        "wewe_rss": "Wewe-RSS 服务",
        "wewe_login": "微信读书登录",
    }
    
    for name, check in result["checks"].items():
        display_name = name_map.get(name, name)
        status = check.get("status", "unknown")
        message = check.get("message", "")
        
        if status == "ok":
            print(f"  {GREEN}✓{NC} {display_name:15} {message}")
        elif status == "warning":
            print(f"  {YELLOW}⚠{NC} {display_name:15} {message}")
        else:
            print(f"  {RED}✗{NC} {display_name:15} {message}")
        
        # 如果有详细信息，显示
        if check.get("details"):
            print(f"    {CYAN}→{NC} {check['details']}")
    
    # 汇总
    error_count = sum(1 for c in result["checks"].values() if c.get("status") == "error")
    warning_count = sum(1 for c in result["checks"].values() if c.get("status") == "warning")
    
    print()
    if error_count > 0:
        print(f"{RED}健康检查完成: {error_count} 个错误, {warning_count} 个警告{NC}")
    elif warning_count > 0:
        print(f"{YELLOW}健康检查完成: {warning_count} 个警告{NC}")
    else:
        print(f"{GREEN}健康检查完成: 全部正常 ✓{NC}")


def main():
    """主入口"""
    parser = argparse.ArgumentParser(
        description="TrendRadar 命令行工具",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    subparsers = parser.add_subparsers(dest="command", help="可用命令")
    
    # run 命令
    run_parser = subparsers.add_parser("run", help="运行模块")
    run_parser.add_argument(
        "module",
        choices=["podcast", "investment", "community", "wechat", "all"],
        help="要运行的模块"
    )
    run_parser.add_argument(
        "-f", "--force",
        action="store_true",
        help="强制执行（忽略 enabled 状态）"
    )
    
    # status 命令
    status_parser = subparsers.add_parser("status", help="查看模块状态")
    
    # schedule 命令
    schedule_parser = subparsers.add_parser("schedule", help="查看调度时间表")
    
    # health 命令
    health_parser = subparsers.add_parser("health", help="健康检查")

    # daily-log 命令
    daily_log_parser = subparsers.add_parser("daily-log", help="发送每日日志邮件")

    args = parser.parse_args()
    
    if args.command == "run":
        cmd_run(args)
    elif args.command == "status":
        cmd_status(args)
    elif args.command == "schedule":
        cmd_schedule(args)
    elif args.command == "health":
        cmd_health(args)
    elif args.command == "daily-log":
        cmd_daily_log(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
