"""
邮件通知器 - 发送每日报告和账号提醒
"""

import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr
from datetime import datetime
from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape
import markdown

from .models import DailyReport, Article, Topic
from .config_loader import ConfigLoader, EmailConfig

logger = logging.getLogger(__name__)


# SMTP 服务器自动识别
SMTP_SERVERS = {
    '163.com': ('smtp.163.com', 465),
    '126.com': ('smtp.126.com', 465),
    'qq.com': ('smtp.qq.com', 465),
    'gmail.com': ('smtp.gmail.com', 587),
    'outlook.com': ('smtp-mail.outlook.com', 587),
    'hotmail.com': ('smtp-mail.outlook.com', 587),
    'yahoo.com': ('smtp.mail.yahoo.com', 465),
}


class WechatNotifier:
    """微信公众号邮件通知器"""
    
    def __init__(self, config: ConfigLoader):
        self.config = config
        self.email_config: EmailConfig = config.email
        
        # 初始化模板引擎
        template_dir = Path("templates")
        if template_dir.exists():
            self.jinja_env = Environment(
                loader=FileSystemLoader(str(template_dir)),
                autoescape=select_autoescape(['html', 'xml'])
            )
        else:
            self.jinja_env = None
    
    def send_daily_report(self, report: DailyReport) -> bool:
        """
        发送每日报告邮件
        
        Args:
            report: 每日报告数据
        
        Returns:
            是否发送成功
        """
        if not self._validate_email_config():
            logger.error("邮件配置不完整")
            return False
        
        # 生成 HTML 内容
        html_content = self._render_daily_report(report)
        
        # 保存 HTML 文件
        output_dir = Path(self.config.storage.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        filename = f"wechat_daily_{report.date.strftime('%Y%m%d_%H%M%S')}.html"
        html_path = output_dir / filename
        html_path.write_text(html_content, encoding='utf-8')
        logger.info(f"报告已保存: {html_path}")
        
        # 发送邮件
        subject = f"📱 微信公众号日报 - {report.date.strftime('%Y-%m-%d')}"
        
        return self._send_email(
            subject=subject,
            html_content=html_content,
            text_content=self._render_daily_report_text(report)
        )
    
    def send_account_alert(self, account_name: str, external_url: str = "", message: str = "") -> bool:
        """
        发送账号失效提醒
        
        Args:
            account_name: 账号名称
            external_url: Wewe-RSS 外部访问地址
            message: 自定义提示消息（可选）
        
        Returns:
            是否发送成功
        """
        if not self._validate_email_config():
            logger.error("邮件配置不完整")
            return False
        
        # 使用自定义消息或默认消息
        alert_message = message or f"您的微信读书账号 <strong>{account_name}</strong> 登录状态已失效，公众号订阅服务将无法正常获取文章。"
        text_alert = message or f"您的微信读书账号 {account_name} 登录状态已失效，公众号订阅服务将无法正常获取文章。"
        
        subject = "⚠️ 微信公众号订阅服务异常提醒"
        
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>服务异常提醒</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f5f5f5;">
    <div style="background-color: #fff; border-radius: 12px; padding: 30px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
        <h1 style="color: #ff6b6b; margin-top: 0;">⚠️ 服务异常提醒</h1>
        
        <p style="font-size: 16px; color: #333; line-height: 1.6;">
            {alert_message}
        </p>
        
        <p style="font-size: 16px; color: #333; line-height: 1.6;">
            请按以下步骤处理：
        </p>
        
        <ol style="font-size: 15px; color: #555; line-height: 1.8;">
            <li>访问 Wewe-RSS 后台：<a href="{external_url}" style="color: #07c160;">{external_url}</a></li>
            <li>检查服务状态和账号登录情况</li>
            <li>如需重新登录，使用微信扫码</li>
            <li><strong>注意：不要勾选"24小时后自动退出"</strong></li>
        </ol>
        
        <div style="background-color: #fff3cd; border-radius: 8px; padding: 15px; margin-top: 20px;">
            <p style="margin: 0; color: #856404; font-size: 14px;">
                💡 提示：微信读书的登录状态通常在 2-3 天后失效，届时需要重新扫码。
            </p>
        </div>
        
        <p style="font-size: 14px; color: #999; margin-top: 30px; border-top: 1px solid #eee; padding-top: 15px;">
            此邮件由微信公众号订阅服务自动发送<br>
            发送时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        </p>
    </div>
</body>
</html>
"""
        
        text_content = f"""
服务异常提醒

{text_alert}

请按以下步骤处理：
1. 访问 Wewe-RSS 后台：{external_url}
2. 检查服务状态和账号登录情况
3. 如需重新登录，使用微信扫码
4. 注意：不要勾选"24小时后自动退出"

提示：微信读书的登录状态通常在 2-3 天后失效，届时需要重新扫码。
"""
        
        return self._send_email(
            subject=subject,
            html_content=html_content,
            text_content=text_content
        )
    
    def _validate_email_config(self) -> bool:
        """验证邮件配置"""
        return all([
            self.email_config.from_addr,
            self.email_config.password,
            self.email_config.to_addr
        ])
    
    def _get_smtp_server(self) -> tuple:
        """获取 SMTP 服务器配置"""
        # 如果配置了自定义服务器
        if self.email_config.smtp_server and self.email_config.smtp_port:
            return (self.email_config.smtp_server, int(self.email_config.smtp_port))
        
        # 自动识别
        email_domain = self.email_config.from_addr.split('@')[-1].lower()
        
        for domain, server_info in SMTP_SERVERS.items():
            if domain in email_domain:
                return server_info
        
        # 默认使用 SSL 端口
        return (f"smtp.{email_domain}", 465)
    
    def _send_email(
        self,
        subject: str,
        html_content: str,
        text_content: str
    ) -> bool:
        """发送邮件"""
        try:
            smtp_server, smtp_port = self._get_smtp_server()
            
            # 创建邮件
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = formataddr(('微信公众号订阅', self.email_config.from_addr))
            msg['To'] = self.email_config.to_addr
            
            # 添加纯文本和 HTML 内容
            msg.attach(MIMEText(text_content, 'plain', 'utf-8'))
            msg.attach(MIMEText(html_content, 'html', 'utf-8'))
            
            # 发送
            if smtp_port == 465:
                # SSL
                with smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=30) as server:
                    server.login(self.email_config.from_addr, self.email_config.password)
                    server.sendmail(
                        self.email_config.from_addr,
                        self.email_config.to_addr.split(','),
                        msg.as_string()
                    )
            else:
                # TLS
                with smtplib.SMTP(smtp_server, smtp_port, timeout=30) as server:
                    server.starttls()
                    server.login(self.email_config.from_addr, self.email_config.password)
                    server.sendmail(
                        self.email_config.from_addr,
                        self.email_config.to_addr.split(','),
                        msg.as_string()
                    )
            
            logger.info(f"邮件发送成功: {subject}")
            return True
            
        except Exception as e:
            logger.error(f"邮件发送失败: {e}")
            return False
    
    def _render_daily_report(self, report: DailyReport) -> str:
        """渲染每日报告 HTML（使用统一的 EmailRenderer）"""
        # 使用报告中的 all_articles（已在 analyzer 中排序）
        all_articles = report.all_articles if hasattr(report, 'all_articles') else []
        
        # 如果 all_articles 为空，尝试从 topics 中提取
        if not all_articles:
            seen_ids = set()
            for article in report.critical_articles:
                if article.id not in seen_ids:
                    all_articles.append(article)
                    seen_ids.add(article.id)
            for topic in report.topics:
                for article in topic.articles:
                    if article.id not in seen_ids:
                        all_articles.append(article)
                        seen_ids.add(article.id)
            all_articles.sort(key=lambda a: (a.feed_name, a.title))
        
        # 尝试使用统一的 EmailRenderer
        try:
            import sys
            from pathlib import Path
            
            # 添加 shared 目录到 Python 路径（wechat 模块位于子目录）
            project_root = Path(__file__).parent.parent.parent
            sys.path.insert(0, str(project_root))
            
            from shared.lib.email_renderer import EmailRenderer
            
            renderer = EmailRenderer()
            
            # 准备模板数据 - 将 DailyReport 对象转换为可序列化的格式
            # 模板期望的结构与 DailyReport 对象基本一致
            template_data = {
                "report": {
                    "date": report.date.strftime('%Y-%m-%d') if hasattr(report.date, 'strftime') else str(report.date),
                    "total_articles": report.total_articles,
                    "critical_count": report.critical_count,
                    "normal_count": report.normal_count,
                    "critical_articles": [
                        {
                            "id": a.id,
                            "title": a.title,
                            "url": a.url,
                            "feed_name": a.feed_name,
                            "ai_summary": a.ai_summary,
                            "published_at": a.published_at.isoformat() if hasattr(a.published_at, 'isoformat') and a.published_at else None,
                        }
                        for a in report.critical_articles
                    ],
                    "topics": [
                        {
                            "name": t.name,
                            "description": t.description,
                            "ai_analysis": t.ai_analysis,
                            "highlight": getattr(t, 'highlight', None),
                            "data_numbers": [
                                {"content": dn.content, "context": dn.context, "source": dn.source}
                                for dn in getattr(t, 'data_numbers', []) or []
                            ],
                            "events_news": [
                                {"content": en.content, "time": en.time, "parties": en.parties, "source": en.source}
                                for en in getattr(t, 'events_news', []) or []
                            ],
                            "insider_insights": [
                                {"content": ii.content, "insight_type": ii.insight_type, "source": ii.source}
                                for ii in getattr(t, 'insider_insights', []) or []
                            ],
                            "key_dates": getattr(t, 'key_dates', None),
                            "sources": [
                                {"title": s.title, "key_contribution": s.key_contribution, "url": s.url, "feed_name": s.feed_name}
                                for s in getattr(t, 'sources', []) or []
                            ],
                            "articles": [
                                {
                                    "id": a.id,
                                    "title": a.title,
                                    "url": a.url,
                                    "feed_name": a.feed_name,
                                    "ai_summary": a.ai_summary,
                                    "published_at": a.published_at.isoformat() if hasattr(a.published_at, 'isoformat') and a.published_at else None,
                                }
                                for a in t.articles
                            ] if hasattr(t, 'articles') else [],
                        }
                        for t in report.topics
                    ],
                },
                "all_articles": [
                    {
                        "id": a.id,
                        "title": a.title,
                        "url": a.url,
                        "feed_name": a.feed_name,
                        "ai_summary": a.ai_summary,
                        "published_at": a.published_at.isoformat() if hasattr(a.published_at, 'isoformat') and a.published_at else None,
                    }
                    for a in all_articles
                ],
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            
            logger.info("[WechatNotifier] 使用 EmailRenderer 渲染邮件...")
            return renderer.render_module_email(
                module='wechat',
                template_name='daily_report.html',
                context=template_data
            )
            
        except Exception as e:
            logger.warning(f"[WechatNotifier] ⚠️ EmailRenderer 渲染失败，使用备用方案: {e}")
            import traceback
            traceback.print_exc()
        
        # 尝试使用本地 Jinja2 模板（旧方式）
        if self.jinja_env:
            try:
                template = self.jinja_env.get_template("daily_report.html")
                return template.render(
                    report=report,
                    all_articles=all_articles,
                    now=datetime.now()
                )
            except Exception as e:
                logger.warning(f"本地模板渲染失败，使用内置模板: {e}")
        
        # 使用内置模板
        return self._builtin_daily_report_template(report)
    
    def _builtin_daily_report_template(self, report: DailyReport) -> str:
        """内置的每日报告 HTML 模板"""
        
        # 第一类文章 HTML
        critical_html = ""
        for article in report.critical_articles:
            summary_html = ""
            if article.ai_summary:
                # 转换 Markdown 为 HTML
                summary_html = markdown.markdown(article.ai_summary)
            
            critical_html += f"""
            <div style="background-color: #fff; border-radius: 12px; padding: 20px; margin-bottom: 15px; box-shadow: 0 2px 8px rgba(0,0,0,0.05);">
                <div style="font-size: 12px; color: #07c160; margin-bottom: 8px;">{article.feed_name}</div>
                <h3 style="margin: 0 0 10px 0; font-size: 16px;">
                    <a href="{article.url}" style="color: #333; text-decoration: none;">{article.title}</a>
                </h3>
                {f'<div style="background-color: #f8f9fa; border-radius: 8px; padding: 12px; font-size: 14px; color: #555; line-height: 1.6;">{summary_html}</div>' if summary_html else ''}
            </div>
            """
        
        # 第二类话题 HTML
        topics_html = ""
        for topic in report.topics:
            articles_list = "".join([
                f'<li><a href="{a.url}" style="color: #555; text-decoration: none;">{a.title}</a> <span style="color: #999; font-size: 12px;">({a.feed_name})</span></li>'
                for a in topic.articles
            ])
            
            topics_html += f"""
            <div style="background-color: #fff; border-radius: 12px; padding: 20px; margin-bottom: 15px; box-shadow: 0 2px 8px rgba(0,0,0,0.05);">
                <h3 style="margin: 0 0 5px 0; font-size: 16px; color: #333;">📌 {topic.name}</h3>
                <p style="margin: 0 0 15px 0; font-size: 14px; color: #666;">{topic.description}</p>
                
                <ul style="margin: 0 0 15px 0; padding-left: 20px; font-size: 14px; line-height: 1.8;">
                    {articles_list}
                </ul>
                
                {f'<div style="background-color: #e8f5e9; border-radius: 8px; padding: 12px; font-size: 14px; color: #2e7d32; line-height: 1.6;">{topic.ai_analysis}</div>' if topic.ai_analysis else ''}
            </div>
            """
        
        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>微信公众号日报 - {report.date.strftime('%Y-%m-%d')}</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 0; background-color: #f5f5f5;">
    <div style="max-width: 680px; margin: 0 auto; padding: 20px;">
        <!-- 头部 -->
        <div style="background: linear-gradient(135deg, #07c160 0%, #09bb07 100%); border-radius: 12px; padding: 25px; margin-bottom: 20px; color: #fff;">
            <h1 style="margin: 0 0 10px 0; font-size: 22px;">📱 微信公众号日报</h1>
            <p style="margin: 0; font-size: 14px; opacity: 0.9;">{report.date.strftime('%Y年%m月%d日')}</p>
            <div style="margin-top: 15px; font-size: 13px; opacity: 0.8;">
                共收录 {report.total_articles} 篇文章 | 重点 {report.critical_count} 篇 | 资讯 {report.normal_count} 篇
            </div>
        </div>
        
        <!-- 第一类：重点文章 -->
        {f'''
        <div style="margin-bottom: 25px;">
            <h2 style="font-size: 18px; color: #333; margin: 0 0 15px 0; padding-bottom: 10px; border-bottom: 2px solid #07c160;">
                🔥 重点文章
            </h2>
            {critical_html}
        </div>
        ''' if report.critical_articles else ''}
        
        <!-- 第二类：话题聚合 -->
        {f'''
        <div style="margin-bottom: 25px;">
            <h2 style="font-size: 18px; color: #333; margin: 0 0 15px 0; padding-bottom: 10px; border-bottom: 2px solid #07c160;">
                📰 今日话题
            </h2>
            {topics_html}
        </div>
        ''' if report.topics else ''}
        
        <!-- 页脚 -->
        <div style="text-align: center; font-size: 12px; color: #999; padding: 20px 0;">
            由微信公众号订阅服务自动生成<br>
            {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        </div>
    </div>
</body>
</html>
"""
    
    def _render_daily_report_text(self, report: DailyReport) -> str:
        """渲染每日报告纯文本版"""
        lines = [
            f"📱 微信公众号日报 - {report.date.strftime('%Y-%m-%d')}",
            f"共收录 {report.total_articles} 篇文章",
            "",
        ]
        
        if report.critical_articles:
            lines.append("🔥 重点文章")
            lines.append("-" * 40)
            for article in report.critical_articles:
                lines.append(f"\n【{article.feed_name}】{article.title}")
                lines.append(f"链接: {article.url}")
                if article.ai_summary:
                    lines.append(f"摘要: {article.ai_summary[:200]}...")
            lines.append("")
        
        if report.topics:
            lines.append("📰 今日话题")
            lines.append("-" * 40)
            for topic in report.topics:
                lines.append(f"\n📌 {topic.name}")
                lines.append(f"   {topic.description}")
                for a in topic.articles:
                    lines.append(f"   - {a.title}")
                if topic.ai_analysis:
                    lines.append(f"   分析: {topic.ai_analysis[:200]}...")
        
        return "\n".join(lines)
