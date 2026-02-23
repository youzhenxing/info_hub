# coding=utf-8
"""
每日日志通知发送器

每天23:30发送系统运行日志汇总邮件
"""
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import subprocess


class DailyLogNotifier:
    """每日日志通知发送器"""

    def __init__(self, config: dict):
        """
        初始化

        Args:
            config: 包含 notification 配置的字典
        """
        self.config = config

        # 邮件配置 - load_config() 返回 flat dict，EMAIL_FROM 等为顶层 key
        self.email_from = config.get('EMAIL_FROM', '')
        self.email_password = config.get('EMAIL_PASSWORD', '')
        self.email_to = config.get('EMAIL_TO', '')

    def send_daily_log(self, date: Optional[datetime] = None) -> bool:
        """
        发送每日日志邮件

        Args:
            date: 日期，默认今天

        Returns:
            是否发送成功
        """
        date = date or datetime.now()

        # 1. 收集数据
        context = self._collect_data(date)

        # 2. 渲染模板
        html_content = self._render_template(context)
        if not html_content:
            print("[DailyLogNotifier] ❌ 模板渲染失败")
            return False

        # 3. 保存HTML
        html_file = self._save_html(html_content, date)

        # 4. 发送邮件
        return self._send_email(html_file, date)

    def _collect_data(self, date: datetime) -> dict:
        """收集日志数据"""
        return {
            'date': date.strftime('%Y-%m-%d'),
            'now': date,
            'monitor_status': self._get_monitor_status(),
            'wewe_status': self._get_wewe_status(),
            'module_status': self._get_module_status(date),
            'schedule_config': self._get_schedule_config(),
            'podcast_logs': self._get_podcast_logs(date),
            'git_commits': self._get_git_commits(5),
            'system_logs': self._get_system_logs(date),
            'module_names': {
                'podcast': '播客模块',
                'investment': '投资模块',
                'community': '社区模块',
                'wechat': '公众号模块',
            },
            'module_icons': {
                'podcast': '🎙️',
                'investment': '📈',
                'community': '🌐',
                'wechat': '📱',
            },
        }

    def _get_monitor_status(self) -> dict:
        """获取监控服务状态"""
        return {
            'development': {
                'running': self._check_port(8088),
                'port': 8088,
            },
            'production': {
                'running': self._check_port(8089),
                'port': 8089,
            },
        }

    def _check_port(self, port: int) -> bool:
        """检查端口是否在监听"""
        try:
            import socket
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                return s.connect_ex(('localhost', port)) == 0
        except Exception:
            return False

    def _get_wewe_status(self) -> Optional[dict]:
        """获取Wewe-RSS状态"""
        try:
            import requests
            wewe_config = self.config.get('wewe_rss', self.config.get('WEWE_RSS', {}))
            base_url = wewe_config.get('base_url', 'http://localhost:4000')

            # 检查服务
            response = requests.get(f"{base_url}/feeds", timeout=5)
            feeds_count = len(response.json()) if response.ok else 0

            return {
                'service': {
                    'running': response.ok,
                    'feeds': feeds_count,
                },
            }
        except Exception:
            return None

    def _get_module_status(self, date: datetime) -> List[dict]:
        """获取今日模块运行记录"""
        try:
            from trendradar.core.status import StatusDB
            monitor_config = self.config.get('MONITOR', self.config.get('monitor', {}))
            db_path = monitor_config.get('STATUS_DB', 'output/system/status.db')
            db = StatusDB(db_path)

            modules = ['podcast', 'investment', 'community', 'wechat']
            status_list = []

            for module in modules:
                last_run = db.get_last_run(module)
                if last_run:
                    status_list.append({
                        'module': module,
                        'status': last_run.get('status', 'unknown'),
                        'started_at': last_run.get('started_at', ''),
                    })

            return status_list
        except Exception as e:
            print(f"[DailyLogNotifier] 获取模块状态失败: {e}")
            return []

    def _get_schedule_config(self) -> dict:
        """获取调度配置"""
        return self.config.get('SCHEDULE', self.config.get('schedule', {}))

    def _get_podcast_logs(self, date: datetime) -> List[str]:
        """获取今日播客处理记录"""
        try:
            log_file = Path(f"logs/podcast_{date.strftime('%Y%m%d')}.log")
            if log_file.exists():
                lines = log_file.read_text().split('\n')
                # 返回最后50行
                return lines[-50:]
            return []
        except Exception:
            return []

    def _get_git_commits(self, limit: int = 5) -> List[dict]:
        """获取最近Git提交"""
        try:
            result = subprocess.run(
                ['git', 'log', f'-{limit}', '--format=%h|%s|%cr'],
                capture_output=True, text=True, timeout=5
            )
            commits = []
            for line in result.stdout.strip().split('\n'):
                if '|' in line:
                    parts = line.split('|', 2)
                    commits.append({
                        'hash': parts[0],
                        'message': parts[1] if len(parts) > 1 else '',
                        'time': parts[2] if len(parts) > 2 else '',
                    })
            return commits
        except Exception:
            return []

    def _get_system_logs(self, date: datetime) -> List[str]:
        """获取系统日志"""
        try:
            log_file = Path("logs/daily_report.log")
            if log_file.exists():
                lines = log_file.read_text().split('\n')
                # 过滤今天的日志
                date_str = date.strftime('%Y-%m-%d')
                today_logs = [line for line in lines if date_str in line]
                return today_logs[-50:]
            return []
        except Exception:
            return []

    def _render_template(self, context: dict) -> Optional[str]:
        """渲染模板"""
        try:
            from shared.lib.email_renderer import EmailRenderer
            renderer = EmailRenderer()
            return renderer.render_module_email(
                module='monitor',
                template_name='daily_log.html',
                context=context
            )
        except Exception as e:
            print(f"[DailyLogNotifier] 模板渲染错误: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _save_html(self, html_content: str, date: datetime) -> Path:
        """保存HTML"""
        output_dir = Path('output/monitor')
        output_dir.mkdir(parents=True, exist_ok=True)

        html_file = output_dir / f"daily_log_{date.strftime('%Y%m%d')}.html"
        html_file.write_text(html_content, encoding='utf-8')

        print(f"[DailyLogNotifier] 💾 HTML已保存: {html_file}")
        return html_file

    def _send_email(self, html_file: Path, date: datetime) -> bool:
        """发送邮件"""
        try:
            from trendradar.notification.senders import send_to_email

            success = send_to_email(
                from_email=self.email_from,
                password=self.email_password,
                to_email=self.email_to,
                report_type=f'📋 TrendRadar 工作日志 - {date.strftime("%Y-%m-%d")}',
                html_file_path=str(html_file),
            )

            if success:
                print(f"[DailyLogNotifier] ✅ 日志邮件发送成功")
            else:
                print(f"[DailyLogNotifier] ❌ 日志邮件发送失败")

            return success
        except Exception as e:
            print(f"[DailyLogNotifier] 邮件发送错误: {e}")
            return False
