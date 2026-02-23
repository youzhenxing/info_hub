#!/usr/bin/env python3
# coding=utf-8
"""
预发版端到端完整测试脚本 (CI/CT Pre-release Test)

模拟正式发版的完整链路测试，不使用缓存：
1. 投资模块 - 完整链路: 收集 → AI 分析 → 邮件渲染 → 发送
2. 播客模块 - 选取真实转写文本 → AI 分析 → 邮件渲染 → 发送
3. 社区模块 - 完整链路: 收集(无缓存) → AI 分析 → 邮件渲染 → 发送
4. 公众号模块 - 从数据库获取真实文章 → AI 分析 → 邮件渲染 → 发送
"""

import os
import sys
import time
import shutil
import sqlite3
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

# 添加项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "wechat"))


# 清除代理环境变量（在任何操作之前，避免影响 AI API 调用）
proxy_vars = [
    'all_proxy', 'ALL_PROXY',
    'http_proxy', 'HTTP_PROXY',
    'https_proxy', 'HTTPS_PROXY',
]
cleared = []
for var in proxy_vars:
    if var in os.environ:
        del os.environ[var]
        cleared.append(var)
if cleared:
    print(f"🔧 已清除代理环境变量: {', '.join(cleared)} (AI API 不需要代理)")


def load_env():
    """加载环境变量"""
    env_files = [
        PROJECT_ROOT / "agents" / ".env",  # 优先加载 agents/.env
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
            break


load_env()


@dataclass
class TestResult:
    """测试结果"""
    module: str
    success: bool
    html_file: Optional[str] = None
    email_sent: bool = False
    error: Optional[str] = None
    duration: float = 0
    details: Dict[str, Any] = None

    def __post_init__(self):
        if self.details is None:
            self.details = {}


class PreReleaseE2ETest:
    """预发版端到端完整测试"""

    def __init__(self, send_email: bool = True):
        """
        初始化测试

        Args:
            send_email: 是否发送邮件
        """
        self.results: List[TestResult] = []
        self.output_dir = PROJECT_ROOT / "agents" / "e2e_output"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.send_email = send_email

        # 时间戳
        self.timestamp = datetime.now().strftime("%H%M%S")

        # 加载配置
        self.config = self._load_config()

        # 邮件配置 - 从 config 中读取（loader 已处理环境变量优先级）
        self.email_from = self.config.get("EMAIL_FROM", "")
        self.email_password = self.config.get("EMAIL_PASSWORD", "")
        self.email_to = self.config.get("EMAIL_TO", "")
        self.smtp_server = self.config.get("EMAIL_SMTP_SERVER", "")
        self.smtp_port = str(self.config.get("EMAIL_SMTP_PORT", ""))

    def _load_config(self) -> Dict:
        """加载项目配置"""
        from trendradar.core.loader import load_config
        return load_config()

    def _send_email(self, subject: str, html_file: Path) -> bool:
        """发送邮件"""
        if not self.send_email:
            print("    ⚠️ 邮件发送已禁用")
            return False

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

    # =========================================================================
    # 投资模块测试
    # =========================================================================
    def test_investment(self) -> TestResult:
        """测试投资模块 - 完整链路"""
        print("\n" + "=" * 60)
        print("📈 投资模块 - 完整端到端测试")
        print("=" * 60)

        start_time = time.time()
        result = TestResult(module="investment", success=False)

        try:
            from trendradar.investment.collector import InvestmentCollector
            from trendradar.investment.analyzer import InvestmentAnalyzer
            from trendradar.investment.notifier import InvestmentNotifier

            # 1. 收集数据（不使用缓存 - 创建新实例）
            print("  📊 [1/4] 收集实时行情数据...")
            collector = InvestmentCollector.from_config(self.config)
            data = collector.collect()

            indices_count = len(data.market_snapshot.indices) if data.market_snapshot else 0
            stocks_count = len(data.market_snapshot.stocks) if data.market_snapshot else 0
            crypto_count = len(data.market_snapshot.crypto) if data.market_snapshot else 0
            news_count = len(data.news) if data.news else 0

            print(f"      ✅ 指数: {indices_count} | 个股: {stocks_count} | 加密货币: {crypto_count} | 新闻: {news_count}")

            # 2. AI 分析
            print("  🤖 [2/4] AI 分析生成投资简报...")
            analyzer = InvestmentAnalyzer.from_config(self.config)
            analysis = analyzer.analyze(data)

            if analysis.success:
                print(f"      ✅ AI 分析完成，内容长度: {len(analysis.content)} 字符")
            else:
                print(f"      ⚠️ AI 分析失败: {analysis.error}")

            # 3. 渲染邮件
            print("  📧 [3/4] 使用 EmailRenderer 渲染邮件...")
            notifier = InvestmentNotifier.from_config(self.config)
            html_content = notifier._render_email_html(data, analysis, "cn")

            # 验证模板
            if 'theme-investment' in html_content:
                print("      ✅ 使用新统一模板 (theme-investment)")
            else:
                print("      ⚠️ 警告: 使用了 fallback 模板")

            # 保存 HTML
            html_file = self.output_dir / f"investment_prerelease_{self.timestamp}.html"
            html_file.write_text(html_content, encoding="utf-8")
            print(f"      💾 HTML 已保存: {html_file.name}")

            # 4. 发送邮件
            print("  📤 [4/4] 发送邮件...")
            email_sent = self._send_email(
                f"📈 [预发版测试] 投资简报 - {data.date}",
                html_file
            )

            result.success = True
            result.html_file = str(html_file)
            result.email_sent = email_sent
            result.details = {
                "indices": indices_count,
                "stocks": stocks_count,
                "crypto": crypto_count,
                "news": news_count,
                "ai_success": analysis.success,
            }

        except Exception as e:
            print(f"  ❌ 测试失败: {e}")
            import traceback
            traceback.print_exc()
            result.error = str(e)

        result.duration = time.time() - start_time
        print(f"  ⏱️ 耗时: {result.duration:.1f} 秒")
        return result

    # =========================================================================
    # 播客模块测试
    # =========================================================================
    def test_podcast(self) -> TestResult:
        """测试播客模块 - 使用真实转写文本"""
        print("\n" + "=" * 60)
        print("🎙️ 播客模块 - 真实转写文本端到端测试")
        print("=" * 60)

        start_time = time.time()
        result = TestResult(module="podcast", success=False)

        try:
            from trendradar.podcast.analyzer import PodcastAnalyzer
            from trendradar.podcast.notifier import PodcastNotifier
            from trendradar.podcast.fetcher import PodcastEpisode

            # 1. 选取真实转写文本
            print("  📄 [1/4] 选取转写文本...")
            transcript_dir = PROJECT_ROOT / "output" / "podcast" / "batch"
            transcript_files = list(transcript_dir.glob("*_transcript.txt"))

            if not transcript_files:
                raise Exception("未找到转写文本文件")

            # 选择最新的一个
            transcript_file = sorted(transcript_files, key=lambda f: f.stat().st_mtime, reverse=True)[0]
            transcript = transcript_file.read_text(encoding="utf-8")

            # 解析文件名提取播客信息
            filename = transcript_file.stem.replace("_transcript", "")
            parts = filename.split("_", 1)
            feed_name = parts[0] if len(parts) > 0 else "未知播客"
            episode_title = parts[1] if len(parts) > 1 else filename

            print(f"      ✅ 选取: {feed_name} - {episode_title[:40]}...")
            print(f"      📏 转写文本长度: {len(transcript)} 字符")

            # 创建模拟 Episode 对象
            episode = PodcastEpisode(
                feed_id=feed_name.lower().replace(" ", "_"),
                feed_name=feed_name,
                title=episode_title,
                url="",
                guid=f"test_{self.timestamp}",
                audio_url="",
                duration="测试",
                published_at=datetime.now().isoformat(),
                summary="预发版端到端测试",
            )

            # 2. AI 分析
            print("  🤖 [2/4] AI 分析转写内容...")
            analyzer = PodcastAnalyzer.from_config(self.config)
            # analyze(transcript, podcast_name, podcast_title, detected_language)
            analysis_result = analyzer.analyze(
                transcript=transcript,
                podcast_name=feed_name,
                podcast_title=episode_title,
                detected_language="zh",
            )

            if analysis_result.success:
                print(f"      ✅ AI 分析完成，内容长度: {len(analysis_result.analysis)} 字符")
                analysis = analysis_result.analysis
            else:
                print(f"      ⚠️ AI 分析失败: {analysis_result.error}，使用 fallback")
                analysis = f"## 转写内容摘要\n\n{transcript[:500]}..."

            # 3. 渲染邮件
            print("  📧 [3/4] 使用 EmailRenderer 渲染邮件...")
            notifier = PodcastNotifier.from_config(self.config)
            html_content = notifier._render_email_html(episode, transcript, analysis)

            # 验证模板
            if 'theme-podcast' in html_content:
                print("      ✅ 使用新统一模板 (theme-podcast)")
            else:
                print("      ⚠️ 警告: 使用了 fallback 模板")

            # 保存 HTML
            html_file = self.output_dir / f"podcast_prerelease_{self.timestamp}.html"
            html_file.write_text(html_content, encoding="utf-8")
            print(f"      💾 HTML 已保存: {html_file.name}")

            # 4. 发送邮件
            print("  📤 [4/4] 发送邮件...")
            email_sent = self._send_email(
                f"🎙️ [预发版测试] {episode_title[:30]}...",
                html_file
            )

            result.success = True
            result.html_file = str(html_file)
            result.email_sent = email_sent
            result.details = {
                "feed": feed_name,
                "episode": episode_title,
                "transcript_length": len(transcript),
                "ai_success": analysis_result.success,
            }

        except Exception as e:
            print(f"  ❌ 测试失败: {e}")
            import traceback
            traceback.print_exc()
            result.error = str(e)

        result.duration = time.time() - start_time
        print(f"  ⏱️ 耗时: {result.duration:.1f} 秒")
        return result

    # =========================================================================
    # 社区模块测试
    # =========================================================================
    def test_community(self) -> TestResult:
        """测试社区模块 - 完整链路（禁用缓存）"""
        print("\n" + "=" * 60)
        print("🌐 社区模块 - 完整端到端测试（无缓存）")
        print("=" * 60)

        start_time = time.time()
        result = TestResult(module="community", success=False)

        try:
            from trendradar.community.collector import CommunityCollector
            from trendradar.community.analyzer import CommunityAnalyzer
            from trendradar.community.notifier import CommunityNotifier

            # 1. 收集数据（不使用缓存）
            print("  📡 [1/4] 收集社区热点（无缓存模式）...")

            # 临时禁用缓存：删除今日缓存目录
            today = datetime.now().strftime("%Y%m%d")
            cache_dir = PROJECT_ROOT / "output" / "community" / "content_cache" / today
            if cache_dir.exists():
                print(f"      🗑️ 清除缓存目录: {cache_dir}")
                shutil.rmtree(cache_dir)

            collector = CommunityCollector.from_config(self.config)
            data = collector.collect()

            print(f"      ✅ 数据收集完成，共 {data.total_items} 条")
            for source_id, source_data in data.sources.items():
                print(f"          - {source_id}: {source_data.count} 条")

            # 2. AI 分析
            print("  🤖 [2/4] AI 分析社区内容...")
            analyzer = CommunityAnalyzer.from_config(self.config)
            analysis = analyzer.analyze(data)

            print(f"      ✅ AI 分析完成")
            if hasattr(analysis, 'overall_summary') and analysis.overall_summary:
                print(f"          摘要长度: {len(analysis.overall_summary)} 字符")

            # 3. 渲染邮件
            print("  📧 [3/4] 使用 EmailRenderer 渲染邮件...")
            notifier = CommunityNotifier.from_config(self.config)
            html_content = notifier._render_email_html(data, analysis)

            # 验证模板
            if 'theme-community' in html_content:
                print("      ✅ 使用新统一模板 (theme-community)")
            else:
                print("      ⚠️ 警告: 使用了 fallback 模板")

            # 保存 HTML
            html_file = self.output_dir / f"community_prerelease_{self.timestamp}.html"
            html_file.write_text(html_content, encoding="utf-8")
            print(f"      💾 HTML 已保存: {html_file.name}")

            # 4. 发送邮件
            print("  📤 [4/4] 发送邮件...")
            email_sent = self._send_email(
                f"🌐 [预发版测试] 社区热点 - {data.date}",
                html_file
            )

            result.success = True
            result.html_file = str(html_file)
            result.email_sent = email_sent
            result.details = {
                "total_items": data.total_items,
                "sources": list(data.sources.keys()),
            }

        except Exception as e:
            print(f"  ❌ 测试失败: {e}")
            import traceback
            traceback.print_exc()
            result.error = str(e)

        result.duration = time.time() - start_time
        print(f"  ⏱️ 耗时: {result.duration:.1f} 秒")
        return result

    # =========================================================================
    # 公众号模块测试
    # =========================================================================
    def test_wechat(self, article_count: int = 3) -> TestResult:
        """测试公众号模块 - 从数据库获取真实文章"""
        print("\n" + "=" * 60)
        print(f"📱 公众号模块 - 真实文章端到端测试（{article_count} 篇）")
        print("=" * 60)

        start_time = time.time()
        result = TestResult(module="wechat", success=False)

        try:
            # 1. 从数据库获取真实文章
            print("  📄 [1/4] 从数据库获取文章...")
            db_path = PROJECT_ROOT / "wechat" / "data" / "wewe-rss" / "wewe-rss.db"

            if not db_path.exists():
                raise Exception(f"数据库不存在: {db_path}")

            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # 获取最近的文章（wewe-rss 数据库结构）
            cursor.execute("""
                SELECT
                    a.id, a.title, a.pic_url, a.publish_time,
                    f.mp_name as feed_name
                FROM articles a
                LEFT JOIN feeds f ON a.mp_id = f.id
                ORDER BY a.publish_time DESC
                LIMIT ?
            """, (article_count,))

            rows = cursor.fetchall()
            conn.close()

            if not rows:
                raise Exception("数据库中没有可用的文章")

            print(f"      ✅ 获取到 {len(rows)} 篇文章:")

            articles = []
            for row in rows:
                # wewe-rss 数据库结构
                publish_time = row["publish_time"]
                # 转换 Unix 时间戳为 ISO 格式
                if isinstance(publish_time, int):
                    publish_time = datetime.fromtimestamp(publish_time).isoformat()

                articles.append({
                    "id": row["id"],
                    "title": row["title"],
                    "link": f"https://mp.weixin.qq.com/s/{row['id']}",  # 构造链接
                    "content": f"文章：{row['title']}",  # wewe-rss 不存储正文内容
                    "published_at": publish_time,
                    "feed_name": row["feed_name"] or "未知公众号",
                })
                print(f"          - [{row['feed_name']}] {row['title'][:30]}...")

            # 2. AI 分析（使用 wechat 模块的分析器）
            print("  🤖 [2/4] AI 分析文章内容...")

            # 构建测试数据
            from wechat.src.models import DailyReport, Topic, Article as WechatArticle, FeedType

            # 创建文章对象
            wechat_articles = []
            for a in articles:
                pub_at = None
                if a["published_at"]:
                    try:
                        pub_at = datetime.fromisoformat(a["published_at"])
                    except:
                        pub_at = datetime.now()

                wechat_articles.append(WechatArticle(
                    id=a["id"],
                    feed_id="test",
                    feed_name=a["feed_name"],
                    feed_type=FeedType.NORMAL,
                    title=a["title"],
                    url=a["link"],
                    content=a["content"],
                    published_at=pub_at,
                ))

            # 调用 AI 分析（生成话题聚合）
            try:
                # 直接使用 AIClient
                from trendradar.ai.client import AIClient

                # 调试：检查 config 内容
                print(f"      [调试] self.config 键: {list(self.config.keys())[:20]}")
                print(f"      [调试] AI 相关键: {[k for k in self.config.keys() if 'AI' in k.upper()]}")

                ai_config_dict_full = self.config.get("AI", self.config.get("ai", {}))
                print(f"      [调试] self.config['AI'] 类型: {type(ai_config_dict_full)}")
                print(f"      [调试] self.config['AI'] 键: {list(ai_config_dict_full.keys()) if isinstance(ai_config_dict_full, dict) else 'N/A'}")
                print(f"      [调试] self.config['AI'] 内容: {ai_config_dict_full}")

                ai_config_dict = ai_config_dict_full

                # 调试信息
                print(f"      [调试] AI 配置:")
                print(f"        MODEL: {ai_config_dict.get('MODEL')}")
                print(f"        API_KEY: {ai_config_dict.get('API_KEY', '')[:20] if ai_config_dict.get('API_KEY') else '(空)'}...")
                print(f"        API_BASE: {ai_config_dict.get('API_BASE')}")

                ai_client = AIClient(ai_config_dict)

                # 再次调试
                print(f"      [调试] AIClient 实例:")
                print(f"        model: {ai_client.model}")
                print(f"        api_key: {ai_client.api_key[:20] if ai_client.api_key else '(空)'}...")
                print(f"        api_base: {ai_client.api_base}")

                # 手动调用 AI 分析
                # 为每篇文章生成摘要
                for article in wechat_articles:
                    try:
                        prompt = f"""请对以下文章标题生成一个简洁的摘要（50字以内）：

标题：{article.title}

要求：突出文章的核心主题和关键信息。"""
                        article.ai_summary = ai_client.chat([{"role": "user", "content": prompt}])
                        print(f"        - {article.title[:30]}... ✅")
                    except Exception as e:
                        print(f"        - {article.title[:30]}... ⚠️ ({e})")
                        article.ai_summary = f"《{article.title}》的深度分析"

                # 话题聚合分析
                articles_text = "\n\n".join([
                    f"【文章{i+1}】\n来源：{a.feed_name}\n标题：{a.title}\n摘要：{a.ai_summary}"
                    for i, a in enumerate(wechat_articles)
                ])

                topic_prompt = f"""请分析以下公众号文章，生成一个话题聚合报告。

{articles_text}

请按以下 JSON 格式输出：
```json
{{
  "topics": [
    {{
      "name": "话题名称",
      "highlight": "一句话概括话题亮点",
      "data_numbers": [
        {{"content": "关键数据", "context": "数据背景", "source": "来源"}}
      ],
      "events_news": [
        {{"content": "事件描述", "time": "时间", "parties": "相关方", "source": "来源"}}
      ],
      "insider_insights": [
        {{"content": "洞察内容", "type": "类型", "source": "来源"}}
      ],
      "sources": [
        {{"title": "文章标题", "key_contribution": "核心贡献", "url": "链接"}}
      ]
    }}
  ]
}}
```"""

                topic_result = ai_client.chat([{"role": "user", "content": topic_prompt}])
                print(f"      ✅ AI 分析完成，话题聚合长度: {len(topic_result)} 字符")

                # 解析 AI 结果
                import json
                import re

                # 提取 JSON
                json_match = re.search(r'```json\s*(.*?)\s*```', topic_result, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1)
                else:
                    json_str = topic_result

                # 解析
                try:
                    topic_data = json.loads(json_str)
                    ai_topics = topic_data.get("topics", [])
                except:
                    print(f"      ⚠️ JSON 解析失败，使用默认话题")
                    ai_topics = [{
                        "name": "今日资讯",
                        "highlight": f"预发版端到端测试 - {len(wechat_articles)} 篇公众号文章汇总",
                        "data_numbers": [],
                        "events_news": [],
                        "insider_insights": [],
                        "sources": [
                            {
                                "title": a.title,
                                "key_contribution": a.ai_summary or "预发版测试文章",
                                "url": a.url
                            }
                            for a in wechat_articles
                        ]
                    }]

                # 构建 Topic 对象
                from wechat.src.models import DataNumber, EventNews, InsiderInsight, TopicSource

                topics = []
                for t_data in ai_topics:
                    # 解析数据与数字
                    data_numbers = [DataNumber(**d) for d in t_data.get("data_numbers", [])]

                    # 解析事件与动态
                    events_news = [EventNews(**e) for e in t_data.get("events_news", [])]

                    # 解析内幕与洞察（字段映射：type -> insight_type）
                    insider_insights = []
                    for i in t_data.get("insider_insights", []):
                        # 映射字段名
                        insight_data = {
                            "content": i.get("content", ""),
                            "insight_type": i.get("type", i.get("insight_type", "")),
                            "source": i.get("source", "")
                        }
                        insider_insights.append(InsiderInsight(**insight_data))

                    # 解析来源
                    sources = []
                    for s_data in t_data.get("sources", []):
                        # 匹配文章 URL
                        matched_url = ""
                        for article in wechat_articles:
                            if s_data["title"] in article.title or article.title in s_data["title"]:
                                matched_url = article.url
                                break
                        if not matched_url and wechat_articles:
                            matched_url = wechat_articles[0].url  # fallback

                        sources.append(TopicSource(
                            title=s_data["title"],
                            key_contribution=s_data.get("key_contribution", ""),
                            url=matched_url,
                            feed_name=wechat_articles[0].feed_name if wechat_articles else ""
                        ))

                    topics.append(Topic(
                        name=t_data.get("name", "未命名话题"),
                        highlight=t_data.get("highlight", ""),
                        articles=wechat_articles,
                        data_numbers=data_numbers,
                        events_news=events_news,
                        insider_insights=insider_insights,
                        sources=sources
                    ))

            except Exception as e:
                print(f"      ⚠️ AI 分析失败: {e}，使用 fallback")
                import traceback
                traceback.print_exc()

                # Fallback: 创建默认话题
                from wechat.src.models import TopicSource

                topics = [Topic(
                    name="今日文章",
                    highlight=f"预发版端到端测试 - {len(wechat_articles)} 篇公众号文章汇总",
                    articles=wechat_articles,
                    sources=[
                        TopicSource(
                            title=a.title,
                            key_contribution=a.ai_summary or "预发版测试文章",
                            url=a.url,
                            feed_name=a.feed_name
                        )
                        for a in wechat_articles
                    ]
                )]

            # 构建日报数据
            test_report = DailyReport(
                date=datetime.now(),
                total_articles=len(wechat_articles),
                critical_count=0,
                normal_count=len(wechat_articles),
                critical_articles=[],
                all_articles=wechat_articles,
                topics=topics,
            )

            # 3. 渲染邮件
            print("  📧 [3/4] 使用 EmailRenderer 渲染邮件...")
            from shared.lib.email_renderer import EmailRenderer

            renderer = EmailRenderer()

            # 转换 Topic 对象为模板数据
            topics_data = []
            for t in test_report.topics:
                sources_data = []
                for s in t.sources:
                    sources_data.append({
                        "title": s.title,
                        "url": s.url,
                        "feed_name": s.feed_name,
                        "key_contribution": s.key_contribution,
                    })

                topics_data.append({
                    "name": t.name,
                    "highlight": t.highlight,
                    "data_numbers": [
                        {
                            "content": d.content,
                            "context": d.context,
                            "source": d.source
                        }
                        for d in t.data_numbers
                    ],
                    "events_news": [
                        {
                            "content": e.content,
                            "time": e.time,
                            "parties": e.parties,
                            "source": e.source
                        }
                        for e in t.events_news
                    ],
                    "insider_insights": [
                        {
                            "content": i.content,
                            "insight_type": i.insight_type,
                            "source": i.source
                        }
                        for i in t.insider_insights
                    ],
                    "sources": sources_data,
                })

            # 准备模板数据（匹配 wechat 模板期望的结构）
            template_data = {
                "report": {
                    "date": test_report.date.strftime("%Y-%m-%d"),
                    "total_articles": test_report.total_articles,
                    "critical_count": test_report.critical_count,
                    "normal_count": test_report.normal_count,
                    "critical_articles": [],  # 重点文章为空
                    "topics": topics_data,
                },
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            }

            html_content = renderer.render_module_email(
                module='wechat',
                template_name='daily_report.html',
                context=template_data
            )

            # 验证模板
            if 'theme-wechat' in html_content:
                print("      ✅ 使用新统一模板 (theme-wechat)")
            else:
                print("      ⚠️ 警告: 使用了 fallback 模板")

            # 保存 HTML
            html_file = self.output_dir / f"wechat_prerelease_{self.timestamp}.html"
            html_file.write_text(html_content, encoding="utf-8")
            print(f"      💾 HTML 已保存: {html_file.name}")

            # 4. 发送邮件
            print("  📤 [4/4] 发送邮件...")
            email_sent = self._send_email(
                f"📱 [预发版测试] 公众号日报 - {datetime.now().strftime('%Y-%m-%d')}",
                html_file
            )

            result.success = True
            result.html_file = str(html_file)
            result.email_sent = email_sent
            result.details = {
                "article_count": len(articles),
                "feeds": list(set(a["feed_name"] for a in articles)),
            }

        except Exception as e:
            print(f"  ❌ 测试失败: {e}")
            import traceback
            traceback.print_exc()
            result.error = str(e)

        result.duration = time.time() - start_time
        print(f"  ⏱️ 耗时: {result.duration:.1f} 秒")
        return result

    # =========================================================================
    # 运行所有测试
    # =========================================================================
    def run_all(self) -> List[TestResult]:
        """运行所有模块的端到端测试"""
        print("=" * 60)
        print("🚀 TrendRadar 预发版端到端完整测试 (CI/CT)")
        print("=" * 60)
        print(f"⏰ 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"📧 邮件: {self.email_from} → {self.email_to}")
        print(f"🔧 邮件发送: {'启用' if self.send_email else '禁用'}")

        total_start = time.time()

        # 按照正式部署顺序执行
        self.results.append(self.test_investment())
        self.results.append(self.test_podcast())
        self.results.append(self.test_community())
        self.results.append(self.test_wechat(article_count=3))

        total_duration = time.time() - total_start

        # 打印汇总
        self._print_summary(total_duration)

        return self.results

    def _print_summary(self, total_duration: float):
        """打印测试汇总"""
        print("\n" + "=" * 60)
        print("📊 预发版端到端测试结果汇总")
        print("=" * 60)

        module_icons = {
            "investment": "📈",
            "podcast": "🎙️",
            "community": "🌐",
            "wechat": "📱",
        }

        module_names = {
            "investment": "投资模块",
            "podcast": "播客模块",
            "community": "社区模块",
            "wechat": "公众号模块",
        }

        success_count = 0
        email_count = 0

        for result in self.results:
            icon = module_icons.get(result.module, "📦")
            name = module_names.get(result.module, result.module)

            if result.success:
                status = "✅ 成功"
                success_count += 1
            else:
                status = f"❌ 失败: {result.error or '未知错误'}"

            email_status = ""
            if result.email_sent:
                email_status = " | 📧 已发送"
                email_count += 1
            elif result.success:
                email_status = " | 📧 未发送"

            print(f"  {icon} {name}: {status}{email_status} ({result.duration:.1f}s)")

        print(f"\n📈 总计: {success_count}/4 模块成功 | {email_count} 封邮件发送")
        print(f"⏱️ 总耗时: {total_duration:.1f} 秒")
        print(f"📁 输出目录: {self.output_dir}")
        print(f"⏰ 完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # 生成预览链接
        print("\n📱 手机预览链接 (需启动 HTTP 服务器):")
        for result in self.results:
            if result.html_file:
                filename = Path(result.html_file).name
                print(f"  - {module_icons.get(result.module, '')} http://192.168.0.112:8899/{filename}")

        if success_count == 4:
            print("\n🎉 预发版测试全部通过！可以进行发布。")
        else:
            print("\n⚠️ 存在失败的模块，请检查后重试。")


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='TrendRadar 预发版端到端测试')
    parser.add_argument('--no-email', action='store_true', help='禁用邮件发送')
    parser.add_argument('--module', choices=['investment', 'podcast', 'community', 'wechat', 'all'],
                        default='all', help='选择测试模块')

    args = parser.parse_args()

    tester = PreReleaseE2ETest(send_email=not args.no_email)

    if args.module == 'all':
        results = tester.run_all()
    else:
        if args.module == 'investment':
            result = tester.test_investment()
        elif args.module == 'podcast':
            result = tester.test_podcast()
        elif args.module == 'community':
            result = tester.test_community()
        elif args.module == 'wechat':
            result = tester.test_wechat()

        results = [result]
        tester.results = results
        tester._print_summary(result.duration)

    # 返回退出码
    success_count = sum(1 for r in results if r.success)
    return 0 if success_count == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
