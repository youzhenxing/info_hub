#!/usr/bin/env python3
# coding=utf-8
"""
4个模块真实端到端测试脚本

测试以下模块的邮件渲染和发送：
1. 播客模块（仅转录1个）
2. 投资模块
3. 社区模块
4. 监控日志

使用真实数据和新的EmailRenderer模板系统
"""

import os
import sys
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

# 添加项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 加载环境变量
def load_env():
    """加载环境变量"""
    env_files = [
        PROJECT_ROOT / "agents" / ".env",
        PROJECT_ROOT / "docker" / ".env",
        PROJECT_ROOT / ".env",
    ]
    for env_file in env_files:
        if env_file.exists():
            print(f"📄 加载环境变量: {env_file}")
            with open(env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        if key not in os.environ:
                            os.environ[key] = value

load_env()

# 导入EmailRenderer
from shared.lib.email_renderer import EmailRenderer
from trendradar.notification.senders import send_to_email


def test_podcast_module():
    """测试播客模块（仅处理1个）"""
    print("\n" + "="*60)
    print("🎙️ 测试播客模块")
    print("="*60)

    try:
        from trendradar.podcast.fetcher import PodcastFetcher
        from trendradar.podcast.transcriber import ASRTranscriber
        from trendradar.podcast.analyzer import PodcastAnalyzer

        # 配置
        config = {
            "PODCAST": {
                "feeds": [
                    {
                        "name": "硅谷101",
                        "url": "https://feeds.buzzsprout.com/1930654.rss",
                        "enabled": True,
                        "language": "zh"
                    }
                ]
            },
            "AI": {
                "api_key": os.environ.get("AI_API_KEY", ""),
                "base_url": os.environ.get("AI_BASE_URL", "https://api.deepseek.com/v1"),
                "model": os.environ.get("AI_MODEL", "deepseek-chat"),
                "asr_model": os.environ.get("AI_ASR_MODEL", "deepseek-audio")
            }
        }

        fetcher = PodcastFetcher(config["PODCAST"]["feeds"])
        transcriber = ASRTranscriber(config["AI"])
        analyzer = PodcastAnalyzer(config["AI"])

        # 获取最新一期
        print("📡 获取播客源...")
        episodes = fetcher.fetch_latest(count=1)

        if not episodes:
            print("❌ 未获取到播客节目")
            return None

        episode = episodes[0]
        print(f"✅ 获取到节目: {episode.title}")

        # 转写
        print("🎙️ 开始转写...")
        transcript = transcriber.transcribe(episode.audio_url)
        if not transcript:
            print("⚠️ 转写失败，使用空文本")
            transcript = ""
        else:
            print(f"✅ 转写完成，长度: {len(transcript)} 字符")

        # AI分析
        print("🤖 AI分析中...")
        analysis = analyzer.analyze(
            episode=episode,
            transcript=transcript
        )
        print(f"✅ 分析完成")

        # 使用EmailRenderer渲染
        renderer = EmailRenderer()

        # 准备模板数据
        template_data = {
            "episode": {
                "feed_name": episode.feed_name,
                "title": episode.title,
                "author": episode.author or "",
                "published_at": episode.published_at or "",
                "duration": episode.duration or "",
                "url": episode.url or "",
                "audio_url": episode.audio_url or "",
                "summary": episode.summary or ""
            },
            "transcript": transcript[:500] + "..." if len(transcript) > 500 else transcript,
            "analysis": analysis,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        # 渲染模板
        html = renderer.render_module_email(
            module="podcast",
            template_name="episode_update.html",
            context=template_data
        )

        # 保存HTML
        output_dir = PROJECT_ROOT / "agents" / "e2e_output"
        output_dir.mkdir(parents=True, exist_ok=True)
        html_file = output_dir / "podcast_real.html"
        html_file.write_text(html, encoding="utf-8")
        print(f"💾 HTML已保存: {html_file}")

        # 发送邮件
        from_email = os.environ.get("EMAIL_FROM", "")
        password = os.environ.get("EMAIL_PASSWORD", "")
        to_email = os.environ.get("EMAIL_TO", "")

        if all([from_email, password, to_email]):
            print("📧 发送邮件...")
            success = send_to_email(
                from_email=from_email,
                password=password,
                to_email=to_email,
                report_type=f"🎙️ 播客测试: {episode.title}",
                html_file_path=str(html_file)
            )
            if success:
                print("✅ 播客邮件发送成功")
            else:
                print("❌ 播客邮件发送失败")
        else:
            print("⚠️ 邮件配置不完整，跳过发送")

        return {
            "success": True,
            "episode": episode.title,
            "html_file": str(html_file)
        }

    except Exception as e:
        print(f"❌ 播客模块测试失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_investment_module():
    """测试投资模块"""
    print("\n" + "="*60)
    print("📈 测试投资模块")
    print("="*60)

    try:
        from trendradar.investment.collector import InvestmentCollector
        from trendradar.investment.analyzer import InvestmentAnalyzer

        # 配置
        config = {
            "INVESTMENT": {
                "indices": ["000001", "399001", "000300"],
                "stocks": [
                    {"symbol": "600519", "name": "贵州茅台"},
                    {"symbol": "000858", "name": "五粮液"}
                ],
                "crypto": ["bitcoin", "ethereum"]
            },
            "AI": {
                "api_key": os.environ.get("AI_API_KEY", ""),
                "base_url": os.environ.get("AI_BASE_URL", "https://api.deepseek.com/v1"),
                "model": os.environ.get("AI_MODEL", "deepseek-chat")
            }
        }

        collector = InvestmentCollector(config["INVESTMENT"])
        analyzer = InvestmentAnalyzer(config["AI"])

        # 收集数据
        print("📊 收集投资数据...")
        data = collector.collect()
        print(f"✅ 数据收集完成")

        # AI分析
        print("🤖 AI分析中...")
        analysis = analyzer.analyze(data)
        print(f"✅ 分析完成")

        # 使用EmailRenderer渲染
        renderer = EmailRenderer()

        # 准备模板数据
        template_data = {
            "date": data.date,
            "timestamp": data.timestamp,
            "market_snapshot": data.market_snapshot,
            "news": data.news[:15] if data.news else [],
            "analysis": {
                "success": analysis.success,
                "content": analysis.content
            }
        }

        # 渲染模板
        html = renderer.render_module_email(
            module="investment",
            template_name="daily_report.html",
            context=template_data
        )

        # 保存HTML
        output_dir = PROJECT_ROOT / "agents" / "e2e_output"
        output_dir.mkdir(parents=True, exist_ok=True)
        html_file = output_dir / "investment_real.html"
        html_file.write_text(html, encoding="utf-8")
        print(f"💾 HTML已保存: {html_file}")

        # 发送邮件
        from_email = os.environ.get("EMAIL_FROM", "")
        password = os.environ.get("EMAIL_PASSWORD", "")
        to_email = os.environ.get("EMAIL_TO", "")

        if all([from_email, password, to_email]):
            print("📧 发送邮件...")
            success = send_to_email(
                from_email=from_email,
                password=password,
                to_email=to_email,
                report_type=f"📈 投资简报测试 - {data.date}",
                html_file_path=str(html_file)
            )
            if success:
                print("✅ 投资邮件发送成功")
            else:
                print("❌ 投资邮件发送失败")
        else:
            print("⚠️ 邮件配置不完整，跳过发送")

        return {
            "success": True,
            "date": data.date,
            "html_file": str(html_file)
        }

    except Exception as e:
        print(f"❌ 投资模块测试失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_community_module():
    """测试社区模块"""
    print("\n" + "="*60)
    print("🌐 测试社区模块")
    print("="*60)

    try:
        from trendradar.community.collector import CommunityCollector
        from trendradar.community.analyzer import CommunityAnalyzer

        # 配置
        config = {
            "COMMUNITY": {
                "sources": {
                    "hackernews": {
                        "enabled": True,
                        "url": "https://hacker-news.firebaseio.com/v0"
                    }
                }
            },
            "AI": {
                "api_key": os.environ.get("AI_API_KEY", ""),
                "base_url": os.environ.get("AI_BASE_URL", "https://api.deepseek.com/v1"),
                "model": os.environ.get("AI_MODEL", "deepseek-chat")
            }
        }

        collector = CommunityCollector(config["COMMUNITY"]["sources"])
        analyzer = CommunityAnalyzer(config["AI"])

        # 收集数据
        print("📡 收集社区热点...")
        data = collector.collect()
        print(f"✅ 数据收集完成")

        # AI分析
        print("🤖 AI分析中...")
        analysis = analyzer.analyze(data)
        print(f"✅ 分析完成")

        # 使用EmailRenderer渲染
        renderer = EmailRenderer()

        # 准备模板数据
        sources = []
        for source_type, source_data in data.sources.items():
            source_config = {
                "source_type": source_type,
                "name": source_data.source_name,
                "icon": "📰" if source_type == "hackernews" else "💻",
                "color": "#FF6600" if source_type == "hackernews" else "#333333",
                "entries": []
            }

            # SourceData.items 是一个列表
            for entry in source_data.items[:10]:  # 限制10条
                source_config["entries"].append({
                    "title": entry.get("title", ""),
                    "url": entry.get("url", ""),
                    "score": entry.get("score", 0),
                    "comments": entry.get("comments", 0),
                    "published_at": entry.get("time", ""),
                    "author": entry.get("by", ""),
                    "ai_summary": entry.get("ai_summary", "")
                })

            sources.append(source_config)

        template_data = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "sources": sources,
            "analysis": analysis
        }

        # 渲染模板
        html = renderer.render_module_email(
            module="community",
            template_name="daily_report.html",
            context=template_data
        )

        # 保存HTML
        output_dir = PROJECT_ROOT / "agents" / "e2e_output"
        output_dir.mkdir(parents=True, exist_ok=True)
        html_file = output_dir / "community_real.html"
        html_file.write_text(html, encoding="utf-8")
        print(f"💾 HTML已保存: {html_file}")

        # 发送邮件
        from_email = os.environ.get("EMAIL_FROM", "")
        password = os.environ.get("EMAIL_PASSWORD", "")
        to_email = os.environ.get("EMAIL_TO", "")

        if all([from_email, password, to_email]):
            print("📧 发送邮件...")
            success = send_to_email(
                from_email=from_email,
                password=password,
                to_email=to_email,
                report_type=f"🌐 社区热点测试 - {datetime.now().strftime('%Y-%m-%d')}",
                html_file_path=str(html_file)
            )
            if success:
                print("✅ 社区邮件发送成功")
            else:
                print("❌ 社区邮件发送失败")
        else:
            print("⚠️ 邮件配置不完整，跳过发送")

        return {
            "success": True,
            "html_file": str(html_file)
        }

    except Exception as e:
        print(f"❌ 社区模块测试失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_monitor_module():
    """测试监控日志模块"""
    print("\n" + "="*60)
    print("📋 测试监控日志模块")
    print("="*60)

    try:
        # 获取真实数据
        import subprocess
        import sqlite3
        import json

        # Git提交
        try:
            result = subprocess.run(
                ["git", "-C", str(PROJECT_ROOT), "log", "-5", "--pretty=format:%h|%s|%cr"],
                capture_output=True, text=True, timeout=10
            )
            commits = []
            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    parts = line.split('|', 2)
                    if len(parts) == 3:
                        commits.append({
                            "hash": parts[0],
                            "message": parts[1],
                            "time": parts[2]
                        })
        except:
            commits = []

        # 模块运行状态
        module_runs = []
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
                        ORDER BY started_at DESC
                        LIMIT 10
                    """)
                    for row in cursor.fetchall():
                        module_runs.append({
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

        # 使用EmailRenderer渲染
        renderer = EmailRenderer()

        # 读取调度配置
        import yaml
        schedule_config = {}  # 改为字典
        config_path = PROJECT_ROOT / "config" / "system.yaml"
        if not config_path.exists():
            config_path = Path("/home/zxy/Documents/install/trendradar/shared/config/system.yaml")

        if config_path.exists():
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
                schedule = config.get("schedule", {})

                for module_name, module_config in schedule.items():
                    if module_name == "health_check":
                        schedule_config[module_name] = {
                            "cron": f"每 {module_config.get('interval_minutes', 30)} 分钟",
                            "description": "系统健康检查",
                            "enabled": module_config.get("enabled", True)
                        }
                    else:
                        stype = module_config.get("type", "interval")
                        if stype == "interval":
                            cron = f"每 {module_config.get('interval_hours', 2)} 小时"
                        else:
                            times = module_config.get("times", [])
                            cron = ", ".join(times) if times else "未配置"

                        schedule_config[module_name] = {
                            "cron": cron,
                            "description": f"{module_name} 数据采集",
                            "enabled": module_config.get("enabled", True)
                        }

                # 添加模块图标和名称映射
                module_icons = {
                    "podcast": "🎙️",
                    "investment": "📈",
                    "community": "🌐",
                    "wechat": "📱",
                    "health_check": "🔍"
                }

                module_names = {
                    "podcast": "播客模块",
                    "investment": "投资模块",
                    "community": "社区模块",
                    "wechat": "公众号模块",
                    "health_check": "健康检查"
                }

                template_data["module_icons"] = module_icons
                template_data["module_names"] = module_names

        # 准备模板数据
        template_data = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "service_status": {
                "dev": {"running": False, "port": 8088},
                "prod": {"running": False, "port": 8089}
            },
            "module_runs": module_runs,
            "schedule_config": schedule_config,
            "git_commits": commits
        }

        # 渲染模板
        html = renderer.render_module_email(
            module="monitor",
            template_name="daily_log.html",
            context=template_data
        )

        # 保存HTML
        output_dir = PROJECT_ROOT / "agents" / "e2e_output"
        output_dir.mkdir(parents=True, exist_ok=True)
        html_file = output_dir / "monitor_real.html"
        html_file.write_text(html, encoding="utf-8")
        print(f"💾 HTML已保存: {html_file}")

        # 发送邮件
        from_email = os.environ.get("EMAIL_FROM", "")
        password = os.environ.get("EMAIL_PASSWORD", "")
        to_email = os.environ.get("EMAIL_TO", "")

        if all([from_email, password, to_email]):
            print("📧 发送邮件...")
            success = send_to_email(
                from_email=from_email,
                password=password,
                to_email=to_email,
                report_type=f"📋 监控日志测试 - {datetime.now().strftime('%Y-%m-%d')}",
                html_file_path=str(html_file)
            )
            if success:
                print("✅ 监控邮件发送成功")
            else:
                print("❌ 监控邮件发送失败")
        else:
            print("⚠️ 邮件配置不完整，跳过发送")

        return {
            "success": True,
            "html_file": str(html_file)
        }

    except Exception as e:
        print(f"❌ 监控模块测试失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    """主函数"""
    print("="*60)
    print("🚀 TrendRadar 4模块端到端测试")
    print("="*60)
    print(f"⏰ 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    results = {}

    # 测试播客模块
    results["podcast"] = test_podcast_module()

    # 测试投资模块
    results["investment"] = test_investment_module()

    # 测试社区模块
    results["community"] = test_community_module()

    # 测试监控模块
    results["monitor"] = test_monitor_module()

    # 汇总结果
    print("\n" + "="*60)
    print("📊 测试结果汇总")
    print("="*60)

    for module, result in results.items():
        if result and result.get("success"):
            print(f"✅ {module.upper()}: 成功")
        else:
            print(f"❌ {module.upper()}: 失败")

    print(f"\n⏰ 结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📁 输出目录: {PROJECT_ROOT / 'agents' / 'e2e_output'}")


if __name__ == "__main__":
    main()
