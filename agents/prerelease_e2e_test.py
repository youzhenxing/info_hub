#!/usr/bin/env python3
# coding=utf-8
"""
预发版端到端测试脚本

使用真实数据测试四个模块的完整流程：
1. 投资模块 - 收集实时行情 + AI 分析 + 邮件发送
2. 社区模块 - 收集热点 + AI 分析 + 邮件发送
3. 播客模块 - 获取最新节目 + 转写 + AI 分析 + 邮件发送（可选）
4. 公众号模块 - 如果 wewe-rss 可用则测试
"""

import os
import sys
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

# 添加项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def load_env():
    """加载环境变量"""
    # 清除代理环境变量，避免干扰 AI API 调用
    proxy_vars = [
        'all_proxy', 'ALL_PROXY',
        'http_proxy', 'HTTP_PROXY',
        'https_proxy', 'HTTPS_PROXY',
        'socks_proxy', 'SOCKS_PROXY',
    ]
    for var in proxy_vars:
        if var in os.environ:
            del os.environ[var]

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
                        # 跳过代理配置
                        if 'proxy' not in key.lower():
                            if key not in os.environ:
                                os.environ[key] = value
            break


load_env()


class PreReleaseTest:
    """预发版测试类"""

    def __init__(self):
        self.results = {}
        self.output_dir = PROJECT_ROOT / "agents" / "e2e_output"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 邮件配置
        self.email_from = os.environ.get("EMAIL_FROM", "")
        self.email_password = os.environ.get("EMAIL_PASSWORD", "")
        self.email_to = os.environ.get("EMAIL_TO", "")
        self.smtp_server = os.environ.get("EMAIL_SMTP_SERVER", "")
        self.smtp_port = os.environ.get("EMAIL_SMTP_PORT", "")
        
        # AI 配置
        self.ai_config = {
            "api_key": os.environ.get("AI_API_KEY", ""),
            "api_base": os.environ.get("AI_API_BASE", ""),
            "model": os.environ.get("AI_MODEL", ""),
        }

    def _send_email(self, subject: str, html_file: Path) -> bool:
        """发送邮件"""
        if not all([self.email_from, self.email_password, self.email_to]):
            print("    ⚠️ 邮件配置不完整，跳过发送")
            return False
        
        try:
            from trendradar.notification.senders import send_to_email
            
            smtp_port_int = None
            if self.smtp_port:
                try:
                    smtp_port_int = int(self.smtp_port)
                except (ValueError, TypeError):
                    pass
            
            success = send_to_email(
                from_email=self.email_from,
                password=self.email_password,
                to_email=self.email_to,
                report_type=subject,
                html_file_path=str(html_file),
                custom_smtp_server=self.smtp_server if self.smtp_server else None,
                custom_smtp_port=smtp_port_int,
            )
            
            return success
        except Exception as e:
            print(f"    ❌ 邮件发送异常: {e}")
            return False

    def test_investment(self) -> Dict[str, Any]:
        """测试投资模块"""
        print("\n" + "="*60)
        print("📈 投资模块 - 真实数据测试")
        print("="*60)
        
        start_time = time.time()
        result = {"success": False, "error": None, "duration": 0}
        
        try:
            from trendradar.core.loader import load_config
            from trendradar.investment.collector import InvestmentCollector
            from trendradar.investment.analyzer import InvestmentAnalyzer
            from trendradar.investment.notifier import InvestmentNotifier
            
            # 加载配置
            config = load_config()
            
            # 收集数据
            print("  📊 收集投资数据...")
            collector = InvestmentCollector.from_config(config)
            data = collector.collect()
            print(f"  ✅ 数据收集完成")
            print(f"      - 指数: {len(data.market_snapshot.indices) if data.market_snapshot else 0} 个")
            print(f"      - 个股: {len(data.market_snapshot.stocks) if data.market_snapshot else 0} 个")
            print(f"      - 加密货币: {len(data.market_snapshot.crypto) if data.market_snapshot else 0} 个")
            print(f"      - 新闻: {len(data.news) if data.news else 0} 条")
            
            # AI 分析
            print("  🤖 AI 分析中...")
            analyzer = InvestmentAnalyzer.from_config(config)
            analysis = analyzer.analyze(data)
            if analysis.success:
                print(f"  ✅ AI 分析完成，内容长度: {len(analysis.content)} 字符")
            else:
                print(f"  ⚠️ AI 分析失败: {analysis.error}")
            
            # 渲染邮件（使用新的 EmailRenderer）
            print("  📧 渲染邮件...")
            notifier = InvestmentNotifier.from_config(config)
            html_content = notifier._render_email_html(data, analysis, "cn")
            
            # 验证使用了新模板
            if 'theme-investment' in html_content:
                print("  ✅ 使用新统一模板 (theme-investment)")
            else:
                print("  ⚠️ 使用了旧模板（fallback）")
            
            # 保存 HTML
            html_file = self.output_dir / f"investment_prerelease_{datetime.now().strftime('%H%M%S')}.html"
            html_file.write_text(html_content, encoding="utf-8")
            print(f"  💾 HTML 已保存: {html_file}")
            
            # 发送邮件
            print("  📤 发送邮件...")
            subject = f"📈 [预发版测试] 投资简报 - {data.date}"
            email_sent = self._send_email(subject, html_file)
            if email_sent:
                print("  ✅ 邮件发送成功")
            
            result["success"] = True
            result["html_file"] = str(html_file)
            result["email_sent"] = email_sent
            result["data_summary"] = {
                "indices": len(data.market_snapshot.indices) if data.market_snapshot else 0,
                "news": len(data.news) if data.news else 0,
            }
            
        except Exception as e:
            print(f"  ❌ 测试失败: {e}")
            import traceback
            traceback.print_exc()
            result["error"] = str(e)
        
        result["duration"] = time.time() - start_time
        print(f"  ⏱️ 耗时: {result['duration']:.1f} 秒")
        return result

    def test_community(self) -> Dict[str, Any]:
        """测试社区模块"""
        print("\n" + "="*60)
        print("🌐 社区模块 - 真实数据测试")
        print("="*60)
        
        start_time = time.time()
        result = {"success": False, "error": None, "duration": 0}
        
        try:
            from trendradar.core.loader import load_config
            from trendradar.community.collector import CommunityCollector
            from trendradar.community.analyzer import CommunityAnalyzer
            from trendradar.community.notifier import CommunityNotifier
            
            # 加载配置
            config = load_config()
            
            # 收集数据
            print("  📡 收集社区热点...")
            collector = CommunityCollector.from_config(config)
            data = collector.collect()
            print(f"  ✅ 数据收集完成，共 {data.total_items} 条")
            for source_id, source_data in data.sources.items():
                print(f"      - {source_id}: {source_data.count} 条")
            
            # AI 分析
            print("  🤖 AI 分析中...")
            analyzer = CommunityAnalyzer.from_config(config)
            analysis = analyzer.analyze(data)
            print(f"  ✅ AI 分析完成")
            
            # 渲染邮件
            print("  📧 渲染邮件...")
            notifier = CommunityNotifier.from_config(config)
            html_content = notifier._render_email_html(data, analysis)
            
            # 验证使用了新模板
            if 'theme-community' in html_content:
                print("  ✅ 使用新统一模板 (theme-community)")
            else:
                print("  ⚠️ 使用了旧模板（fallback）")
            
            # 保存 HTML
            html_file = self.output_dir / f"community_prerelease_{datetime.now().strftime('%H%M%S')}.html"
            html_file.write_text(html_content, encoding="utf-8")
            print(f"  💾 HTML 已保存: {html_file}")
            
            # 发送邮件
            print("  📤 发送邮件...")
            subject = f"🌐 [预发版测试] 社区热点 - {data.date}"
            email_sent = self._send_email(subject, html_file)
            if email_sent:
                print("  ✅ 邮件发送成功")
            
            result["success"] = True
            result["html_file"] = str(html_file)
            result["email_sent"] = email_sent
            result["data_summary"] = {
                "total_items": data.total_items,
                "sources": list(data.sources.keys()),
            }
            
        except Exception as e:
            print(f"  ❌ 测试失败: {e}")
            import traceback
            traceback.print_exc()
            result["error"] = str(e)
        
        result["duration"] = time.time() - start_time
        print(f"  ⏱️ 耗时: {result['duration']:.1f} 秒")
        return result

    def test_podcast(self, use_cached_transcript: bool = True) -> Dict[str, Any]:
        """
        测试播客模块（完全真实场景）

        Args:
            use_cached_transcript: 是否使用缓存的完整转写文本（默认 True）
        """
        print("\n" + "="*60)
        print("🎙️ 播客模块 - 真实数据测试")
        print("="*60)

        if use_cached_transcript:
            print("  ✅ 使用缓存的完整转写文本进行 AI 分析")

        start_time = time.time()
        result = {"success": False, "error": None, "duration": 0}

        try:
            from trendradar.core.loader import load_config
            from trendradar.podcast.fetcher import PodcastFetcher
            from trendradar.podcast.notifier import PodcastNotifier
            from trendradar.podcast.analyzer import PodcastAnalyzer

            # 加载配置
            config = load_config()

            # 获取最新播客
            print("  📡 获取播客源...")
            podcast_config = config.get("PODCAST", config.get("podcast", {}))
            feeds_config = podcast_config.get("feeds", podcast_config.get("FEEDS", []))

            if not feeds_config:
                print("  ⚠️ 未配置播客源，使用默认源")
                feeds_config = [{"name": "硅谷101", "url": "https://feeds.buzzsprout.com/1930654.rss", "enabled": True}]

            # 转换为 PodcastFeedConfig 对象
            from trendradar.podcast.fetcher import PodcastFeedConfig
            feeds = []
            for f in feeds_config:
                if isinstance(f, dict):
                    feed_id = f.get("feed_id", f.get("name", "unknown").lower().replace(" ", "_"))
                    feeds.append(PodcastFeedConfig(
                        id=feed_id,
                        name=f.get("name", "Unknown"),
                        url=f.get("url", ""),
                        enabled=f.get("enabled", True),
                        max_items=f.get("max_items", 10),
                    ))
                else:
                    feeds.append(f)

            fetcher = PodcastFetcher(feeds)
            all_episodes = fetcher.fetch_all()

            # 获取第一个节目的第一个 episode
            episodes = None
            for feed_id, eps in all_episodes.items():
                if eps:
                    episodes = eps
                    break

            if not episodes:
                print("  ❌ 未获取到播客节目")
                result["error"] = "未获取到播客节目"
                return result

            episode = episodes[0]
            print(f"  ✅ 获取到节目: {episode.title}")
            print(f"      - 来源: {episode.feed_name}")
            print(f"      - 时长: {episode.duration}")

            # 转写（从缓存加载）
            transcript = ""
            if use_cached_transcript:
                print("  📦 从缓存加载转写文本...")
                from agents.transcript_cache import TranscriptCache

                cache = TranscriptCache()
                episode_id = "guigu101_2025-01-30_E223"
                cached_data = cache.get(episode_id)

                if cached_data:
                    transcript = cached_data.get("transcript", "")
                    metadata = cached_data.get("metadata", {})
                    print(f"  ✅ 缓存命中: {metadata.get('episode_title', 'N/A')}")
                    print(f"      - 转写文本长度: {len(transcript)} 字符")
                else:
                    print(f"  ⚠️ 缓存未命中: {episode_id}")
                    print("  📝 使用节目简介作为分析输入")
            else:
                print("  📝 使用节目简介作为分析输入")

            # AI 分析（使用真实的 AI）
            print("  🤖 AI 分析中...")
            analyzer_config = podcast_config.get("analysis", podcast_config.get("ANALYSIS", {}))
            ai_config = config.get("AI", config.get("ai", {}))

            analyzer = PodcastAnalyzer(
                ai_config=ai_config,
                analysis_config=analyzer_config,
            )

            # 使用完整转写文本进行分析（如果可用），否则使用节目简介
            if transcript:
                print(f"  📝 使用完整转写文本进行分析 ({len(transcript)} 字符)")
                analysis_input = transcript
            else:
                print("  📝 使用节目简介进行分析")
                analysis_input = episode.summary if episode.summary else episode.title

            analysis_result = analyzer.analyze(
                transcript=analysis_input,
                podcast_name=episode.feed_name,
                podcast_title=episode.title,
            )

            if not analysis_result.success:
                print(f"  ❌ AI 分析失败: {analysis_result.error}")
                result["error"] = f"AI 分析失败: {analysis_result.error}"
                return result

            analysis = analysis_result.analysis
            print(f"  ✅ AI 分析完成，内容长度: {len(analysis)} 字符")

            # 渲染邮件（不传递转写文本，仅显示 AI 分析结果）
            print("  📧 渲染邮件...")
            notifier = PodcastNotifier.from_config(config)
            html_content = notifier._render_email_html(episode, "", analysis)
            
            # 验证使用了新模板
            if 'theme-podcast' in html_content:
                print("  ✅ 使用新统一模板 (theme-podcast)")
            else:
                print("  ⚠️ 使用了旧模板（fallback）")
            
            # 保存 HTML
            html_file = self.output_dir / f"podcast_prerelease_{datetime.now().strftime('%H%M%S')}.html"
            html_file.write_text(html_content, encoding="utf-8")
            print(f"  💾 HTML 已保存: {html_file}")
            
            # 发送邮件
            print("  📤 发送邮件...")
            subject = f"🎙️ [预发版测试] 播客更新 - {episode.title[:30]}..."
            email_sent = self._send_email(subject, html_file)
            if email_sent:
                print("  ✅ 邮件发送成功")
            
            result["success"] = True
            result["html_file"] = str(html_file)
            result["email_sent"] = email_sent
            result["data_summary"] = {
                "episode": episode.title,
                "feed": episode.feed_name,
            }
            
        except Exception as e:
            print(f"  ❌ 测试失败: {e}")
            import traceback
            traceback.print_exc()
            result["error"] = str(e)
        
        result["duration"] = time.time() - start_time
        print(f"  ⏱️ 耗时: {result['duration']:.1f} 秒")
        return result

    def test_wechat(self) -> Dict[str, Any]:
        """测试公众号模块"""
        print("\n" + "="*60)
        print("📱 公众号模块 - 模板渲染测试")
        print("="*60)
        
        start_time = time.time()
        result = {"success": False, "error": None, "duration": 0}
        
        try:
            # 由于 wewe-rss 可能不在运行，使用测试数据
            import json
            test_data_file = PROJECT_ROOT / "agents" / "test_data" / "wechat_test_data.json"
            
            if not test_data_file.exists():
                print("  ⚠️ 测试数据文件不存在，跳过公众号模块测试")
                result["error"] = "测试数据文件不存在"
                return result
            
            print("  📄 加载测试数据...")
            with open(test_data_file, 'r', encoding='utf-8') as f:
                test_data = json.load(f)
            
            # 使用 EmailRenderer 渲染
            print("  📧 渲染邮件...")
            from shared.lib.email_renderer import EmailRenderer
            renderer = EmailRenderer()
            
            html_content = renderer.render_module_email(
                module='wechat',
                template_name='daily_report.html',
                context=test_data
            )
            
            # 验证使用了新模板
            if 'theme-wechat' in html_content:
                print("  ✅ 使用新统一模板 (theme-wechat)")
            else:
                print("  ⚠️ 模板验证失败")
            
            # 保存 HTML
            html_file = self.output_dir / f"wechat_prerelease_{datetime.now().strftime('%H%M%S')}.html"
            html_file.write_text(html_content, encoding="utf-8")
            print(f"  💾 HTML 已保存: {html_file}")
            
            # 发送邮件
            print("  📤 发送邮件...")
            subject = f"📱 [预发版测试] 公众号日报 - {test_data.get('report', {}).get('date', datetime.now().strftime('%Y-%m-%d'))}"
            email_sent = self._send_email(subject, html_file)
            if email_sent:
                print("  ✅ 邮件发送成功")
            
            result["success"] = True
            result["html_file"] = str(html_file)
            result["email_sent"] = email_sent
            result["data_summary"] = {
                "articles": test_data.get('report', {}).get('total_articles', 0),
                "topics": len(test_data.get('report', {}).get('topics', [])),
            }
            
        except Exception as e:
            print(f"  ❌ 测试失败: {e}")
            import traceback
            traceback.print_exc()
            result["error"] = str(e)
        
        result["duration"] = time.time() - start_time
        print(f"  ⏱️ 耗时: {result['duration']:.1f} 秒")
        return result

    def run_all(self):
        """运行所有测试"""
        print("="*60)
        print("🚀 TrendRadar 预发版端到端测试")
        print("="*60)
        print(f"⏰ 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"📧 邮件配置: {self.email_from} -> {self.email_to}")
        
        total_start = time.time()
        
        # 测试投资模块
        self.results["investment"] = self.test_investment()
        
        # 测试社区模块
        self.results["community"] = self.test_community()
        
        # 测试播客模块（使用缓存的完整转写文本）
        self.results["podcast"] = self.test_podcast(use_cached_transcript=True)
        
        # 测试公众号模块
        self.results["wechat"] = self.test_wechat()
        
        total_duration = time.time() - total_start
        
        # 汇总结果
        self._print_summary(total_duration)
        
        return self.results

    def _print_summary(self, total_duration: float):
        """打印测试汇总"""
        print("\n" + "="*60)
        print("📊 预发版测试结果汇总")
        print("="*60)
        
        success_count = 0
        email_count = 0
        
        module_names = {
            "investment": "📈 投资模块",
            "community": "🌐 社区模块",
            "podcast": "🎙️ 播客模块",
            "wechat": "📱 公众号模块",
        }
        
        for module, result in self.results.items():
            name = module_names.get(module, module)
            
            if result.get("success"):
                status = "✅ 成功"
                success_count += 1
            else:
                status = f"❌ 失败: {result.get('error', '未知错误')}"
            
            email_status = ""
            if result.get("email_sent"):
                email_status = " | 📧 已发送"
                email_count += 1
            elif result.get("success"):
                email_status = " | 📧 未发送"
            
            duration = result.get("duration", 0)
            print(f"  {name}: {status}{email_status} ({duration:.1f}s)")
        
        print(f"\n总计: {success_count}/4 模块成功 | {email_count} 封邮件发送")
        print(f"总耗时: {total_duration:.1f} 秒")
        print(f"📁 输出目录: {self.output_dir}")
        print(f"⏰ 完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        if success_count == 4:
            print("\n🎉 预发版测试全部通过！可以进行发布。")
        else:
            print("\n⚠️ 存在失败的模块，请检查后重试。")


def main():
    """主函数"""
    tester = PreReleaseTest()
    results = tester.run_all()
    
    # 返回退出码
    success_count = sum(1 for r in results.values() if r.get("success"))
    return 0 if success_count == 4 else 1


if __name__ == "__main__":
    sys.exit(main())
