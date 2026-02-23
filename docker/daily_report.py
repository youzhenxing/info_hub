#!/usr/bin/env python3
# coding=utf-8
"""
每日任务日志报告

每天 23:00 自动发送当天的任务执行情况汇总
"""

import sys
import os
import re
import logging
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, '/app')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def get_container_logs():
    """获取容器日志"""
    import subprocess
    
    # 获取今天的日期
    today = datetime.now().strftime("%Y-%m-%d")
    
    try:
        # 从 /proc/1/fd/1 读取容器输出（如果可用）
        # 或者从环境中获取日志
        result = subprocess.run(
            ["journalctl", "--since", "today", "-u", "docker", "--no-pager"],
            capture_output=True, text=True, timeout=30
        )
        return result.stdout
    except:
        pass
    
    # 备选方案：读取 supercronic 输出
    try:
        # 尝试读取日志文件
        log_paths = [
            "/var/log/trendradar.log",
            "/app/output/logs/trendradar.log",
        ]
        for path in log_paths:
            if os.path.exists(path):
                with open(path, 'r') as f:
                    return f.read()
    except:
        pass
    
    return ""


def parse_task_results(logs: str) -> dict:
    """解析任务执行结果"""
    today = datetime.now().strftime("%Y-%m-%d")
    
    results = {
        "date": today,
        "investment": {
            "total": 0,
            "success": 0,
            "failed": 0,
            "times": [],
            "errors": []
        },
        "podcast": {
            "total": 0,
            "success": 0,
            "failed": 0,
            "processed": 0,
            "errors": []
        },
        "main_program": {
            "total": 0,
            "success": 0,
            "failed": 0,
            "errors": []
        }
    }
    
    # 分析投资模块
    inv_success = len(re.findall(r'投资报告推送成功', logs))
    inv_failed = len(re.findall(r'投资报告推送失败|投资模块运行失败', logs))
    results["investment"]["success"] = inv_success
    results["investment"]["failed"] = inv_failed
    results["investment"]["total"] = inv_success + inv_failed
    
    # 提取投资模块执行时间
    inv_times = re.findall(r'(\d{2}:\d{2}:\d{2}).*投资模块定时任务启动', logs)
    results["investment"]["times"] = inv_times
    
    # 提取投资模块错误
    inv_errors = re.findall(r'投资.*失败[：:]\s*(.+)', logs)
    results["investment"]["errors"] = inv_errors[:5]  # 最多5条
    
    # 分析播客模块
    podcast_processed = len(re.findall(r'播客处理完成|podcast.*processed', logs, re.I))
    podcast_errors = re.findall(r'播客.*失败|podcast.*error|podcast.*failed', logs, re.I)
    results["podcast"]["processed"] = podcast_processed
    results["podcast"]["errors"] = podcast_errors[:5]
    
    # 分析主程序
    main_success = len(re.findall(r'trendradar.*完成|execution completed', logs, re.I))
    main_errors = re.findall(r'error running command.*trendradar', logs, re.I)
    results["main_program"]["success"] = main_success
    results["main_program"]["failed"] = len(main_errors)
    results["main_program"]["total"] = main_success + len(main_errors)
    results["main_program"]["errors"] = main_errors[:5]
    
    return results


def check_output_files() -> dict:
    """检查今日输出文件"""
    today = datetime.now().strftime("%Y%m%d")
    output_dir = Path("/app/output")
    
    files = {
        "investment_emails": [],
        "news_db": None,
        "podcast_db": None,
        "html_reports": []
    }
    
    # 检查投资邮件
    email_dir = output_dir / "investment" / "email"
    if email_dir.exists():
        for f in email_dir.glob(f"*{today}*.html"):
            files["investment_emails"].append({
                "name": f.name,
                "size": f.stat().st_size,
                "time": datetime.fromtimestamp(f.stat().st_mtime).strftime("%H:%M:%S")
            })
    
    # 检查新闻数据库
    news_db = output_dir / "news" / f"{datetime.now().strftime('%Y-%m-%d')}.db"
    if news_db.exists():
        files["news_db"] = {
            "size": news_db.stat().st_size,
            "time": datetime.fromtimestamp(news_db.stat().st_mtime).strftime("%H:%M:%S")
        }
    
    # 检查播客数据库
    podcast_db = output_dir / "news" / "podcast.db"
    if podcast_db.exists():
        files["podcast_db"] = {
            "size": podcast_db.stat().st_size,
            "time": datetime.fromtimestamp(podcast_db.stat().st_mtime).strftime("%H:%M:%S")
        }
    
    return files


def generate_report(results: dict, files: dict) -> str:
    """生成报告内容"""
    today = datetime.now().strftime("%Y-%m-%d")
    now = datetime.now().strftime("%H:%M:%S")
    
    # 计算总体状态
    total_errors = (
        results["investment"]["failed"] + 
        len(results["podcast"]["errors"]) + 
        results["main_program"]["failed"]
    )
    
    if total_errors == 0:
        status = "✅ 全部正常"
        status_color = "#43a047"
    elif total_errors <= 2:
        status = "⚠️ 部分异常"
        status_color = "#ff9800"
    else:
        status = "❌ 存在问题"
        status_color = "#e53935"
    
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TrendRadar 每日任务日志 - {today}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 100%;
            margin: 0;
            padding: 8px;
            background: #fff;
            font-size: 14px;
        }}
        .header {{
            border-bottom: 3px solid {status_color};
            padding-bottom: 10px;
            margin-bottom: 15px;
        }}
        .header h1 {{
            font-size: 18px;
            margin: 0 0 5px 0;
        }}
        .status {{
            font-size: 16px;
            font-weight: bold;
            color: {status_color};
        }}
        .section {{
            margin: 15px 0;
            padding: 10px;
            background: #f8f9fa;
            border-radius: 6px;
        }}
        .section-title {{
            font-size: 14px;
            font-weight: 600;
            margin-bottom: 8px;
            color: #1a73e8;
        }}
        .stat {{
            display: inline-block;
            margin-right: 15px;
            font-size: 13px;
        }}
        .stat .num {{
            font-weight: bold;
            font-size: 16px;
        }}
        .success {{ color: #43a047; }}
        .failed {{ color: #e53935; }}
        .warn {{ color: #ff9800; }}
        .error-list {{
            font-size: 12px;
            color: #666;
            margin-top: 8px;
            padding-left: 15px;
        }}
        .file-list {{
            font-size: 12px;
            color: #666;
        }}
        .file-item {{
            padding: 3px 0;
        }}
        .footer {{
            margin-top: 20px;
            padding-top: 10px;
            border-top: 1px solid #eee;
            font-size: 11px;
            color: #999;
            text-align: center;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>📊 TrendRadar 每日任务日志</h1>
        <div>日期：{today} | 生成时间：{now}</div>
        <div class="status">{status}</div>
    </div>

    <div class="section">
        <div class="section-title">📈 投资模块</div>
        <div class="stat">执行次数：<span class="num">{results['investment']['total']}</span></div>
        <div class="stat">成功：<span class="num success">{results['investment']['success']}</span></div>
        <div class="stat">失败：<span class="num {'failed' if results['investment']['failed'] > 0 else ''}">{results['investment']['failed']}</span></div>
"""
    
    if results['investment']['errors']:
        html += '<div class="error-list">错误信息：<ul>'
        for err in results['investment']['errors']:
            html += f'<li>{err}</li>'
        html += '</ul></div>'
    
    html += """
    </div>

    <div class="section">
        <div class="section-title">🎙️ 播客模块</div>
"""
    html += f'<div class="stat">处理数量：<span class="num">{results["podcast"]["processed"]}</span></div>'
    
    if results['podcast']['errors']:
        html += '<div class="error-list">错误信息：<ul>'
        for err in results['podcast']['errors'][:3]:
            html += f'<li>{err}</li>'
        html += '</ul></div>'
    
    html += """
    </div>

    <div class="section">
        <div class="section-title">📁 今日输出文件</div>
        <div class="file-list">
"""
    
    # 投资邮件
    if files['investment_emails']:
        html += f'<div class="file-item">📧 投资邮件：{len(files["investment_emails"])} 封</div>'
        for f in files['investment_emails']:
            html += f'<div class="file-item" style="padding-left: 15px;">- {f["name"]} ({f["time"]})</div>'
    else:
        html += '<div class="file-item warn">📧 投资邮件：无</div>'
    
    # 新闻数据库
    if files['news_db']:
        html += f'<div class="file-item">📰 新闻数据库：{files["news_db"]["size"]//1024}KB (更新于 {files["news_db"]["time"]})</div>'
    
    # 播客数据库
    if files['podcast_db']:
        html += f'<div class="file-item">🎙️ 播客数据库：{files["podcast_db"]["size"]//1024}KB (更新于 {files["podcast_db"]["time"]})</div>'
    
    html += f"""
        </div>
    </div>

    <div class="section">
        <div class="section-title">⏰ 定时任务配置</div>
        <div class="file-list">
            <div class="file-item">主程序：每 2 小时</div>
            <div class="file-item">投资模块：06:00 / 11:30 / 23:30</div>
            <div class="file-item">日志报告：23:00</div>
        </div>
    </div>

    <div class="footer">
        由 TrendRadar 自动生成 | {today} {now}
    </div>
</body>
</html>"""
    
    return html


def send_report(html_content: str):
    """发送报告邮件"""
    from trendradar.core import load_config
    from trendradar.notification import send_to_email
    
    today = datetime.now().strftime("%Y-%m-%d")
    
    # 加载配置
    config = load_config()
    
    # 保存 HTML 文件
    output_dir = Path("/app/output/logs")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    html_file = output_dir / f"daily_report_{today.replace('-', '')}.html"
    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    # 获取邮件配置
    email_from = config.get("EMAIL_FROM") or os.environ.get("EMAIL_FROM")
    email_password = config.get("EMAIL_PASSWORD") or os.environ.get("EMAIL_PASSWORD")
    email_to = config.get("EMAIL_TO") or os.environ.get("EMAIL_TO")
    smtp_server = config.get("EMAIL_SMTP_SERVER") or os.environ.get("EMAIL_SMTP_SERVER")
    smtp_port = config.get("EMAIL_SMTP_PORT") or os.environ.get("EMAIL_SMTP_PORT")
    
    if email_from and email_password and email_to:
        success = send_to_email(
            from_email=email_from,
            password=email_password,
            to_email=email_to,
            report_type=f"每日任务日志 - {today}",
            html_file_path=str(html_file),
            custom_smtp_server=smtp_server,
            custom_smtp_port=int(smtp_port) if smtp_port else None,
        )
        if success:
            logger.info(f"✅ 每日日志报告已发送至 {email_to}")
        else:
            logger.error(f"❌ 每日日志报告发送失败")
    else:
        logger.error("❌ 邮件配置缺失，无法发送报告")


def main():
    """主函数"""
    logger.info("=" * 50)
    logger.info("生成每日任务日志报告")
    logger.info("=" * 50)
    
    try:
        # 获取日志
        logs = get_container_logs()
        
        # 解析结果
        results = parse_task_results(logs)
        
        # 检查输出文件
        files = check_output_files()
        
        # 生成报告
        html = generate_report(results, files)
        
        # 发送报告
        send_report(html)
        
        logger.info("✅ 每日日志报告生成完成")
        
    except Exception as e:
        logger.error(f"❌ 生成日志报告失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
