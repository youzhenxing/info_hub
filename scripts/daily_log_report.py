#!/usr/bin/env python3
# coding=utf-8
"""
每日工作日志推送

每天 23:30 发送当日监控日志汇总邮件
包含：播客处理记录、系统状态、错误日志、监控环境信息等

使用方法:
  python scripts/daily_log_report.py          # 发送今日日志
  python scripts/daily_log_report.py --test   # 测试模式（不发送邮件）
"""

import os
import sys
import smtplib
import argparse
import sqlite3
import json
import urllib.request
from pathlib import Path
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# 添加项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 尝试从 .env 加载配置
def load_env():
    """加载环境变量"""
    env_files = [
        PROJECT_ROOT / "agents" / ".env",
        PROJECT_ROOT / "docker" / ".env",
        PROJECT_ROOT / ".env",
    ]
    for env_file in env_files:
        if env_file.exists():
            with open(env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        if key not in os.environ:
                            os.environ[key] = value

load_env()

# 配置（从环境变量读取）
EMAIL_FROM = os.environ.get("EMAIL_FROM", "{{EMAIL_ADDRESS}}")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD", "")
EMAIL_TO = os.environ.get("EMAIL_TO", "{{EMAIL_ADDRESS}}")
EMAIL_SMTP = os.environ.get("EMAIL_SMTP_SERVER", "smtp.163.com")
EMAIL_PORT = int(os.environ.get("EMAIL_SMTP_PORT", "465"))


def get_today_date():
    """获取今日日期"""
    return datetime.now().strftime("%Y-%m-%d")


def get_podcast_log():
    """获取播客处理日志"""
    today = get_today_date()
    log_entries = []
    
    # 检查播客输出目录
    podcast_dir = PROJECT_ROOT / "output" / "podcast"
    if podcast_dir.exists():
        # 查找今日处理的文件
        for f in podcast_dir.rglob("*"):
            if f.is_file():
                mtime = datetime.fromtimestamp(f.stat().st_mtime)
                if mtime.strftime("%Y-%m-%d") == today:
                    log_entries.append(f"- {f.name} ({mtime.strftime('%H:%M')})")
    
    # 检查测试输出目录
    test_dir = PROJECT_ROOT / "agents" / "podcast_full_test"
    if test_dir.exists():
        for f in test_dir.glob("*.md"):
            mtime = datetime.fromtimestamp(f.stat().st_mtime)
            if mtime.strftime("%Y-%m-%d") == today:
                log_entries.append(f"- [分析] {f.stem} ({mtime.strftime('%H:%M')})")
        for f in test_dir.glob("*.txt"):
            mtime = datetime.fromtimestamp(f.stat().st_mtime)
            if mtime.strftime("%Y-%m-%d") == today:
                size_kb = f.stat().st_size / 1024
                log_entries.append(f"- [转写] {f.stem} ({size_kb:.1f}KB, {mtime.strftime('%H:%M')})")
    
    return log_entries


def get_system_log():
    """获取系统日志"""
    today = get_today_date()
    log_entries = []
    
    logs_dir = PROJECT_ROOT / "logs"
    if logs_dir.exists():
        for f in logs_dir.glob("*.log"):
            mtime = datetime.fromtimestamp(f.stat().st_mtime)
            if mtime.strftime("%Y-%m-%d") == today:
                # 读取最后 20 行
                try:
                    lines = f.read_text(encoding='utf-8', errors='ignore').split('\n')[-20:]
                    log_entries.append(f"### {f.name}")
                    log_entries.extend([f"  {line}" for line in lines if line.strip()])
                except:
                    pass
    
    return log_entries


def get_config_changes():
    """获取配置变更"""
    config_file = PROJECT_ROOT / "config" / "config.yaml"
    if config_file.exists():
        mtime = datetime.fromtimestamp(config_file.stat().st_mtime)
        today = get_today_date()
        if mtime.strftime("%Y-%m-%d") == today:
            return f"配置文件已更新 ({mtime.strftime('%H:%M')})"
    return None


def get_git_commits():
    """获取今日 Git 提交"""
    import subprocess
    today = get_today_date()
    try:
        result = subprocess.run(
            ["git", "log", "--oneline", "--since=midnight", "--format=%h %s"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True
        )
        if result.returncode == 0 and result.stdout.strip():
            commits = result.stdout.strip().split('\n')
            return commits
    except:
        pass
    return []


def get_module_status():
    """获取模块运行状态（从 status.db）"""
    results = []
    today = get_today_date()
    
    db_paths = [
        PROJECT_ROOT / "output" / "system" / "status.db",
        Path("/home/zxy/Documents/install/trendradar/shared/output/system/status.db"),
    ]
    
    for db_path in db_paths:
        if db_path.exists():
            try:
                conn = sqlite3.connect(str(db_path))
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("""
                    SELECT module, status, message, started_at, finished_at
                    FROM module_runs 
                    WHERE DATE(started_at) = ?
                    ORDER BY started_at DESC 
                """, (today,))
                for row in cursor.fetchall():
                    results.append({
                        "module": row["module"],
                        "status": row["status"],
                        "message": row["message"] or "",
                        "started_at": row["started_at"],
                        "finished_at": row["finished_at"],
                    })
                conn.close()
                break
            except:
                pass
    
    return results


def get_health_check_status():
    """获取最近的健康检查结果"""
    db_paths = [
        PROJECT_ROOT / "output" / "system" / "status.db",
        Path("/home/zxy/Documents/install/trendradar/shared/output/system/status.db"),
    ]
    
    for db_path in db_paths:
        if db_path.exists():
            try:
                conn = sqlite3.connect(str(db_path))
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("""
                    SELECT * FROM health_checks 
                    ORDER BY checked_at DESC LIMIT 1
                """)
                row = cursor.fetchone()
                conn.close()
                if row:
                    return {
                        "overall": row["overall_status"],
                        "details": json.loads(row["details"]) if row["details"] else {},
                        "time": row["checked_at"],
                    }
            except:
                pass
    
    return None


def check_monitor_services():
    """检查监控服务状态"""
    result = {
        "dev": {"running": False, "port": 8088},
        "prod": {"running": False, "port": 8089},
    }
    
    for env, port in [("dev", 8088), ("prod", 8089)]:
        try:
            req = urllib.request.Request(f"http://localhost:{port}/api/health")
            with urllib.request.urlopen(req, timeout=3) as resp:
                if resp.status == 200:
                    result[env]["running"] = True
                    result[env]["data"] = json.loads(resp.read().decode())
        except:
            pass
    
    return result


def check_wewe_rss():
    """检查 Wewe-RSS 状态"""
    result = {
        "service": {"running": False, "feeds": 0},
        "login": {"status": "unknown", "active": 0, "total": 0},
    }
    
    # 尝试从 system.yaml 读取配置
    import yaml
    config_paths = [
        PROJECT_ROOT / "config" / "system.yaml",
        Path("/home/zxy/Documents/install/trendradar/shared/config/system.yaml"),
    ]
    
    base_url = "http://localhost:4000"
    auth_code = ""
    
    for config_path in config_paths:
        if config_path.exists():
            try:
                with open(config_path, 'r') as f:
                    config = yaml.safe_load(f)
                    wewe_config = config.get("wewe_rss", {})
                    base_url = wewe_config.get("base_url", base_url)
                    auth_code = wewe_config.get("auth_code", "")
                    break
            except:
                pass
    
    # 检查服务
    try:
        req = urllib.request.Request(f"{base_url}/feeds")
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode())
                result["service"]["running"] = True
                result["service"]["feeds"] = len(data) if isinstance(data, list) else 0
    except:
        pass
    
    # 检查账号
    if auth_code:
        try:
            req = urllib.request.Request(f"{base_url}/trpc/account.list")
            req.add_header("Authorization", f"Bearer {auth_code}")
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode())
                    accounts = data.get("result", {}).get("data", [])
                    active = sum(1 for a in accounts if a.get("status") == 1)
                    result["login"]["status"] = "ok" if active > 0 else "expired"
                    result["login"]["active"] = active
                    result["login"]["total"] = len(accounts)
        except:
            pass
    
    return result


def get_schedule_info():
    """获取调度配置信息"""
    import yaml
    
    config_paths = [
        PROJECT_ROOT / "config" / "system.yaml",
        Path("/home/zxy/Documents/install/trendradar/shared/config/system.yaml"),
    ]
    
    for config_path in config_paths:
        if config_path.exists():
            try:
                with open(config_path, 'r') as f:
                    config = yaml.safe_load(f)
                    schedule = config.get("schedule", {})
                    return {
                        "podcast": schedule.get("podcast", {}),
                        "investment": schedule.get("investment", {}),
                        "community": schedule.get("community", {}),
                        "wechat": schedule.get("wechat", {}),
                        "health_check": schedule.get("health_check", {}),
                    }
            except:
                pass
    
    return {}


def generate_report():
    """生成日志报告"""
    today = get_today_date()
    now = datetime.now().strftime("%H:%M")
    
    # 获取各种状态信息
    module_status = get_module_status()
    health_status = get_health_check_status()
    monitor_status = check_monitor_services()
    wewe_status = check_wewe_rss()
    schedule_info = get_schedule_info()
    
    report = f"""
# TrendRadar 每日工作日志

**日期**: {today}
**生成时间**: {now}

---

## 🖥️ 监控服务状态

| 环境 | 状态 | 端口 |
|------|------|------|
| 开发环境 | {"✅ 运行中" if monitor_status["dev"]["running"] else "❌ 未运行"} | 8088 |
| 生产环境 | {"✅ 运行中" if monitor_status["prod"]["running"] else "❌ 未运行"} | 8089 |

---

## 📱 Wewe-RSS / 公众号状态

| 项目 | 状态 |
|------|------|
| 服务状态 | {"✅ 正常" if wewe_status["service"]["running"] else "❌ 异常"} ({wewe_status["service"]["feeds"]} 订阅源) |
| 登录状态 | {"✅ 正常" if wewe_status["login"]["status"] == "ok" else "⚠️ 需要重新登录"} ({wewe_status["login"]["active"]}/{wewe_status["login"]["total"]} 账号) |

---

## 📊 今日模块运行记录

"""
    
    if module_status:
        report += "| 模块 | 状态 | 时间 | 消息 |\n"
        report += "|------|------|------|------|\n"
        for m in module_status:
            status_icon = "✅" if m["status"] == "success" else "❌"
            time_str = m["started_at"][:16] if m["started_at"] else "-"
            msg = m["message"][:30] if m["message"] else "-"
            report += f"| {m['module']} | {status_icon} {m['status']} | {time_str} | {msg} |\n"
    else:
        report += "今日无模块运行记录\n"
    
    report += "\n---\n\n## 🔍 最近健康检查\n\n"
    
    if health_status:
        report += f"- **整体状态**: {'✅ 正常' if health_status['overall'] == 'ok' else '⚠️ 异常'}\n"
        report += f"- **检查时间**: {health_status['time']}\n"
        if health_status.get('details'):
            report += "\n**详细状态**:\n"
            for key, value in health_status['details'].items():
                status = value.get('status', 'unknown')
                msg = value.get('message', '')
                icon = "✅" if status == "ok" else "❌"
                report += f"- {key}: {icon} {msg}\n"
    else:
        report += "暂无健康检查记录\n"
    
    report += "\n---\n\n## ⏰ 调度配置\n\n"
    
    def format_schedule(cfg):
        if not cfg.get("enabled", True):
            return "已禁用"
        stype = cfg.get("type", "interval")
        if stype == "interval":
            return f"每 {cfg.get('interval_hours', 2)} 小时"
        elif stype == "fixed":
            times = cfg.get("times", [])
            return ", ".join(times) if times else "未配置"
        return "未知"
    
    if schedule_info:
        report += f"- **播客模块**: {format_schedule(schedule_info.get('podcast', {}))}\n"
        report += f"- **投资模块**: {format_schedule(schedule_info.get('investment', {}))}\n"
        report += f"- **社区模块**: {format_schedule(schedule_info.get('community', {}))}\n"
        report += f"- **公众号模块**: {format_schedule(schedule_info.get('wechat', {}))}\n"
        hc = schedule_info.get('health_check', {})
        report += f"- **健康检查**: 每 {hc.get('interval_minutes', 30)} 分钟\n"
    
    report += "\n---\n\n## 📻 播客处理记录\n"
    
    podcast_logs = get_podcast_log()
    if podcast_logs:
        report += "\n".join(podcast_logs)
    else:
        report += "今日无播客处理记录"
    
    report += "\n\n---\n\n## 💾 Git 提交记录\n"
    
    commits = get_git_commits()
    if commits:
        for commit in commits:
            report += f"- `{commit}`\n"
    else:
        report += "今日无提交"
    
    # 配置变更
    config_change = get_config_changes()
    if config_change:
        report += f"\n\n---\n\n## ⚙️ 配置变更\n\n{config_change}"
    
    # 系统日志
    system_logs = get_system_log()
    if system_logs:
        report += "\n\n---\n\n## 📝 系统日志\n\n"
        report += "\n".join(system_logs[:50])  # 限制日志行数
    
    report += f"""

---

*由 TrendRadar 自动生成 · {today} {now}*
"""
    
    return report


def _md_to_html(md_text):
    """轻量 Markdown→HTML 转换，仅处理日报用到的格式（标题/表格/列表/代码块/行内代码/水平线）"""
    import re

    out = []
    in_pre = False
    in_table = False
    first_table_row = True

    for line in md_text.split('\n'):
        # 代码块开关
        if line.strip().startswith('```'):
            if in_pre:
                out.append('</code></pre>')
                in_pre = False
            else:
                out.append('<pre><code>')
                in_pre = True
            continue
        if in_pre:
            out.append(line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'))
            continue

        # 表格行
        if line.strip().startswith('|') and line.strip().endswith('|'):
            if not in_table:
                out.append('<table style="border-collapse:collapse;width:100%;margin:12px 0">')
                in_table = True
                first_table_row = True
            # 分隔行跳过
            if re.match(r'^\|[\s:|-]+\|$', line.strip()):
                continue
            cells = [c.strip() for c in line.strip().strip('|').split('|')]
            if first_table_row:
                out.append('<tr>' + ''.join(f'<th style="padding:6px 10px;background:#f5f5f5">{c}</th>' for c in cells) + '</tr>')
                first_table_row = False
            else:
                out.append('<tr>' + ''.join(f'<td style="padding:6px 10px">{c}</td>' for c in cells) + '</tr>')
            continue

        # 结束表格
        if in_table:
            out.append('</table>')
            in_table = False

        # 水平线
        if line.strip() in ('---', '***', '___'):
            out.append('<hr>')
            continue

        # 标题
        m = re.match(r'^(#{1,3})\s+(.+)', line)
        if m:
            lvl = len(m.group(1))
            out.append(f'<h{lvl}>{m.group(2)}</h{lvl}>')
            continue

        # 列表项
        if line.strip().startswith('- '):
            content = re.sub(r'`([^`]+)`', r'<code>\1</code>', line.strip()[2:])
            out.append(f'<li style="margin-bottom:4px">{content}</li>')
            continue

        # 行内代码
        line = re.sub(r'`([^`]+)`', r'<code>\1</code>', line)

        # 空行
        if not line.strip():
            out.append('')
            continue

        out.append(f'<p>{line.strip()}</p>')

    if in_table:
        out.append('</table>')
    if in_pre:
        out.append('</code></pre>')
    return '\n'.join(out)


def send_email(subject, body_markdown):
    """发送邮件"""
    body_html = _md_to_html(body_markdown)
    
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: -apple-system, sans-serif; line-height: 1.6; padding: 20px; max-width: 800px; margin: 0 auto; }}
        h1 {{ color: #333; border-bottom: 2px solid #07c160; padding-bottom: 10px; }}
        h2 {{ color: #07c160; margin-top: 24px; }}
        code {{ background: #f5f5f5; padding: 2px 6px; border-radius: 3px; }}
        pre {{ background: #f5f5f5; padding: 12px; border-radius: 6px; overflow-x: auto; }}
        hr {{ border: none; border-top: 1px solid #eee; margin: 20px 0; }}
        ul {{ padding-left: 20px; }}
        li {{ margin-bottom: 6px; }}
    </style>
</head>
<body>
{body_html}
</body>
</html>
"""
    
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = EMAIL_FROM
    msg['To'] = EMAIL_TO
    
    msg.attach(MIMEText(body_markdown, 'plain', 'utf-8'))
    msg.attach(MIMEText(html, 'html', 'utf-8'))
    
    server = smtplib.SMTP_SSL(EMAIL_SMTP, EMAIL_PORT)
    server.login(EMAIL_FROM, EMAIL_PASSWORD)
    server.sendmail(EMAIL_FROM, EMAIL_TO.split(','), msg.as_string())
    server.quit()


def main():
    parser = argparse.ArgumentParser(description='发送每日工作日志')
    parser.add_argument('--test', action='store_true', help='测试模式，不发送邮件')
    args = parser.parse_args()
    
    today = get_today_date()
    print(f"📝 生成 {today} 工作日志...")
    
    report = generate_report()
    
    if args.test:
        print("\n" + "=" * 50)
        print(report)
        print("=" * 50)
        print("\n✅ 测试模式，未发送邮件")
    else:
        subject = f"📋 TrendRadar 工作日志 - {today}"
        send_email(subject, report)
        print(f"✅ 日志邮件已发送: {subject}")


if __name__ == "__main__":
    main()
