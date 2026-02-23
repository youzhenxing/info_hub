# coding=utf-8
"""
播客即时推送通知

发现新播客节目后立即推送邮件（Type A）
"""

import os
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional
from dataclasses import dataclass

from .fetcher import PodcastEpisode


@dataclass
class NotifyResult:
    """推送结果"""
    success: bool
    channel: str = ""
    error: Optional[str] = None


class PodcastNotifier:
    """
    播客即时推送通知器

    Type A 推送：发现新节目即推送，每个节目单独一封邮件
    """

    def __init__(
        self,
        notification_config: dict,
        email_config: dict,
        timezone: str = "Asia/Shanghai",
    ):
        """
        初始化通知器

        Args:
            notification_config: 播客通知配置（来自 podcast.notification）
            email_config: 邮件配置（来自 notification.channels.email）
            timezone: 时区
        """
        self.notification_config = notification_config
        self.email_config = email_config
        self.timezone = timezone

        self.enabled = notification_config.get("ENABLED", notification_config.get("enabled", True))
        self.channels = notification_config.get("CHANNELS", notification_config.get("channels", {}))

    def notify(
        self,
        episode: PodcastEpisode,
        transcript: str = "",
        analysis: str = "",
    ) -> Dict[str, NotifyResult]:
        """
        推送播客通知

        Args:
            episode: 播客节目信息
            transcript: 转写文本（可选，用于生成邮件内容）
            analysis: AI 分析结果（Markdown 格式）

        Returns:
            {channel: NotifyResult} 字典
        """
        results = {}

        if not self.enabled:
            return results

        # 邮件推送
        if self.channels.get("email", False):
            result = self._send_email(episode, transcript, analysis)
            results["email"] = result

        return results

    def _send_email(
        self,
        episode: PodcastEpisode,
        transcript: str,
        analysis: str,
    ) -> NotifyResult:
        """
        发送播客邮件

        Args:
            episode: 播客节目信息
            transcript: 转写文本
            analysis: AI 分析结果

        Returns:
            NotifyResult 对象
        """
        try:
            # 检查邮件配置（支持大小写）
            from_email = self.email_config.get("FROM", self.email_config.get("from", ""))
            password = self.email_config.get("PASSWORD", self.email_config.get("password", ""))
            to_email = self.email_config.get("TO", self.email_config.get("to", ""))

            print(f"[PodcastNotifier] 准备发送邮件: {episode.title}")
            print(f"[PodcastNotifier] 发件人: {from_email}")
            print(f"[PodcastNotifier] 收件人: {to_email}")

            if not all([from_email, password, to_email]):
                print(f"[PodcastNotifier] ❌ 邮件配置不完整")
                return NotifyResult(
                    success=False,
                    channel="email",
                    error="邮件配置不完整"
                )

            # 生成 HTML 内容
            html_content = self._render_email_html(episode, transcript, analysis)

            # 保存临时 HTML 文件
            temp_dir = Path("output/podcast/email")
            temp_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            html_file = temp_dir / f"podcast_{episode.feed_id}_{timestamp}.html"
            html_file.write_text(html_content, encoding="utf-8")

            # 调用现有的邮件发送函数
            from trendradar.notification.senders import send_to_email

            subject = f"🎙️ 播客更新: {episode.title}"
            
            print(f"[PodcastNotifier] 开始调用 send_to_email...")
            print(f"[PodcastNotifier] HTML 文件: {html_file}")

            smtp_server = self.email_config.get("SMTP_SERVER", self.email_config.get("smtp_server", ""))
            smtp_port = self.email_config.get("SMTP_PORT", self.email_config.get("smtp_port", ""))
            
            # 转换端口为整数
            smtp_port_int = None
            if smtp_port:
                try:
                    smtp_port_int = int(smtp_port)
                except (ValueError, TypeError):
                    pass

            success = send_to_email(
                from_email=from_email,
                password=password,
                to_email=to_email,
                report_type=subject,
                html_file_path=str(html_file),
                custom_smtp_server=smtp_server if smtp_server else None,
                custom_smtp_port=smtp_port_int,
            )

            print(f"[PodcastNotifier] send_to_email 返回: {success}")

            if success:
                print(f"[PodcastNotifier] ✅ 邮件发送成功: {episode.title}")
                return NotifyResult(success=True, channel="email")
            else:
                print(f"[PodcastNotifier] ❌ 邮件发送失败")
                return NotifyResult(
                    success=False,
                    channel="email",
                    error="邮件发送失败"
                )

        except Exception as e:
            print(f"[PodcastNotifier] ❌ 邮件发送异常: {e}")
            import traceback
            traceback.print_exc()
            return NotifyResult(
                success=False,
                channel="email",
                error=f"邮件发送异常: {e}"
            )

    def _render_email_html(
        self,
        episode: PodcastEpisode,
        transcript: str,
        analysis: str,
    ) -> str:
        """
        渲染播客邮件 HTML（使用统一的 EmailRenderer）

        Args:
            episode: 播客节目信息
            transcript: 转写文本
            analysis: AI 分析结果

        Returns:
            HTML 内容字符串
        """
        try:
            from shared.lib.email_renderer import EmailRenderer

            renderer = EmailRenderer()

            # 准备模板数据 - 将 PodcastEpisode 对象转换为字典
            template_data = {
                "episode": {
                    "title": episode.title,
                    "feed_name": episode.feed_name,
                    "feed_id": episode.feed_id,
                    "published_at": episode.published_at,
                    "duration": episode.duration,
                    "author": episode.author,
                    "summary": episode.summary,
                    "url": episode.url,
                    "audio_url": episode.audio_url,
                },
                "transcript": transcript,
                "analysis": analysis,
                "date": datetime.now().strftime("%Y-%m-%d"),
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }

            print(f"[PodcastNotifier] 使用 EmailRenderer 渲染邮件...")
            return renderer.render_module_email(
                module='podcast',
                template_name='episode_update.html',
                context=template_data
            )

        except Exception as e:
            print(f"[PodcastNotifier] ⚠️ EmailRenderer 渲染失败，使用备用方案: {e}")
            import traceback
            traceback.print_exc()
            return self._render_email_html_fallback(episode, transcript, analysis)

    def _render_email_html_fallback(
        self,
        episode: PodcastEpisode,
        transcript: str,
        analysis: str,
    ) -> str:
        """
        渲染播客邮件 HTML（备用方案，使用内联 HTML）

        Args:
            episode: 播客节目信息
            transcript: 转写文本
            analysis: AI 分析结果

        Returns:
            HTML 内容字符串
        """
        # 格式化发布时间
        published_str = episode.published_at or "未知"
        if published_str and "T" in published_str:
            try:
                dt = datetime.fromisoformat(published_str.replace("Z", "+00:00"))
                published_str = dt.strftime("%Y-%m-%d %H:%M")
            except Exception:
                pass

        # 格式化时长
        duration_str = episode.duration or "未知"

        # 将 Markdown 分析结果转换为 HTML
        analysis_html = self._markdown_to_html(analysis) if analysis else "<p>（AI 分析未启用或失败）</p>"

        # 截断转写文本预览
        transcript_preview = ""
        if transcript:
            preview_length = 500
            if len(transcript) > preview_length:
                transcript_preview = transcript[:preview_length] + "..."
            else:
                transcript_preview = transcript

        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>播客更新: {self._escape_html(episode.title)}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            background: white;
            border-radius: 12px;
            padding: 30px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        .header {{
            border-bottom: 2px solid #007AFF;
            padding-bottom: 20px;
            margin-bottom: 20px;
        }}
        .podcast-name {{
            color: #007AFF;
            font-size: 14px;
            font-weight: 500;
            margin-bottom: 8px;
        }}
        .episode-title {{
            font-size: 24px;
            font-weight: 700;
            color: #1a1a1a;
            margin: 0 0 15px 0;
        }}
        .meta {{
            color: #666;
            font-size: 14px;
        }}
        .meta-item {{
            display: inline-block;
            margin-right: 20px;
        }}
        .section {{
            margin: 25px 0;
        }}
        .section-title {{
            font-size: 18px;
            font-weight: 600;
            color: #1a1a1a;
            margin-bottom: 15px;
            padding-bottom: 8px;
            border-bottom: 1px solid #eee;
        }}
        .analysis {{
            background: #f8f9fa;
            border-radius: 8px;
            padding: 20px;
        }}
        .analysis h3 {{
            color: #007AFF;
            font-size: 16px;
            margin: 20px 0 10px 0;
        }}
        .analysis h3:first-child {{
            margin-top: 0;
        }}
        .analysis ul {{
            padding-left: 20px;
        }}
        .analysis li {{
            margin: 8px 0;
        }}
        .transcript-preview {{
            background: #f0f0f0;
            border-radius: 8px;
            padding: 15px;
            font-size: 14px;
            color: #555;
            white-space: pre-wrap;
            max-height: 200px;
            overflow-y: auto;
        }}
        .btn {{
            display: inline-block;
            background: #007AFF;
            color: white;
            padding: 12px 24px;
            border-radius: 8px;
            text-decoration: none;
            font-weight: 500;
            margin-top: 15px;
        }}
        .btn:hover {{
            background: #0056b3;
        }}
        .footer {{
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #eee;
            font-size: 12px;
            color: #999;
            text-align: center;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="podcast-name">🎙️ {self._escape_html(episode.feed_name)}</div>
            <h1 class="episode-title">{self._escape_html(episode.title)}</h1>
            <div class="meta">
                <span class="meta-item">📅 {published_str}</span>
                <span class="meta-item">⏱️ {duration_str}</span>
                {f'<span class="meta-item">👤 {self._escape_html(episode.author)}</span>' if episode.author else ''}
            </div>
        </div>

        <div class="section">
            <h2 class="section-title">🤖 AI 分析</h2>
            <div class="analysis">
                {analysis_html}
            </div>
        </div>


        <div class="section">
            {f'<a href="{self._escape_html(episode.url)}" class="btn">🔗 查看原文</a>' if episode.url else ''}
            {f'<a href="{self._escape_html(episode.audio_url)}" class="btn" style="margin-left: 10px;">🎧 收听音频</a>' if episode.audio_url else ''}
        </div>

        <div class="footer">
            <p>由 TrendRadar 播客监控自动生成</p>
            <p>生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
        </div>
    </div>
</body>
</html>"""

        return html

    def _render_transcript_section(self, transcript_preview: str) -> str:
        """渲染转写预览段落"""
        return f"""
        <div class="section">
            <h2 class="section-title">📝 转写预览</h2>
            <div class="transcript-preview">{self._escape_html(transcript_preview)}</div>
        </div>
        """

    def _render_summary_section(self, summary: str) -> str:
        """渲染节目简介段落"""
        return f"""
        <div class="section">
            <h2 class="section-title">📖 节目简介</h2>
            <p>{self._escape_html(summary)}</p>
        </div>
        """

    def _escape_html(self, text: str) -> str:
        """转义 HTML 特殊字符"""
        import html
        return html.escape(str(text)) if text else ""

    def _markdown_to_html(self, markdown_text: str) -> str:
        """
        简单的 Markdown 转 HTML

        支持：标题、列表、粗体、斜体
        """
        import re

        if not markdown_text:
            return ""

        html_text = markdown_text

        # 转义 HTML
        html_text = self._escape_html(html_text)

        # 标题 (### -> h3)
        html_text = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html_text, flags=re.MULTILINE)
        html_text = re.sub(r'^## (.+)$', r'<h3>\1</h3>', html_text, flags=re.MULTILINE)

        # 粗体
        html_text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html_text)

        # 斜体
        html_text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html_text)

        # 无序列表
        html_text = re.sub(r'^- (.+)$', r'<li>\1</li>', html_text, flags=re.MULTILINE)
        html_text = re.sub(r'(<li>.*</li>\n?)+', r'<ul>\g<0></ul>', html_text)

        # 段落
        html_text = re.sub(r'\n\n+', '</p><p>', html_text)
        html_text = f'<p>{html_text}</p>'

        # 清理多余的标签
        html_text = html_text.replace('<p></p>', '')
        html_text = html_text.replace('<p><h3>', '<h3>')
        html_text = html_text.replace('</h3></p>', '</h3>')
        html_text = html_text.replace('<p><ul>', '<ul>')
        html_text = html_text.replace('</ul></p>', '</ul>')

        return html_text

    @classmethod
    def from_config(cls, config: dict) -> "PodcastNotifier":
        """
        从配置字典创建通知器

        Args:
            config: 完整配置字典

        Returns:
            PodcastNotifier 实例
        """
        podcast_config = config.get("PODCAST", config.get("podcast", {}))
        notification_config = podcast_config.get("notification", {})

        email_config = config.get("NOTIFICATION", config.get("notification", {}))
        email_config = email_config.get("channels", {}).get("email", {})

        timezone = config.get("APP", config.get("app", {})).get("timezone", "Asia/Shanghai")

        return cls(
            notification_config=notification_config,
            email_config=email_config,
            timezone=timezone,
        )
