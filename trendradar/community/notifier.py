# coding=utf-8
"""
社区内容邮件通知器

参考播客模块的邮件风格，生成美观的 HTML 邮件
"""

import os
import html
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, List, Any
from dataclasses import dataclass

from .collector import CollectedData, SourceData
from .analyzer import AnalysisResult, SourceAnalysis


@dataclass
class NotifyResult:
    """推送结果"""
    success: bool
    channel: str = ""
    error: Optional[str] = None


class CommunityNotifier:
    """
    社区内容邮件通知器
    
    生成包含多个来源的统一邮件，每个来源独立展示
    """
    
    # 来源配置（图标、颜色）
    SOURCE_CONFIG = {
        "hackernews": {
            "name": "HackerNews",
            "icon": "📰",
            "color": "#FF6600",
            "description": "技术社区热门讨论",
        },
        "reddit": {
            "name": "Reddit",
            "icon": "🔥",
            "color": "#FF4500",
            "description": "社区热点话题",
        },
        "kickstarter": {
            "name": "Kickstarter",
            "icon": "🚀",
            "color": "#05CE78",
            "description": "创新众筹项目",
        },
        "twitter": {
            "name": "Twitter/X",
            "icon": "🐦",
            "color": "#1DA1F2",
            "description": "实时动态",
        },
        "github": {
            "name": "GitHub Trending",
            "icon": "💻",
            "color": "#333333",
            "description": "热门开源项目",
        },
        "producthunt": {
            "name": "ProductHunt",
            "icon": "🎯",
            "color": "#DA552F",
            "description": "热门新产品",
        },
    }
    
    def __init__(
        self,
        notification_config: dict,
        email_config: dict,
        timezone: str = "Asia/Shanghai",
    ):
        """
        初始化通知器
        
        Args:
            notification_config: 通知配置
            email_config: 邮件配置
            timezone: 时区
        """
        self.notification_config = notification_config
        self.email_config = email_config
        self.timezone = timezone
        
        # 支持大小写 key
        self.enabled = notification_config.get("ENABLED", notification_config.get("enabled", True))
        self.channels = notification_config.get("CHANNELS", notification_config.get("channels", {}))
    
    def notify(
        self,
        data: CollectedData,
        analysis: AnalysisResult,
    ) -> Dict[str, NotifyResult]:
        """
        发送通知
        
        Args:
            data: 收集的数据
            analysis: 分析结果
            
        Returns:
            {channel: NotifyResult} 字典
        """
        results = {}
        
        if not self.enabled:
            return results
        
        # 邮件推送
        if self.channels.get("email", False):
            result = self._send_email(data, analysis)
            results["email"] = result
        
        return results
    
    def _send_email(
        self,
        data: CollectedData,
        analysis: AnalysisResult,
    ) -> NotifyResult:
        """发送邮件"""
        try:
            # 生成 HTML 内容（无论邮件配置如何都生成）
            html_content = self._render_email_html(data, analysis)

            # 保存临时 HTML 文件（无论邮件发送是否成功都保存）
            temp_dir = Path("output/community/email")
            temp_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            html_file = temp_dir / f"community_{timestamp}.html"
            html_file.write_text(html_content, encoding="utf-8")
            print(f"[CommunityNotifier] 💾 HTML已保存: {html_file}")

            # 检查邮件配置
            from_email = self.email_config.get("FROM", self.email_config.get("from", ""))
            password = self.email_config.get("PASSWORD", self.email_config.get("password", ""))
            to_email = self.email_config.get("TO", self.email_config.get("to", ""))

            if not all([from_email, password, to_email]):
                return NotifyResult(
                    success=False,
                    channel="email",
                    error="邮件配置不完整（HTML已生成）"
                )
            
            # 发送邮件
            from trendradar.notification.senders import send_to_email
            
            subject = f"🌐 社区热点日报 - {data.date}"
            
            smtp_server = self.email_config.get("SMTP_SERVER", self.email_config.get("smtp_server", ""))
            smtp_port = self.email_config.get("SMTP_PORT", self.email_config.get("smtp_port", ""))
            
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
            
            if success:
                print(f"[CommunityNotifier] ✅ 邮件发送成功")
                return NotifyResult(success=True, channel="email")
            else:
                return NotifyResult(
                    success=False,
                    channel="email",
                    error="邮件发送失败"
                )
                
        except Exception as e:
            print(f"[CommunityNotifier] ❌ 邮件发送异常: {e}")
            import traceback
            traceback.print_exc()
            return NotifyResult(
                success=False,
                channel="email",
                error=str(e)
            )
    
    def _render_email_html(
        self,
        data: CollectedData,
        analysis: AnalysisResult,
    ) -> str:
        """
        渲染邮件 HTML（使用统一的 EmailRenderer）
        """
        try:
            from shared.lib.email_renderer import EmailRenderer

            renderer = EmailRenderer()

            # 准备模板数据
            # 使用 overall_summary 作为 AI 分析内容（因为 source_analysis.summary 可能未填充）
            ai_content = analysis.overall_summary
            if not ai_content:
                # 如果 overall_summary 也为空，尝试使用 hackernews 的 summary
                hn_analysis = analysis.source_analyses.get("hackernews")
                if hn_analysis and hn_analysis.summary:
                    ai_content = hn_analysis.summary
            
            template_data = {
                "date": data.date,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "total_items": data.total_items,
                "sources": [],
                "analysis": {
                    "overall_summary": analysis.overall_summary,
                    "hackernews": {
                        "success": bool(ai_content),  # 有内容才算成功
                        "content": ai_content
                    }
                }
            }

            # 转换各来源数据为模板格式
            for source_id, source_data in data.sources.items():
                config = self.SOURCE_CONFIG.get(source_id, {
                    "name": source_id,
                    "icon": "📌",
                    "color": "#c8a86b",
                    "description": "",
                })

                # 获取来源分析
                source_analysis = analysis.source_analyses.get(source_id)

                # 准备条目数据
                entries = []
                for item in source_data.items:
                    entry = {
                        "title": item.get("title") or item.get("name", ""),
                        "url": item.get("url", ""),
                        "description": item.get("description") or item.get("tagline", ""),
                        "published_at": item.get("created_at") or item.get("published_at", ""),
                    }

                    # 添加特定来源的元数据
                    if source_id == "hackernews":
                        entry.update({
                            "score": item.get("score", 0),
                            "comments": item.get("comments", 0),
                            "author": item.get("author", ""),
                        })
                    elif source_id == "github":
                        entry.update({
                            "language": item.get("language", ""),
                            "stars": item.get("stars", 0),
                            "forks": item.get("forks", 0),
                        })
                    elif source_id == "producthunt":
                        entry.update({
                            "votes": item.get("votes", 0),
                            "comments": item.get("comments", 0),
                        })

                    # AI 总结
                    if source_analysis and source_analysis.item_analyses:
                        for item_analysis in source_analysis.item_analyses:
                            if item_analysis.item_id == item.get("id"):
                                entry["ai_summary"] = item_analysis.analysis
                                break

                    entries.append(entry)

                template_data["sources"].append({
                    "name": config["name"],
                    "icon": config["icon"],
                    "color": config["color"],
                    "description": config["description"],
                    "source_type": source_id,
                    "entries": entries,
                })

            # 使用 EmailRenderer 渲染
            return renderer.render_module_email(
                module='community',
                template_name='daily_report.html',
                context=template_data
            )

        except Exception as e:
            print(f"[CommunityNotifier] ⚠️ EmailRenderer 渲染失败，使用备用方案: {e}")
            import traceback
            traceback.print_exc()
            # 使用 fallback 方法
            return self._render_email_html_fallback(data, analysis)

    def _render_email_html_fallback(
        self,
        data: CollectedData,
        analysis: AnalysisResult,
    ) -> str:
        """渲染邮件 HTML"""
        
        # 渲染各来源的内容
        sources_html = ""
        for source_id, source_data in data.sources.items():
            if source_data.items:
                source_analysis = analysis.source_analyses.get(source_id)
                sources_html += self._render_source_section(source_id, source_data, source_analysis)
        
        # 总体摘要（公众号风格）
        overall_html = ""
        if analysis.overall_summary:
            overall_html = f"""
            <div class="overall-summary">
                <div class="summary-content content">
                    {self._markdown_to_html(analysis.overall_summary)}
                </div>
            </div>
            """
        
        html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>社区热点日报 - {data.date}</title>
    <style>
        /* ===== 公众号风格排版 ===== */
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
            line-height: 1.75;
            color: #3f3f3f;
            background-color: #fff;
            font-size: 16px;
            padding: 0;
        }}
        .container {{
            max-width: 680px;
            margin: 0 auto;
            padding: 20px 16px;
            background: white;
        }}
        /* 头部 */
        .header {{
            text-align: center;
            padding-bottom: 20px;
            margin-bottom: 25px;
            border-bottom: 1px solid #eee;
        }}
        .header h1 {{
            font-size: 22px;
            font-weight: 600;
            color: #1a1a1a;
            margin-bottom: 10px;
            letter-spacing: 1px;
        }}
        .header .date {{
            color: #888;
            font-size: 14px;
        }}
        .header .author {{
            color: #576b95;
            font-size: 14px;
            margin-top: 5px;
        }}
        /* 引用框（类似公众号灰色背景框）*/
        .quote-box {{
            background: #f7f7f7;
            border-left: 3px solid #c8a86b;
            padding: 15px 18px;
            margin: 20px 0;
            font-size: 15px;
            line-height: 1.8;
            color: #5a5a5a;
        }}
        .quote-box p {{
            margin: 8px 0;
        }}
        /* 章节标题 */
        .section-title {{
            font-size: 18px;
            font-weight: 600;
            color: #1a1a1a;
            margin: 30px 0 15px 0;
            padding-left: 12px;
            border-left: 4px solid #c8a86b;
        }}
        .section-subtitle {{
            font-size: 16px;
            font-weight: 600;
            color: #333;
            margin: 25px 0 12px 0;
        }}
        /* 正文段落 */
        .content p {{
            margin: 15px 0;
            text-align: justify;
        }}
        .content strong {{
            color: #c8a86b;
            font-weight: 600;
        }}
        .content a {{
            color: #576b95;
            text-decoration: none;
            border-bottom: 1px solid #576b95;
        }}
        .content a:hover {{
            color: #3a5180;
        }}
        /* 列表 */
        .content ul {{
            margin: 15px 0;
            padding-left: 0;
            list-style: none;
        }}
        .content ul li {{
            position: relative;
            padding-left: 20px;
            margin: 10px 0;
            line-height: 1.8;
        }}
        .content ul li::before {{
            content: "•";
            color: #c8a86b;
            font-weight: bold;
            position: absolute;
            left: 0;
        }}
        /* 来源标签 */
        .source-tag {{
            display: inline-block;
            background: #f0f0f0;
            color: #666;
            padding: 2px 10px;
            border-radius: 12px;
            font-size: 13px;
            margin-right: 8px;
        }}
        /* 案例卡片 */
        .case-card {{
            background: #fff;
            border: 1px solid #eee;
            border-radius: 8px;
            padding: 20px;
            margin: 20px 0;
            box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        }}
        .case-header {{
            margin-bottom: 15px;
        }}
        .case-number {{
            display: inline-block;
            background: #c8a86b;
            color: white;
            width: 26px;
            height: 26px;
            line-height: 26px;
            text-align: center;
            border-radius: 50%;
            font-size: 14px;
            font-weight: 600;
            margin-right: 10px;
        }}
        .case-title {{
            font-size: 17px;
            font-weight: 600;
            color: #1a1a1a;
            text-decoration: none;
            line-height: 1.5;
        }}
        .case-title:hover {{
            color: #576b95;
        }}
        .case-meta {{
            font-size: 13px;
            color: #888;
            margin-top: 8px;
            padding-left: 36px;
        }}
        .case-link {{
            display: inline-block;
            margin-top: 8px;
            padding-left: 36px;
        }}
        .case-link a {{
            color: #576b95;
            font-size: 13px;
            text-decoration: none;
        }}
        .case-link a:hover {{
            text-decoration: underline;
        }}
        .case-analysis {{
            margin-top: 15px;
            padding-top: 15px;
            border-top: 1px dashed #eee;
            font-size: 15px;
            line-height: 1.8;
            color: #3f3f3f;
        }}
        .case-analysis h3 {{
            font-size: 15px;
            font-weight: 600;
            color: #333;
            margin: 18px 0 10px 0;
        }}
        .case-analysis p {{
            margin: 10px 0;
        }}
        .case-analysis ul {{
            margin: 10px 0;
            padding-left: 0;
            list-style: none;
        }}
        .case-analysis ul li {{
            position: relative;
            padding-left: 18px;
            margin: 8px 0;
        }}
        .case-analysis ul li::before {{
            content: "·";
            color: #c8a86b;
            font-weight: bold;
            position: absolute;
            left: 0;
            font-size: 18px;
        }}
        .case-analysis strong {{
            color: #c8a86b;
        }}
        /* 来源分隔 */
        .source-divider {{
            margin: 35px 0 25px 0;
            text-align: center;
            position: relative;
        }}
        .source-divider::before {{
            content: "";
            position: absolute;
            left: 0;
            right: 0;
            top: 50%;
            height: 1px;
            background: #eee;
        }}
        .source-divider span {{
            background: white;
            padding: 0 20px;
            position: relative;
            color: #888;
            font-size: 14px;
        }}
        /* 数据表格 */
        .data-table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            font-size: 14px;
        }}
        .data-table th,
        .data-table td {{
            border: 1px solid #eee;
            padding: 12px;
            text-align: left;
        }}
        .data-table th {{
            background: #f7f7f7;
            font-weight: 600;
            color: #333;
        }}
        .data-table td {{
            color: #555;
        }}
        /* 页脚 */
        .footer {{
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #eee;
            text-align: center;
            font-size: 13px;
            color: #999;
        }}
        .footer p {{
            margin: 5px 0;
        }}
        /* 总览区域 */
        .overall-summary {{
            margin: 0;
        }}
        .overall-summary .summary-content {{
            font-size: 15px;
            line-height: 1.85;
            color: #3f3f3f;
        }}
        .overall-summary .summary-content h2 {{
            font-size: 18px;
            font-weight: 600;
            color: #1a1a1a;
            margin: 30px 0 15px 0;
            padding-left: 12px;
            border-left: 4px solid #c8a86b;
        }}
        .overall-summary .summary-content h3 {{
            font-size: 16px;
            font-weight: 600;
            color: #333;
            margin: 25px 0 12px 0;
        }}
        .overall-summary .summary-content h4 {{
            font-size: 15px;
            font-weight: 600;
            color: #444;
            margin: 20px 0 10px 0;
        }}
        .overall-summary .summary-content p {{
            margin: 12px 0;
            text-align: justify;
        }}
        .overall-summary .summary-content ul {{
            margin: 12px 0;
            padding-left: 0;
            list-style: none;
        }}
        .overall-summary .summary-content ul li {{
            position: relative;
            padding-left: 18px;
            margin: 8px 0;
        }}
        .overall-summary .summary-content ul li::before {{
            content: "•";
            color: #c8a86b;
            font-weight: bold;
            position: absolute;
            left: 0;
        }}
        .overall-summary .summary-content strong {{
            color: #c8a86b;
        }}
        .overall-summary .summary-content table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            font-size: 14px;
        }}
        .overall-summary .summary-content th,
        .overall-summary .summary-content td {{
            border: 1px solid #eee;
            padding: 12px;
            text-align: left;
        }}
        .overall-summary .summary-content th {{
            background: #f7f7f7;
            font-weight: 600;
        }}
        .overall-summary .summary-content hr {{
            border: none;
            height: 1px;
            background: linear-gradient(to right, transparent, #ddd, transparent);
            margin: 30px 0;
        }}
        .overall-summary .summary-content a {{
            color: #576b95;
            text-decoration: none;
        }}
        /* 移动端优化 */
        @media (max-width: 600px) {{
            body {{ font-size: 15px; }}
            .container {{ padding: 15px 12px; }}
            .header h1 {{ font-size: 20px; }}
            .section-title {{ font-size: 17px; }}
            .case-card {{ padding: 15px; }}
            .case-title {{ font-size: 16px; }}
            .case-analysis {{ font-size: 14px; }}
            .overall-summary .summary-content {{ font-size: 14px; }}
            .overall-summary .summary-content h2 {{ font-size: 17px; }}
            .overall-summary .summary-content h3 {{ font-size: 15px; }}
        }}
        /* 兼容旧样式 */
        .section {{ margin: 0; padding: 0; background: none; border: none; border-radius: 0; }}
        .source-section {{ margin: 20px 0; }}
        .source-header {{ margin-bottom: 15px; }}
        .source-name {{ font-size: 16px; font-weight: 600; color: #1a1a1a; }}
        .source-desc {{ font-size: 13px; color: #888; margin-top: 5px; }}
        .analysis-box {{ background: #f7f7f7; border: none; border-left: 3px solid #c8a86b; border-radius: 0; padding: 15px 18px; margin: 15px 0; }}
        .analysis-box h3 {{ color: #333; font-size: 15px; margin-bottom: 10px; }}
        .item-list {{ list-style: none; padding: 0; }}
        .item {{ padding: 12px 0; border-bottom: 1px solid #f0f0f0; }}
        .item:last-child {{ border-bottom: none; }}
        .item-title {{ font-weight: 500; font-size: 15px; color: #1a1a1a; text-decoration: none; }}
        .item-title:hover {{ color: #576b95; }}
        .item-meta {{ font-size: 13px; color: #888; margin-top: 6px; }}
        .tag {{ background: #f0f0f0; color: #666; padding: 2px 8px; border-radius: 10px; font-size: 12px; }}
        /* 逐案例分析 - 使用新的 case-card 样式 */
        .analyzed-item {{ background: none; border: none; padding: 0; margin: 0; }}
        .analyzed-item-header {{ display: block; margin: 0; }}
        .item-number {{ display: none; }}
        .analyzed-item-title {{ font-size: 16px; }}
        .analyzed-item-meta {{ padding-left: 0; font-size: 13px; color: #888; }}
        .analyzed-item-analysis {{ padding-left: 0; font-size: 15px; line-height: 1.8; }}
            .analyzed-item {{ padding: 10px; margin-bottom: 10px; }}
            .analyzed-item-header {{ gap: 8px; }}
            .item-number {{ width: 20px; height: 20px; font-size: 10px; }}
            .analyzed-item-title {{ font-size: 13px; }}
            .analyzed-item-meta {{ font-size: 11px; padding-left: 28px; }}
            .analyzed-item-analysis {{ font-size: 12px; padding-left: 28px; line-height: 1.6; }}
            .analyzed-item-analysis h3 {{ font-size: 13px; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🌐 社区热点日报</h1>
            <div class="date">📅 {data.date} · 共 {data.total_items} 条</div>
        </div>
        
        {overall_html}
        
        {sources_html}
        
        <div class="footer">
            <p>TrendRadar 社区监控 · {datetime.now().strftime("%Y-%m-%d %H:%M")}</p>
        </div>
    </div>
</body>
</html>"""
        
        return html_content
    
    def _render_source_section(
        self,
        source_id: str,
        source_data: SourceData,
        source_analysis: Optional[SourceAnalysis],
    ) -> str:
        """渲染单个来源的内容（公众号风格）"""
        config = self.SOURCE_CONFIG.get(source_id, {
            "name": source_id,
            "icon": "📌",
            "color": "#c8a86b",
            "description": "",
        })
        
        # 检查是否有逐案例分析
        if source_analysis and source_analysis.item_analyses:
            # 有逐案例分析：渲染每个案例的详细分析
            items_html = self._render_analyzed_items(source_analysis.item_analyses)
            analysis_count = len(source_analysis.item_analyses)
            
            return f"""
        <!-- 来源分隔线 -->
        <div class="source-divider">
            <span>{config['icon']} {config['name']}</span>
        </div>
        
        <p style="color: #888; font-size: 14px; text-align: center; margin-bottom: 20px;">
            {config['description']} · 详细分析 {analysis_count} 个案例
        </p>
        
        {items_html}
        """
        else:
            # 没有逐案例分析：使用原来的渲染方式
            analysis_html = ""
            if source_analysis and source_analysis.summary:
                analysis_html = f"""
            <div class="quote-box">
                <strong>🤖 AI 分析</strong>
                {self._markdown_to_html(source_analysis.summary)}
            </div>
            """
            
            items_html = self._render_items(source_id, source_data.items[:15])
            
            return f"""
        <!-- 来源分隔线 -->
        <div class="source-divider">
            <span>{config['icon']} {config['name']}</span>
        </div>
        
        <p style="color: #888; font-size: 14px; text-align: center; margin-bottom: 20px;">
            {config['description']} · {source_data.count} 条
        </p>
        
        {analysis_html}
        <ul class="item-list">
            {items_html}
        </ul>
        """
    
    def _render_analyzed_items(self, item_analyses: list) -> str:
        """渲染带有 AI 分析的案例列表（公众号风格）"""
        from .analyzer import ItemAnalysis
        
        html_parts = []
        for idx, item_analysis in enumerate(item_analyses, 1):
            title = self._escape_html(item_analysis.title)
            url = item_analysis.url or "#"
            analysis_html = self._markdown_to_html(item_analysis.analysis)
            
            # 构建元信息
            meta_parts = []
            for key, value in item_analysis.meta.items():
                meta_parts.append(f"{key}: {value}")
            meta_str = " · ".join(meta_parts) if meta_parts else ""
            
            # 构建链接显示（截断长链接）
            link_display = url[:60] + "..." if len(url) > 60 else url
            link_html = f'''
                <div class="case-link">
                    <a href="{url}" target="_blank">🔗 {link_display}</a>
                </div>
            ''' if url and url != "#" else ""
            
            html_parts.append(f"""
            <div class="case-card">
                <div class="case-header">
                    <span class="case-number">{idx}</span>
                    <a href="{url}" class="case-title" target="_blank">{title}</a>
                </div>
                {f'<div class="case-meta">{meta_str}</div>' if meta_str else ''}
                {link_html}
                <div class="case-analysis">
                    {analysis_html}
                </div>
            </div>
            """)
        
        return "\n".join(html_parts)
    
    def _render_items(self, source_id: str, items: List[Dict]) -> str:
        """渲染条目列表"""
        html_parts = []
        
        for item in items:
            if source_id == "kickstarter":
                html_parts.append(self._render_kickstarter_item(item))
            elif source_id == "twitter":
                html_parts.append(self._render_twitter_item(item))
            elif source_id == "github":
                html_parts.append(self._render_github_item(item))
            elif source_id == "producthunt":
                html_parts.append(self._render_producthunt_item(item))
            else:
                html_parts.append(self._render_default_item(item))
        
        return "\n".join(html_parts)
    
    def _render_default_item(self, item: Dict) -> str:
        """渲染默认条目（HackerNews、Reddit）"""
        title = self._escape_html(item.get("title", ""))
        url = item.get("url", "#")
        
        # 分数和评论
        meta_parts = []
        if "score" in item:
            meta_parts.append(f"⬆️ {item['score']}")
        if "comments" in item:
            meta_parts.append(f"💬 {item['comments']}")
        if "subreddit" in item:
            meta_parts.append(f"r/{item['subreddit']}")
        if "author" in item:
            meta_parts.append(f"👤 {item['author']}")
        
        meta_html = " · ".join(meta_parts) if meta_parts else ""
        
        # AI 评分和标签
        score_html = ""
        if "ai_score" in item:
            score_html = f'<span class="item-score">{item["ai_score"]}分</span>'
        
        tags_html = ""
        if "ai_tags" in item and item["ai_tags"]:
            tags = "".join([f'<span class="tag">{t}</span>' for t in item["ai_tags"][:3]])
            tags_html = f'<span class="item-tags">{tags}</span>'
        
        return f"""
        <li class="item">
            {score_html}{tags_html}
            <a href="{url}" class="item-title" target="_blank">{title}</a>
            <div class="item-meta">{meta_html}</div>
        </li>
        """
    
    def _render_kickstarter_item(self, item: Dict) -> str:
        """渲染 Kickstarter 条目"""
        name = self._escape_html(item.get("name", ""))
        blurb = self._escape_html(item.get("blurb", ""))[:100]
        url = item.get("url", "#")
        
        pledged = item.get("pledged", 0)
        goal = item.get("goal", 1)
        backers = item.get("backers", 0)
        funded_percent = item.get("funded_percent", 0)
        currency = item.get("currency", "USD")
        
        progress_width = min(funded_percent, 100)
        
        return f"""
        <li class="item">
            <a href="{url}" class="item-title" target="_blank">{name}</a>
            <div style="font-size: 13px; color: #666; margin: 5px 0;">{blurb}</div>
            <div class="ks-progress">
                <div class="ks-progress-bar" style="width: {progress_width}%"></div>
            </div>
            <div class="item-meta">
                <span>💰 {currency} {pledged:,.0f} / {goal:,.0f}</span>
                <span>📈 {funded_percent}%</span>
                <span>👥 {backers} 支持者</span>
            </div>
        </li>
        """
    
    def _render_twitter_item(self, item: Dict) -> str:
        """渲染 Twitter 条目"""
        content = self._escape_html(item.get("content", ""))[:280]
        url = item.get("url", "#")
        author = item.get("author", "")
        author_handle = item.get("author_handle", "")
        
        return f"""
        <li class="item">
            <div class="item-meta" style="margin-bottom: 5px;">
                <span>👤 {author}</span>
                <span>@{author_handle}</span>
            </div>
            <div style="font-size: 14px; line-height: 1.5;">{content}</div>
            <a href="{url}" target="_blank" style="font-size: 12px; color: #1DA1F2;">查看原文</a>
        </li>
        """
    
    def _render_github_item(self, item: Dict) -> str:
        """渲染 GitHub 条目"""
        name = self._escape_html(item.get("name", ""))
        full_name = self._escape_html(item.get("full_name", ""))
        description = self._escape_html(item.get("description", ""))[:150]
        url = item.get("url", "#")
        stars = item.get("stars", 0)
        forks = item.get("forks", 0)
        language = item.get("language", "")
        owner = item.get("owner", "")
        topics = item.get("topics", [])
        
        # AI 评分和标签
        score_html = ""
        if "ai_score" in item:
            score_html = f'<span class="item-score">{item["ai_score"]}分</span>'
        
        tags_html = ""
        if "ai_tags" in item and item["ai_tags"]:
            tags = "".join([f'<span class="tag">{t}</span>' for t in item["ai_tags"][:3]])
            tags_html = f'<span class="item-tags">{tags}</span>'
        elif topics:
            tags = "".join([f'<span class="tag">{t}</span>' for t in topics[:3]])
            tags_html = f'<span class="item-tags">{tags}</span>'
        
        # 语言标签
        lang_html = f'<span style="color: #666;">📦 {language}</span>' if language else ""
        
        return f"""
        <li class="item">
            {score_html}{tags_html}
            <a href="{url}" class="item-title" target="_blank">{full_name}</a>
            <div style="font-size: 13px; color: #666; margin: 5px 0;">{description}</div>
            <div class="item-meta">
                <span>⭐ {stars:,}</span>
                <span>🍴 {forks:,}</span>
                {lang_html}
            </div>
        </li>
        """
    
    def _render_producthunt_item(self, item: Dict) -> str:
        """渲染 ProductHunt 条目"""
        name = self._escape_html(item.get("name", ""))
        tagline = self._escape_html(item.get("tagline", ""))[:100]
        url = item.get("url", "#")
        votes = item.get("votes", 0)
        topics = item.get("topics", [])
        
        # AI 评分和标签
        score_html = ""
        if "ai_score" in item:
            score_html = f'<span class="item-score">{item["ai_score"]}分</span>'
        
        tags_html = ""
        if "ai_tags" in item and item["ai_tags"]:
            tags = "".join([f'<span class="tag">{t}</span>' for t in item["ai_tags"][:3]])
            tags_html = f'<span class="item-tags">{tags}</span>'
        elif topics:
            tags = "".join([f'<span class="tag">{t}</span>' for t in topics[:3]])
            tags_html = f'<span class="item-tags">{tags}</span>'
        
        # 投票数（如果有）
        votes_html = f'<span>🔺 {votes} votes</span>' if votes > 0 else ""
        
        return f"""
        <li class="item">
            {score_html}{tags_html}
            <a href="{url}" class="item-title" target="_blank">{name}</a>
            <div style="font-size: 13px; color: #666; margin: 5px 0;">{tagline}</div>
            <div class="item-meta">
                {votes_html}
            </div>
        </li>
        """
    
    def _escape_html(self, text: str) -> str:
        """转义 HTML 特殊字符"""
        return html.escape(str(text)) if text else ""
    
    def _markdown_to_html(self, markdown_text: str) -> str:
        """简单的 Markdown 转 HTML"""
        if not markdown_text:
            return ""
        
        text = self._escape_html(markdown_text)
        
        # 标题
        text = re.sub(r'^### (.+)$', r'<h4>\1</h4>', text, flags=re.MULTILINE)
        text = re.sub(r'^## (.+)$', r'<h3>\1</h3>', text, flags=re.MULTILINE)
        
        # 粗体
        text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
        
        # 列表
        text = re.sub(r'^- (.+)$', r'<li>\1</li>', text, flags=re.MULTILINE)
        text = re.sub(r'(<li>.*</li>\n?)+', r'<ul>\g<0></ul>', text)
        
        # 段落
        text = re.sub(r'\n\n+', '</p><p>', text)
        text = f'<p>{text}</p>'
        
        # 清理
        text = text.replace('<p></p>', '')
        text = text.replace('<p><h3>', '<h3>').replace('</h3></p>', '</h3>')
        text = text.replace('<p><h4>', '<h4>').replace('</h4></p>', '</h4>')
        text = text.replace('<p><ul>', '<ul>').replace('</ul></p>', '</ul>')
        
        return text
    
    @classmethod
    def from_config(cls, config: dict) -> "CommunityNotifier":
        """从配置创建通知器"""
        community_config = config.get("COMMUNITY", config.get("community", {}))
        notification_config = community_config.get("NOTIFICATION", community_config.get("notification", {}))

        # 确保 channels 配置存在（默认启用邮件）
        if "channels" not in notification_config and "CHANNELS" not in notification_config:
            notification_config = dict(notification_config)  # 复制避免修改原配置
            notification_config["channels"] = {"email": True}
        elif "channels" not in notification_config:
            notification_config = dict(notification_config)
            notification_config["channels"] = notification_config.get("CHANNELS", {"email": True})

        # 构建邮件配置（从全局 notification 配置读取）
        email_config = {
            "from": config.get("EMAIL_FROM", ""),
            "password": config.get("EMAIL_PASSWORD", ""),
            "to": config.get("EMAIL_TO", ""),
            "smtp_server": config.get("EMAIL_SMTP_SERVER", ""),
            "smtp_port": config.get("EMAIL_SMTP_PORT", ""),
        }

        timezone = config.get("TIMEZONE", "Asia/Shanghai")

        return cls(
            notification_config=notification_config,
            email_config=email_config,
            timezone=timezone,
        )
