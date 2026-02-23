# coding=utf-8
"""
投资简报推送通知

定时推送每日投资简报邮件（Type C）
"""

import html
import re
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from .collector import CollectedData
from .analyzer import AnalysisResult


@dataclass
class NotifyResult:
    """推送结果"""
    success: bool
    channel: str = ""
    error: Optional[str] = None


class InvestmentNotifier:
    """
    投资简报推送通知器

    Type C 推送：定时推送（中午 A股/港股，晚上美股）
    """

    def __init__(
        self,
        notification_config: Dict[str, Any],
        email_config: Dict[str, Any],
        timezone: str = "Asia/Shanghai",
    ):
        """
        初始化通知器

        Args:
            notification_config: 投资通知配置（来自 investment.notification）
            email_config: 邮件配置（来自 notification.channels.email）
            timezone: 时区
        """
        self.notification_config = notification_config
        self.email_config = email_config
        self.timezone = timezone

        self.enabled = notification_config.get("enabled", True)
        self.channels = notification_config.get("channels", {})

    def notify(
        self,
        data: CollectedData,
        analysis: AnalysisResult,
        market_type: str = "cn",  # cn 或 us
    ) -> Dict[str, NotifyResult]:
        """
        推送投资简报

        Args:
            data: 收集的投资数据
            analysis: AI 分析结果
            market_type: 市场类型（cn=A股/港股，us=美股）

        Returns:
            {channel: NotifyResult} 字典
        """
        results = {}

        if not self.enabled:
            return results

        # 邮件推送
        if self.channels.get("email", False):
            result = self._send_email(data, analysis, market_type)
            results["email"] = result

        return results

    def _send_email(
        self,
        data: CollectedData,
        analysis: AnalysisResult,
        market_type: str,
    ) -> NotifyResult:
        """
        发送投资简报邮件

        Args:
            data: 收集的投资数据
            analysis: AI 分析结果
            market_type: 市场类型

        Returns:
            NotifyResult 对象
        """
        try:
            # 检查邮件配置
            from_email = self.email_config.get("from", self.email_config.get("FROM", ""))
            password = self.email_config.get("password", self.email_config.get("PASSWORD", ""))
            to_email = self.email_config.get("to", self.email_config.get("TO", ""))

            print(f"[InvestmentNotifier] 准备发送投资简报邮件")
            print(f"[InvestmentNotifier] 发件人: {from_email}")
            print(f"[InvestmentNotifier] 收件人: {to_email}")

            if not all([from_email, password, to_email]):
                print(f"[InvestmentNotifier] ❌ 邮件配置不完整")
                return NotifyResult(
                    success=False,
                    channel="email",
                    error="邮件配置不完整"
                )

            # 生成 HTML 内容
            html_content = self._render_email_html(data, analysis, market_type)

            # 保存临时 HTML 文件
            temp_dir = Path("output/investment/email")
            temp_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            html_file = temp_dir / f"investment_{market_type}_{timestamp}.html"
            html_file.write_text(html_content, encoding="utf-8")

            # 调用现有的邮件发送函数
            from trendradar.notification.senders import send_to_email

            market_name = "A股/港股" if market_type == "cn" else "美股"
            subject = f"每日投资简报 - {data.date}"

            print(f"[InvestmentNotifier] 开始调用 send_to_email...")
            print(f"[InvestmentNotifier] HTML 文件: {html_file}")

            smtp_server = self.email_config.get("smtp_server", self.email_config.get("SMTP_SERVER", ""))
            smtp_port = self.email_config.get("smtp_port", self.email_config.get("SMTP_PORT", ""))

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

            print(f"[InvestmentNotifier] send_to_email 返回: {success}")

            if success:
                print(f"[InvestmentNotifier] ✅ 邮件发送成功")
                return NotifyResult(success=True, channel="email")
            else:
                print(f"[InvestmentNotifier] ❌ 邮件发送失败")
                return NotifyResult(
                    success=False,
                    channel="email",
                    error="邮件发送失败"
                )

        except Exception as e:
            print(f"[InvestmentNotifier] ❌ 邮件发送异常: {e}")
            import traceback
            traceback.print_exc()
            return NotifyResult(
                success=False,
                channel="email",
                error=f"邮件发送异常: {e}"
            )

    def _render_email_html(
        self,
        data: CollectedData,
        analysis: AnalysisResult,
        market_type: str,
    ) -> str:
        """
        渲染投资简报邮件 HTML（使用统一的 EmailRenderer）

        Args:
            data: 收集的投资数据
            analysis: AI 分析结果
            market_type: 市场类型

        Returns:
            HTML 内容字符串
        """
        try:
            from shared.lib.email_renderer import EmailRenderer

            renderer = EmailRenderer()

            # 格式化新闻时间
            now = datetime.now()
            formatted_news = []
            for item in (data.news[:15] if data.news else []):
                # 创建新的新闻项,格式化时间为纯文本
                from copy import deepcopy
                news_item = deepcopy(item)
                if news_item.published:
                    original_time = news_item.published
                    news_item.published = self._format_news_time_text(news_item.published, now)
                    print(f"[InvestmentNotifier] 时间格式化: {original_time} -> {news_item.published}")
                formatted_news.append(news_item)

            # 准备模板数据 - 需要包装为 data 结构以匹配模板
            template_data = {
                "data": {
                    "date": data.date,
                    "timestamp": data.timestamp,
                    "market_snapshot": data.market_snapshot,
                    "news": formatted_news,
                },
                "analysis": {
                    "success": analysis.success,
                    "content": analysis.content if analysis.success else None,
                },
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }

            print(f"[InvestmentNotifier] 使用 EmailRenderer 渲染邮件...")
            return renderer.render_module_email(
                module='investment',
                template_name='daily_report.html',
                context=template_data
            )

        except Exception as e:
            print(f"[InvestmentNotifier] ⚠️ EmailRenderer 渲染失败，使用备用方案: {e}")
            import traceback
            traceback.print_exc()
            return self._render_email_html_fallback(data, analysis, market_type)

    def _render_email_html_fallback(
        self,
        data: CollectedData,
        analysis: AnalysisResult,
        market_type: str,
    ) -> str:
        """
        渲染投资简报邮件 HTML（备用方案，使用内联 HTML）

        Args:
            data: 收集的投资数据
            analysis: AI 分析结果
            market_type: 市场类型

        Returns:
            HTML 内容字符串
        """
        market_name = "A股/港股" if market_type == "cn" else "美股"

        # 构建指数行情表格
        indices_html = self._render_indices_table(data)

        # 构建个股行情表格
        stocks_html = self._render_stocks_table(data)

        # 构建加密货币行情
        crypto_html = self._render_crypto_section(data)

        # 构建北向资金
        northbound_html = self._render_northbound_section(data)

        # 构建新闻列表
        news_html = self._render_news_section(data)

        # AI 分析内容
        analysis_html = ""
        if analysis.success and analysis.content:
            analysis_html = self._markdown_to_html(analysis.content)
        else:
            analysis_html = f"<p style='color: #999;'>AI 分析未生成: {analysis.error or '未启用'}</p>"

        html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>每日投资简报 - {data.date}</title>
    <style>
        * {{
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            margin: 0;
            padding: 2px;
            background-color: #fff;
            font-size: 14px;
        }}
        .container {{
            background: white;
            padding: 6px;
        }}
        .header {{
            border-bottom: 3px solid #1a73e8;
            padding-bottom: 15px;
            margin-bottom: 20px;
        }}
        .header h1 {{
            font-size: 20px;
            font-weight: 700;
            color: #1a1a1a;
            margin: 0 0 8px 0;
        }}
        .header .meta {{
            color: #666;
            font-size: 13px;
        }}
        .header .meta span {{
            display: inline-block;
            margin-right: 15px;
        }}
        .section {{
            margin: 20px 0;
        }}
        .section-title {{
            font-size: 16px;
            font-weight: 600;
            color: #1a1a1a;
            margin-bottom: 12px;
            padding-bottom: 8px;
            border-bottom: 1px solid #eee;
        }}
        /* 行内数据显示 */
        .data-inline {{
            font-size: 13px;
            line-height: 1.8;
        }}
        .data-inline .item {{
            display: inline-block;
            margin-right: 12px;
            white-space: nowrap;
        }}
        .data-inline .name {{
            font-weight: 600;
            color: #333;
        }}
        .data-inline .price {{
            font-family: 'Monaco', 'Menlo', monospace;
            margin: 0 4px;
        }}
        .up {{ color: #e53935; }}
        .down {{ color: #43a047; }}
        .flat {{ color: #666; }}
        /* AI 分析区域 */
        .analysis {{
            background: #f8f9fa;
            border-radius: 8px;
            padding: 15px;
            margin-top: 15px;
        }}
        .analysis h2, .analysis h3 {{
            color: #1a73e8;
            font-size: 15px;
            margin: 18px 0 8px 0;
        }}
        .analysis h2:first-child, .analysis h3:first-child {{
            margin-top: 0;
        }}
        .analysis ul {{
            padding-left: 18px;
            margin: 8px 0;
        }}
        .analysis li {{
            margin: 6px 0;
        }}
        .analysis p {{
            margin: 8px 0;
        }}
        .footer {{
            margin-top: 25px;
            padding-top: 15px;
            border-top: 1px solid #eee;
            font-size: 11px;
            color: #999;
            text-align: center;
        }}
        .disclaimer {{
            background: #fff3cd;
            border: 1px solid #ffc107;
            border-radius: 8px;
            padding: 12px;
            margin-top: 15px;
            font-size: 12px;
            color: #856404;
        }}
        /* 新闻列表 */
        .news-list {{
            font-size: 13px;
            line-height: 1.6;
        }}
        .news-list li {{
            margin: 4px 0;
            padding-left: 0;
        }}
        .news-list a {{
            color: #1a73e8;
            text-decoration: none;
        }}
        .news-list .src {{
            color: #999;
            font-size: 11px;
        }}
        .news-list .time {{
            color: #666;
            font-size: 11px;
            margin-left: 8px;
        }}
        /* 移动端优化 */
        @media (max-width: 600px) {{
            body {{ padding: 4px; font-size: 13px; }}
            .container {{ padding: 8px; }}
            .header {{ padding-bottom: 8px; margin-bottom: 10px; }}
            .header h1 {{ font-size: 16px; }}
            .header .meta {{ font-size: 11px; }}
            .section {{ margin: 10px 0; }}
            .section-title {{ font-size: 14px; margin-bottom: 6px; }}
            .news-list {{ padding-left: 18px; }}
            .analysis {{ padding: 8px; }}
            .analysis h2, .analysis h3 {{ font-size: 13px; }}
            .disclaimer {{ padding: 6px; font-size: 11px; }}
            .footer {{ font-size: 10px; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>每日投资简报</h1>
            <div class="meta">
                <span>📅 {data.date}</span>
                <span style="margin-left: 20px;">⏰ 数据更新时间: {data.timestamp}</span>
            </div>
        </div>

        {indices_html}

        {stocks_html}

        {crypto_html}

        {northbound_html}

        {news_html}

        <div class="section">
            <h2 class="section-title">🤖 AI 分析</h2>
            <div class="analysis">
                {analysis_html}
            </div>
        </div>

        <div class="disclaimer">
            ⚠️ <strong>免责声明</strong>：本简报仅供参考，不构成任何投资建议。投资有风险，入市需谨慎。数据来源于公开市场信息，可能存在延迟或误差。
        </div>

        <div class="footer">
            <p>由 TrendRadar 投资监控自动生成</p>
            <p>生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
        </div>
    </div>
</body>
</html>"""

        return html_content

    def _render_indices_table(self, data: CollectedData) -> str:
        """渲染指数行情（行内紧凑显示）"""
        if not data.market_snapshot or not data.market_snapshot.indices:
            return ""

        items = []
        for idx in data.market_snapshot.indices:
            cls = "up" if idx.change_pct > 0 else ("down" if idx.change_pct < 0 else "flat")
            sign = "+" if idx.change_pct > 0 else ""
            items.append(f'<span class="item"><span class="name">{self._escape_html(idx.name)}</span> <span class="price">{idx.price:,.0f}</span> <span class="{cls}">{sign}{idx.change_pct:.2f}%</span></span>')

        return f"""
        <div class="section">
            <h2 class="section-title">📊 主要指数</h2>
            <div class="data-inline">{" ".join(items)}</div>
        </div>"""

    def _render_stocks_table(self, data: CollectedData) -> str:
        """渲染个股行情（行内紧凑显示）"""
        if not data.market_snapshot or not data.market_snapshot.stocks:
            return ""

        items = []
        for s in data.market_snapshot.stocks:
            cls = "up" if s.change_pct > 0 else ("down" if s.change_pct < 0 else "flat")
            sign = "+" if s.change_pct > 0 else ""
            items.append(f'<span class="item"><span class="name">{self._escape_html(s.name)}</span> <span class="price">{s.price:,.2f}</span> <span class="{cls}">{sign}{s.change_pct:.2f}%</span></span>')

        return f"""
        <div class="section">
            <h2 class="section-title">📈 关注个股</h2>
            <div class="data-inline">{" ".join(items)}</div>
        </div>"""

    def _render_crypto_section(self, data: CollectedData) -> str:
        """渲染加密货币行情（行内紧凑显示）"""
        if not data.market_snapshot or not data.market_snapshot.crypto:
            return ""

        items = []
        for c in data.market_snapshot.crypto:
            cls = "up" if c.change_pct_24h > 0 else ("down" if c.change_pct_24h < 0 else "flat")
            sign = "+" if c.change_pct_24h > 0 else ""
            items.append(f'<span class="item"><span class="name">{c.symbol}</span> <span class="price">${c.price_usd:,.0f}</span> <span class="{cls}">{sign}{c.change_pct_24h:.1f}%</span></span>')

        return f"""
        <div class="section">
            <h2 class="section-title">🪙 加密货币</h2>
            <div class="data-inline">{" ".join(items)}</div>
        </div>"""

    def _render_northbound_section(self, data: CollectedData) -> str:
        """渲染北向资金（行内显示）"""
        if not data.market_snapshot or not data.market_snapshot.northbound:
            return ""

        nb = data.market_snapshot.northbound
        if nb.sh_connect == 0 and nb.sz_connect == 0 and nb.total == 0:
            return ""

        def fmt(val):
            cls = "up" if val > 0 else ("down" if val < 0 else "flat")
            sign = "+" if val > 0 else ""
            return f'<span class="{cls}">{sign}{val:.1f}亿</span>'

        return f"""
        <div class="section">
            <h2 class="section-title">💹 北向资金</h2>
            <div class="data-inline">
                <span class="item">沪股通 {fmt(nb.sh_connect)}</span>
                <span class="item">深股通 {fmt(nb.sz_connect)}</span>
                <span class="item"><strong>合计 {fmt(nb.total)}</strong></span>
            </div>
        </div>"""

    def _render_news_section(self, data: CollectedData) -> str:
        """渲染新闻列表（简洁列表格式，包含时间）"""
        if not data.news:
            return ""

        items = []
        now = datetime.now()

        for item in data.news[:10]:
            src = self._escape_html(item.source)
            title = self._escape_html(item.title)
            url = self._escape_html(item.url)

            # 格式化发布时间
            time_str = ""
            if item.published:
                time_str = self._format_news_time(item.published, now)

            items.append(f'<li><a href="{url}" target="_blank">{title}</a> <span class="src">[{src}]</span>{time_str}</li>')

        return f"""
        <div class="section">
            <h2 class="section-title">📰 财经要闻</h2>
            <ul class="news-list">{"".join(items)}</ul>
        </div>"""

    def _format_news_time(self, published: str, now: datetime) -> str:
        """
        格式化新闻时间为相对时间或绝对时间（用于fallback渲染）

        规则：
        - 当日（24小时内）：显示"X小时前"
        - 其他：显示"YYYY-MM-DD"

        Args:
            published: 发布时间字符串
            now: 当前时间

        Returns:
            HTML格式的时间字符串
        """
        time_text = self._format_news_time_text(published, now)
        if time_text:
            return f'<span class="time">{time_text}</span>'
        return ""

    def _format_news_time_text(self, published: str, now: datetime) -> str:
        """
        格式化新闻时间为纯文本（用于Jinja2模板）

        规则：
        - 当日（24小时内）：显示"X小时前"
        - 其他：显示"YYYY-MM-DD"

        Args:
            published: 发布时间字符串
            now: 当前时间

        Returns:
            纯文本格式的时间字符串
        """
        if not published:
            return ""

        try:
            # 解析时间
            pub_time = None
            has_date = False  # 标记是否包含日期信息

            if 'T' in published:
                # ISO格式带时区: "2026-02-06T14:30:00+08:00"
                pub_time = datetime.fromisoformat(published.replace("Z", "+00:00"))
                has_date = True
            elif '-' in published and ':' in published:
                # 检查是否是完整的日期时间格式
                parts = published.split('-')
                if len(parts) >= 3 and parts[0].isdigit() and len(parts[0]) == 4:
                    # 完整日期时间: "2026-02-06 14:30:00"
                    pub_time = datetime.fromisoformat(published)
                    has_date = True
                else:
                    # 只有时间，使用-作为分隔符: "15-31"
                    # 无法确定日期，直接返回原始时间
                    return published
            elif '-' in published and published.count('-') == 1 and published.replace('-', '').isdigit():
                # 格式: "15-31" (使用-作为时分分隔符)
                # 只有时间，没有日期，无法判断是哪一天，直接返回原始时间
                return published
            elif ':' in published:
                # 只有时间: "14:30"
                # 无法确定日期，直接返回原始时间
                return published
            else:
                # 无法识别的格式，返回原始值
                return published

            if pub_time:
                # 计算时间差
                time_diff = (now - pub_time).total_seconds()

                # 24小时内，显示"X小时前"
                if time_diff < 86400:  # 24小时 = 86400秒
                    hours = int(time_diff / 3600)
                    if hours == 0:
                        return "刚刚"
                    elif hours == 1:
                        return "1小时前"
                    else:
                        return f"{hours}小时前"
                else:
                    # 超过24小时，显示日期
                    return pub_time.strftime("%Y-%m-%d")

        except Exception as e:
            # 解析失败，显示原始字符串
            return published

        return ""

    def _escape_html(self, text: str) -> str:
        """转义 HTML 特殊字符"""
        return html.escape(str(text)) if text else ""

    def _markdown_to_html(self, markdown_text: str) -> str:
        """
        简单的 Markdown 转 HTML

        支持：标题、列表、粗体、斜体、分隔线
        """
        if not markdown_text:
            return ""

        html_text = markdown_text

        # 转义 HTML（但保留一些必要的标记）
        html_text = self._escape_html(html_text)

        # 分隔线
        html_text = re.sub(r'^---+$', '<hr style="margin: 20px 0; border: none; border-top: 1px solid #ddd;">', html_text, flags=re.MULTILINE)

        # 标题 (### -> h3, ## -> h2)
        html_text = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html_text, flags=re.MULTILINE)
        html_text = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html_text, flags=re.MULTILINE)

        # 粗体
        html_text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html_text)

        # 斜体
        html_text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html_text)

        # 无序列表
        html_text = re.sub(r'^- (.+)$', r'<li>\1</li>', html_text, flags=re.MULTILINE)

        # 将连续的 li 包装在 ul 中
        lines = html_text.split('\n')
        result = []
        in_list = False
        for line in lines:
            if line.strip().startswith('<li>'):
                if not in_list:
                    result.append('<ul>')
                    in_list = True
                result.append(line)
            else:
                if in_list:
                    result.append('</ul>')
                    in_list = False
                result.append(line)
        if in_list:
            result.append('</ul>')
        html_text = '\n'.join(result)

        # 段落
        html_text = re.sub(r'\n\n+', '</p><p>', html_text)
        html_text = f'<p>{html_text}</p>'

        # 清理多余的标签
        html_text = html_text.replace('<p></p>', '')
        html_text = html_text.replace('<p><h2>', '<h2>')
        html_text = html_text.replace('</h2></p>', '</h2>')
        html_text = html_text.replace('<p><h3>', '<h3>')
        html_text = html_text.replace('</h3></p>', '</h3>')
        html_text = html_text.replace('<p><ul>', '<ul>')
        html_text = html_text.replace('</ul></p>', '</ul>')
        html_text = html_text.replace('<p><hr', '<hr')
        html_text = html_text.replace('/></p>', '/>')

        return html_text

    @staticmethod
    def _normalize_config(config: Dict[str, Any]) -> Dict[str, Any]:
        """将配置键名转为小写"""
        def lower_keys(d):
            if isinstance(d, dict):
                return {k.lower(): lower_keys(v) for k, v in d.items()}
            elif isinstance(d, list):
                return [lower_keys(item) for item in d]
            return d
        return lower_keys(config)

    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> "InvestmentNotifier":
        """
        从配置字典创建通知器

        Args:
            config: 完整配置字典（支持 load_config 输出的扁平格式）

        Returns:
            InvestmentNotifier 实例
        """
        # 获取投资模块的通知配置
        investment_config = config.get("INVESTMENT", config.get("investment", {}))
        notification_config = investment_config.get("NOTIFICATION", investment_config.get("notification", {}))
        # 转为小写键
        notification_config = cls._normalize_config(notification_config)

        # 获取邮件配置（load_config 输出扁平格式：EMAIL_FROM, EMAIL_PASSWORD 等）
        email_config = {
            "from": config.get("EMAIL_FROM", ""),
            "password": config.get("EMAIL_PASSWORD", ""),
            "to": config.get("EMAIL_TO", ""),
            "smtp_server": config.get("EMAIL_SMTP_SERVER", ""),
            "smtp_port": config.get("EMAIL_SMTP_PORT", ""),
        }

        # 获取时区配置（load_config 也是扁平格式）
        timezone = config.get("TIMEZONE", "Asia/Shanghai")

        return cls(
            notification_config=notification_config,
            email_config=email_config,
            timezone=timezone,
        )
