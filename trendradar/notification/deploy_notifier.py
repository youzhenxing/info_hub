# coding=utf-8
"""
发版通知发送器

在 test_e2e.py 或 run_all() 完成后发送汇总邮件
"""
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import subprocess


class DeployNotifier:
    """发版通知发送器"""

    def __init__(self, config: dict):
        """
        初始化

        Args:
            config: 包含 notification 配置的字典
        """
        self.config = config

        # 邮件配置 - 兼容大小写
        notification = config.get('notification', config.get('NOTIFICATION', {}))
        channels = notification.get('channels', {})
        email_config = channels.get('email', {})

        self.email_from = email_config.get('from', '')
        self.email_password = email_config.get('password', '')
        self.email_to = email_config.get('to', '')

    def send_deploy_notification(
        self,
        version: str,
        module_results: Dict[str, Dict],
        timestamp: Optional[datetime] = None,
    ) -> bool:
        """
        发送发版通知邮件

        Args:
            version: 版本号
            module_results: 模块执行结果，格式:
                {
                    "podcast": {"success": True, "message": "处理完成"},
                    "investment": {"success": True, "message": "邮件已发送"},
                    ...
                }
            timestamp: 时间戳

        Returns:
            是否发送成功
        """
        timestamp = timestamp or datetime.now()

        # 1. 构建模板上下文
        context = self._build_context(version, module_results, timestamp)

        # 2. 渲染模板
        html_content = self._render_template(context)
        if not html_content:
            print("[DeployNotifier] ❌ 模板渲染失败")
            return False

        # 3. 保存HTML文件
        html_file = self._save_html(html_content, timestamp)

        # 4. 发送邮件
        return self._send_email(html_file, version)

    def _build_context(
        self,
        version: str,
        module_results: Dict[str, Dict],
        timestamp: datetime
    ) -> dict:
        """构建模板上下文"""
        # 计算统计
        all_ok = all(r.get('success', False) for r in module_results.values())

        # 模块状态列表（用于模板渲染）
        module_status = []
        for name, result in module_results.items():
            module_status.append({
                'module': name,
                'status': 'success' if result.get('success') else 'failed',
                'message': result.get('message', ''),
                'started_at': result.get('started_at', ''),
            })

        # 获取Git提交
        git_commits = self._get_git_commits(5)

        # 获取调度配置
        schedule_config = self.config.get('SCHEDULE', self.config.get('schedule', {}))

        return {
            'version': version,
            'timestamp': timestamp,
            'all_ok': all_ok,
            'status_text': '全部成功' if all_ok else '部分失败',
            'module_status': module_status,
            'git_commits': git_commits,
            'schedule_config': schedule_config,
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
            'now': timestamp,
        }

    def _get_git_commits(self, limit: int = 5) -> List[dict]:
        """获取最近的Git提交"""
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
        except Exception as e:
            print(f"[DeployNotifier] 获取Git提交失败: {e}")
            return []

    def _render_template(self, context: dict) -> Optional[str]:
        """渲染邮件模板"""
        try:
            from shared.lib.email_renderer import EmailRenderer
            renderer = EmailRenderer()
            return renderer.render_module_email(
                module='deploy',
                template_name='deploy_notification.html',
                context=context
            )
        except Exception as e:
            print(f"[DeployNotifier] 模板渲染错误: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _save_html(self, html_content: str, timestamp: datetime) -> Path:
        """保存HTML到文件"""
        output_dir = Path('output/deploy')
        output_dir.mkdir(parents=True, exist_ok=True)

        html_file = output_dir / f"deploy_{timestamp.strftime('%Y%m%d_%H%M%S')}.html"
        html_file.write_text(html_content, encoding='utf-8')

        print(f"[DeployNotifier] 💾 HTML已保存: {html_file}")
        return html_file

    def _send_email(self, html_file: Path, version: str) -> bool:
        """发送邮件"""
        try:
            from trendradar.notification.senders import send_to_email

            success = send_to_email(
                from_email=self.email_from,
                password=self.email_password,
                to_email=self.email_to,
                report_type=f'🚀 TrendRadar 发版通知 v{version}',
                html_file_path=str(html_file),
            )

            if success:
                print(f"[DeployNotifier] ✅ 发版邮件发送成功")
            else:
                print(f"[DeployNotifier] ❌ 发版邮件发送失败")

            return success
        except Exception as e:
            print(f"[DeployNotifier] 邮件发送错误: {e}")
            return False
