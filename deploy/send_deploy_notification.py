#!/usr/bin/env python3
# coding=utf-8
"""
部署通知邮件脚本

在版本发布后发送部署成功通知邮件，包含：
- 版本信息和 Git 提交记录
- 各模块健康检查状态（播客源、投资数据源等）
- Docker 镜像和服务状态
"""

import os
import sys
import smtplib
import subprocess
import sqlite3
import json
import time
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib.request
import urllib.error
import ssl
import yaml

DEV_BASE = Path("/home/zxy/Documents/code/TrendRadar")
PROD_BASE = Path("/home/zxy/Documents/install/trendradar")

# 加载 .env 文件
def load_env():
    """加载环境变量"""
    env_files = [
        DEV_BASE / "agents" / ".env",
        DEV_BASE / "docker" / ".env",
        DEV_BASE / ".env",
        PROD_BASE / "shared" / ".env",
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


def get_version():
    """获取版本号"""
    version_file = DEV_BASE / "version"
    if version_file.exists():
        return version_file.read_text().strip()
    return "unknown"


def get_git_log(count=5):
    """获取最近的 git 提交记录"""
    try:
        result = subprocess.run(
            ["git", "-C", str(DEV_BASE), "log", f"-{count}", 
             "--pretty=format:%h|%s|%cr"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            commits = []
            for line in result.stdout.strip().split('\n'):
                parts = line.split('|', 2)
                if len(parts) == 3:
                    commits.append({
                        'hash': parts[0],
                        'message': parts[1][:50],
                        'time': parts[2]
                    })
            return commits
    except Exception:
        pass
    return []


def get_docker_images():
    """获取相关 Docker 镜像信息"""
    try:
        result = subprocess.run(
            ["docker", "images", "--format", "{{.Repository}}:{{.Tag}}\t{{.Size}}\t{{.CreatedSince}}",
             "--filter", "reference=trendradar*"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0 and result.stdout.strip():
            images = []
            for line in result.stdout.strip().split('\n')[:5]:
                parts = line.split('\t')
                if len(parts) >= 2:
                    images.append({
                        'name': parts[0],
                        'size': parts[1] if len(parts) > 1 else '-',
                        'created': parts[2] if len(parts) > 2 else '-'
                    })
            return images
    except Exception:
        pass
    return []


def check_url(url: str, timeout: int = 10, max_retries: int = 2, retry_delay: int = 5) -> Tuple[bool, str]:
    """
    检查 URL 是否可访问（支持重试）

    Args:
        url: 要检查的URL
        timeout: 请求超时时间（秒）
        max_retries: 最大重试次数（失败后重试的次数）
        retry_delay: 重试延迟时间（秒）

    Returns:
        (是否成功, 状态消息)
    """
    for attempt in range(max_retries + 1):
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

            req = urllib.request.Request(
                url,
                headers={'User-Agent': 'Mozilla/5.0 TrendRadar/1.0'}
            )
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as response:
                if response.status == 200:
                    if attempt > 0:
                        return True, f"正常（重试{attempt}次后成功）"
                    return True, "正常"
                return False, f"HTTP {response.status}"
        except urllib.error.HTTPError as e:
            if attempt < max_retries:
                time.sleep(retry_delay)
                continue
            return False, f"HTTP {e.code}"
        except urllib.error.URLError as e:
            if attempt < max_retries:
                time.sleep(retry_delay)
                continue
            return False, f"连接失败"
        except Exception as e:
            if attempt < max_retries:
                time.sleep(retry_delay)
                continue
            return False, str(e)[:20]

    return False, "已达最大重试次数"


def load_config() -> dict:
    """加载配置文件"""
    config_path = PROD_BASE / "shared" / "config" / "config.yaml"
    if not config_path.exists():
        config_path = DEV_BASE / "config" / "config.yaml"
    
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    return {}


def check_podcast_feeds(config: dict) -> List[Dict]:
    """检查播客源访问状态"""
    results = []
    podcast_config = config.get("podcast", {})
    feeds = podcast_config.get("feeds", [])
    
    def check_feed(feed):
        name = feed.get("name", "未知")
        url = feed.get("url", "")
        enabled = feed.get("enabled", True)
        
        if not enabled:
            return {"name": name, "status": "disabled", "message": "已禁用"}
        
        if not url:
            return {"name": name, "status": "error", "message": "无URL"}
        
        # 增加超时时间到15秒，并启用重试机制（最多重试2次，延迟5秒）
        ok, msg = check_url(url, timeout=15, max_retries=2, retry_delay=5)
        return {
            "name": name,
            "status": "ok" if ok else "error",
            "message": msg
        }
    
    # 并发检查所有播客源
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(check_feed, feed): feed for feed in feeds}
        for future in as_completed(futures):
            try:
                results.append(future.result())
            except:
                pass
    
    return results


def check_investment_sources() -> List[Dict]:
    """检查投资数据源状态"""
    sources = [
        {"name": "东方财富-指数", "url": "https://push2.eastmoney.com/api/qt/ulist/get"},
        {"name": "CoinGecko-加密货币", "url": "https://api.coingecko.com/api/v3/ping"},
        {"name": "新浪财经-北向资金", "url": "https://hq.sinajs.cn/"},
    ]
    
    results = []
    for src in sources:
        # 启用重试机制（最多重试2次，延迟5秒）
        ok, msg = check_url(src["url"], timeout=15, max_retries=2, retry_delay=5)
        results.append({
            "name": src["name"],
            "status": "ok" if ok else "error",
            "message": msg
        })
    
    return results


def check_database_status() -> Dict:
    """检查数据库状态"""
    result = {
        "podcast_db": {"exists": False, "records": 0, "size": "-"},
        "news_db": {"exists": False, "records": 0, "size": "-"},
    }
    
    db_dir = PROD_BASE / "shared" / "output" / "news"
    
    # 检查播客数据库
    podcast_db = db_dir / "podcast.db"
    if podcast_db.exists():
        result["podcast_db"]["exists"] = True
        result["podcast_db"]["size"] = f"{podcast_db.stat().st_size // 1024}KB"
        try:
            conn = sqlite3.connect(str(podcast_db))
            cursor = conn.execute("SELECT COUNT(*) FROM podcast_episodes")
            result["podcast_db"]["records"] = cursor.fetchone()[0]
            conn.close()
        except:
            pass
    
    # 检查最新新闻数据库
    today = datetime.now().strftime("%Y-%m-%d")
    news_db = db_dir / f"{today}.db"
    if news_db.exists():
        result["news_db"]["exists"] = True
        result["news_db"]["size"] = f"{news_db.stat().st_size // 1024}KB"
    
    return result


def check_config_status(config: dict) -> Dict:
    """检查配置状态"""
    return {
        "podcast_enabled": config.get("podcast", {}).get("enabled", False),
        "investment_enabled": config.get("investment", {}).get("enabled", False),
        "email_configured": bool(config.get("notification", {}).get("channels", {}).get("email", {}).get("from")),
        "ai_configured": bool(config.get("ai", {}).get("api_key")),
    }


def load_system_config() -> dict:
    """加载系统架构配置"""
    config_path = PROD_BASE / "shared" / "config" / "system.yaml"
    if not config_path.exists():
        config_path = DEV_BASE / "config" / "system.yaml"
    
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    return {}


def check_monitor_status() -> Dict:
    """检查监控服务状态"""
    result = {
        "dev": {"running": False, "port": 8088, "url": "http://localhost:8088"},
        "prod": {"running": False, "port": 8089, "url": "http://localhost:8089"},
    }
    
    # 检查开发环境监控
    try:
        req = urllib.request.Request("http://localhost:8088/api/health")
        with urllib.request.urlopen(req, timeout=3) as resp:
            if resp.status == 200:
                result["dev"]["running"] = True
                result["dev"]["data"] = json.loads(resp.read().decode())
    except:
        pass
    
    # 检查生产环境监控
    try:
        req = urllib.request.Request("http://localhost:8089/api/health")
        with urllib.request.urlopen(req, timeout=3) as resp:
            if resp.status == 200:
                result["prod"]["running"] = True
                result["prod"]["data"] = json.loads(resp.read().decode())
    except:
        pass
    
    return result


def check_wewe_rss_status(system_config: dict) -> Dict:
    """检查 Wewe-RSS 服务状态"""
    result = {
        "service": {"running": False, "feeds": 0},
        "login": {"status": "unknown", "accounts": []},
    }
    
    wewe_config = system_config.get("wewe_rss", {})
    base_url = wewe_config.get("base_url", "http://localhost:4000")
    auth_code = wewe_config.get("auth_code", "")
    
    # 检查服务状态
    try:
        req = urllib.request.Request(f"{base_url}/feeds")
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode())
                result["service"]["running"] = True
                result["service"]["feeds"] = len(data) if isinstance(data, list) else 0
    except:
        pass
    
    # 检查账号状态
    try:
        req = urllib.request.Request(f"{base_url}/trpc/account.list")
        req.add_header("Authorization", f"Bearer {auth_code}")
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode())
                accounts = data.get("result", {}).get("data", [])
                active = sum(1 for a in accounts if a.get("status") == 1)
                expired = sum(1 for a in accounts if a.get("status") == 2)
                result["login"]["status"] = "ok" if active > 0 else "expired"
                result["login"]["active"] = active
                result["login"]["expired"] = expired
                result["login"]["total"] = len(accounts)
                result["login"]["accounts"] = [a.get("name", "未知") for a in accounts]
    except:
        pass
    
    return result


def get_schedule_config(system_config: dict) -> Dict:
    """获取调度配置"""
    schedule = system_config.get("schedule", {})
    return {
        "podcast": {
            "type": schedule.get("podcast", {}).get("type", "interval"),
            "interval": schedule.get("podcast", {}).get("interval_hours", 2),
            "enabled": schedule.get("podcast", {}).get("enabled", True),
        },
        "investment": {
            "type": schedule.get("investment", {}).get("type", "fixed"),
            "times": schedule.get("investment", {}).get("times", []),
            "enabled": schedule.get("investment", {}).get("enabled", True),
        },
        "community": {
            "type": schedule.get("community", {}).get("type", "fixed"),
            "times": schedule.get("community", {}).get("times", []),
            "enabled": schedule.get("community", {}).get("enabled", True),
        },
        "wechat": {
            "type": schedule.get("wechat", {}).get("type", "fixed"),
            "times": schedule.get("wechat", {}).get("times", []),
            "enabled": schedule.get("wechat", {}).get("enabled", True),
        },
        "health_check": {
            "interval": schedule.get("health_check", {}).get("interval_minutes", 30),
            "enabled": schedule.get("health_check", {}).get("enabled", True),
        },
    }


def get_module_status_from_db() -> List[Dict]:
    """从状态数据库获取最近的模块运行状态"""
    results = []
    
    db_path = PROD_BASE / "shared" / "output" / "system" / "status.db"
    if not db_path.exists():
        db_path = DEV_BASE / "output" / "system" / "status.db"
    
    if not db_path.exists():
        return results
    
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("""
            SELECT module, status, message, started_at, finished_at
            FROM module_runs 
            ORDER BY started_at DESC 
            LIMIT 10
        """)
        for row in cursor.fetchall():
            results.append({
                "module": row["module"],
                "status": row["status"],
                "message": row["message"],
                "time": row["started_at"],
            })
        conn.close()
    except:
        pass
    
    return results


def render_status_badge(status: str) -> str:
    """渲染状态徽章"""
    if status == "ok":
        return '<span class="badge ok">正常</span>'
    elif status == "disabled":
        return '<span class="badge disabled">禁用</span>'
    else:
        return '<span class="badge error">异常</span>'


def send_notification(version: str):
    """发送部署通知邮件"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 获取各项信息
    git_commits = get_git_log(5)
    docker_images = get_docker_images()
    config = load_config()
    system_config = load_system_config()
    
    # 并发执行健康检查
    print("  检查播客源...")
    podcast_status = check_podcast_feeds(config)
    print("  检查投资数据源...")
    investment_status = check_investment_sources()
    print("  检查数据库...")
    db_status = check_database_status()
    print("  检查配置...")
    config_status = check_config_status(config)
    print("  检查监控服务...")
    monitor_status = check_monitor_status()
    print("  检查 Wewe-RSS...")
    wewe_status = check_wewe_rss_status(system_config)
    print("  获取调度配置...")
    schedule_config = get_schedule_config(system_config)
    print("  获取模块状态...")
    module_status = get_module_status_from_db()
    
    # 统计健康状态
    podcast_ok = sum(1 for p in podcast_status if p["status"] == "ok")
    podcast_total = sum(1 for p in podcast_status if p["status"] != "disabled")
    invest_ok = sum(1 for i in investment_status if i["status"] == "ok")
    invest_total = len(investment_status)
    
    # 整体状态
    all_ok = podcast_ok == podcast_total and invest_ok == invest_total
    status_text = "全部正常" if all_ok else "部分异常"
    status_color = "#43a047" if all_ok else "#ff9800"
    
    # 渲染 Git 提交记录
    commits_html = ""
    for c in git_commits:
        commits_html += f'<div class="commit-item"><span class="hash">{c["hash"]}</span> {c["message"]} <span class="time">{c["time"]}</span></div>'
    
    # 渲染 Docker 镜像
    images_html = ""
    for img in docker_images:
        images_html += f'<div class="image-item">{img["name"]} <span class="size">{img["size"]}</span></div>'
    
    # 渲染播客源状态
    podcast_html = ""
    for p in podcast_status:
        badge = render_status_badge(p["status"])
        podcast_html += f'<div class="check-item"><span class="name">{p["name"]}</span> {badge}</div>'
    
    # 渲染投资数据源状态
    invest_html = ""
    for i in investment_status:
        badge = render_status_badge(i["status"])
        invest_html += f'<div class="check-item"><span class="name">{i["name"]}</span> {badge}</div>'
    
    # 渲染配置状态
    config_html = f'''
    <div class="check-item"><span class="name">播客模块</span> {render_status_badge("ok" if config_status["podcast_enabled"] else "disabled")}</div>
    <div class="check-item"><span class="name">投资模块</span> {render_status_badge("ok" if config_status["investment_enabled"] else "disabled")}</div>
    <div class="check-item"><span class="name">邮件通知</span> {render_status_badge("ok" if config_status["email_configured"] else "error")}</div>
    <div class="check-item"><span class="name">AI 分析</span> {render_status_badge("ok" if config_status["ai_configured"] else "error")}</div>
    '''
    
    # 渲染数据库状态
    db_html = f'''
    <div class="check-item">
        <span class="name">播客数据库</span>
        {render_status_badge("ok" if db_status["podcast_db"]["exists"] else "error")}
        <span class="detail">{db_status["podcast_db"]["records"]} 条记录, {db_status["podcast_db"]["size"]}</span>
    </div>
    <div class="check-item">
        <span class="name">新闻数据库</span>
        {render_status_badge("ok" if db_status["news_db"]["exists"] else "disabled")}
        <span class="detail">{db_status["news_db"]["size"]}</span>
    </div>
    '''
    
    # 渲染监控服务状态
    monitor_html = f'''
    <div class="check-item">
        <span class="name">开发环境监控</span>
        {render_status_badge("ok" if monitor_status["dev"]["running"] else "error")}
        <span class="detail">端口 {monitor_status["dev"]["port"]}</span>
    </div>
    <div class="check-item">
        <span class="name">生产环境监控</span>
        {render_status_badge("ok" if monitor_status["prod"]["running"] else "error")}
        <span class="detail">端口 {monitor_status["prod"]["port"]}</span>
    </div>
    '''
    
    # 渲染 Wewe-RSS 状态
    wewe_html = f'''
    <div class="check-item">
        <span class="name">Wewe-RSS 服务</span>
        {render_status_badge("ok" if wewe_status["service"]["running"] else "error")}
        <span class="detail">{wewe_status["service"]["feeds"]} 个订阅源</span>
    </div>
    <div class="check-item">
        <span class="name">微信读书登录</span>
        {render_status_badge("ok" if wewe_status["login"]["status"] == "ok" else ("error" if wewe_status["login"]["status"] == "expired" else "disabled"))}
        <span class="detail">{wewe_status["login"].get("active", 0)}/{wewe_status["login"].get("total", 0)} 账号正常</span>
    </div>
    '''
    
    # 渲染调度配置
    def format_schedule(cfg):
        if not cfg.get("enabled"):
            return "已禁用"
        if cfg.get("type") == "interval":
            return f"每 {cfg.get('interval', 2)} 小时"
        elif cfg.get("type") == "fixed":
            times = cfg.get("times", [])
            return ", ".join(times) if times else "未配置"
        return "未知"
    
    schedule_html = f'''
    <div class="check-item">
        <span class="name">🎙️ 播客模块</span>
        <span class="detail">{format_schedule(schedule_config["podcast"])}</span>
    </div>
    <div class="check-item">
        <span class="name">📈 投资模块</span>
        <span class="detail">{format_schedule(schedule_config["investment"])}</span>
    </div>
    <div class="check-item">
        <span class="name">🌐 社区模块</span>
        <span class="detail">{format_schedule(schedule_config["community"])}</span>
    </div>
    <div class="check-item">
        <span class="name">📱 公众号模块</span>
        <span class="detail">{format_schedule(schedule_config["wechat"])}</span>
    </div>
    <div class="check-item">
        <span class="name">🔍 健康检查</span>
        <span class="detail">每 {schedule_config["health_check"]["interval"]} 分钟</span>
    </div>
    '''
    
    # 渲染最近模块运行状态
    module_html = ""
    if module_status:
        for m in module_status[:5]:
            status_badge = render_status_badge("ok" if m["status"] == "success" else "error")
            module_html += f'''
            <div class="check-item">
                <span class="name">{m["module"]}</span>
                {status_badge}
                <span class="detail">{m["time"][:16] if m["time"] else "-"}</span>
            </div>
            '''
    else:
        module_html = '<div class="check-item"><span class="name">暂无运行记录</span></div>'
    
    # 构建邮件内容（移动端友好）
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TrendRadar 部署通知 v{version}</title>
    <style>
        * {{ box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
            margin: 0;
            padding: 8px;
            background: #fff;
            font-size: 14px;
        }}
        .header {{
            border-bottom: 3px solid {status_color};
            padding-bottom: 12px;
            margin-bottom: 16px;
        }}
        .header h1 {{
            font-size: 18px;
            margin: 0 0 6px 0;
            color: #1a1a1a;
        }}
        .header .version {{
            font-size: 28px;
            font-weight: bold;
            color: {status_color};
        }}
        .header .status {{
            display: inline-block;
            background: {status_color};
            color: #fff;
            padding: 3px 10px;
            border-radius: 4px;
            font-size: 13px;
            margin-top: 8px;
        }}
        .header .time {{
            color: #666;
            font-size: 12px;
            margin-top: 6px;
        }}
        .section {{
            margin: 16px 0;
        }}
        .section-title {{
            font-size: 14px;
            font-weight: 600;
            color: #1a73e8;
            margin-bottom: 10px;
            padding-bottom: 6px;
            border-bottom: 1px solid #eee;
        }}
        .check-item {{
            display: flex;
            align-items: center;
            padding: 6px 0;
            font-size: 13px;
            border-bottom: 1px solid #f5f5f5;
        }}
        .check-item .name {{
            flex: 1;
            color: #333;
        }}
        .check-item .detail {{
            color: #999;
            font-size: 11px;
            margin-left: 8px;
        }}
        .badge {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 3px;
            font-size: 11px;
            font-weight: 500;
        }}
        .badge.ok {{
            background: #e8f5e9;
            color: #43a047;
        }}
        .badge.error {{
            background: #ffebee;
            color: #e53935;
        }}
        .badge.disabled {{
            background: #f5f5f5;
            color: #999;
        }}
        .commit-item {{
            padding: 5px 0;
            font-size: 12px;
            border-bottom: 1px solid #f5f5f5;
        }}
        .commit-item .hash {{
            font-family: 'Monaco', 'Menlo', monospace;
            color: #1a73e8;
            margin-right: 8px;
        }}
        .commit-item .time {{
            color: #999;
            font-size: 11px;
            float: right;
        }}
        .image-item {{
            padding: 4px 0;
            font-size: 12px;
            font-family: 'Monaco', 'Menlo', monospace;
        }}
        .image-item .size {{
            color: #999;
            margin-left: 10px;
        }}
        .summary {{
            background: #f8f9fa;
            border-radius: 6px;
            padding: 12px;
            margin: 12px 0;
        }}
        .summary-item {{
            display: inline-block;
            margin-right: 20px;
            font-size: 13px;
        }}
        .summary-item .label {{
            color: #666;
        }}
        .summary-item .value {{
            font-weight: 600;
            color: #333;
        }}
        .footer {{
            margin-top: 20px;
            padding-top: 12px;
            border-top: 1px solid #eee;
            font-size: 11px;
            color: #999;
            text-align: center;
        }}
        @media (max-width: 480px) {{
            body {{ padding: 6px; font-size: 13px; }}
            .header h1 {{ font-size: 16px; }}
            .header .version {{ font-size: 24px; }}
            .section-title {{ font-size: 13px; }}
            .check-item {{ font-size: 12px; }}
            .commit-item {{ font-size: 11px; }}
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🚀 TrendRadar 部署通知</h1>
        <div class="version">v{version}</div>
        <span class="status">{status_text}</span>
        <div class="time">{timestamp}</div>
    </div>

    <div class="summary">
        <span class="summary-item"><span class="label">播客源</span> <span class="value">{podcast_ok}/{podcast_total}</span></span>
        <span class="summary-item"><span class="label">投资源</span> <span class="value">{invest_ok}/{invest_total}</span></span>
        <span class="summary-item"><span class="label">部署路径</span> <span class="value">{PROD_BASE}/releases/v{version}</span></span>
    </div>

    <div class="section">
        <div class="section-title">🎙️ 播客源状态</div>
        {podcast_html}
    </div>

    <div class="section">
        <div class="section-title">📈 投资数据源状态</div>
        {invest_html}
    </div>

    <div class="section">
        <div class="section-title">⚙️ 模块配置状态</div>
        {config_html}
    </div>

    <div class="section">
        <div class="section-title">💾 数据库状态</div>
        {db_html}
    </div>

    <div class="section">
        <div class="section-title">🖥️ 监控服务状态</div>
        {monitor_html}
    </div>

    <div class="section">
        <div class="section-title">📱 Wewe-RSS / 公众号</div>
        {wewe_html}
    </div>

    <div class="section">
        <div class="section-title">⏰ 调度配置</div>
        {schedule_html}
    </div>

    <div class="section">
        <div class="section-title">📊 最近模块运行</div>
        {module_html}
    </div>

    <div class="section">
        <div class="section-title">📝 最近提交</div>
        {commits_html}
    </div>

    <div class="section">
        <div class="section-title">🐳 Docker 镜像</div>
        {images_html}
    </div>

    <div class="footer">
        TrendRadar 自动部署系统 · {timestamp}
    </div>
</body>
</html>"""

    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"🚀 TrendRadar v{version} 部署{'成功' if all_ok else '完成（部分异常）'}"
        msg['From'] = EMAIL_FROM
        msg['To'] = EMAIL_TO
        msg.attach(MIMEText(html, 'html', 'utf-8'))
        
        server = smtplib.SMTP_SSL(EMAIL_SMTP, EMAIL_PORT)
        server.login(EMAIL_FROM, EMAIL_PASSWORD)
        server.sendmail(EMAIL_FROM, [EMAIL_TO], msg.as_string())
        server.quit()
        
        print(f"✅ 部署通知邮件已发送至 {EMAIL_TO}")
        return True
    except Exception as e:
        print(f"❌ 邮件发送失败: {e}")
        return False


def main():
    version = sys.argv[1] if len(sys.argv) > 1 else get_version()
    print(f"📧 发送部署通知邮件 (v{version})...")
    send_notification(version)


if __name__ == "__main__":
    main()
