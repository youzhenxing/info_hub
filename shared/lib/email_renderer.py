#!/usr/bin/env python3
"""
统一邮件渲染器

提供统一的邮件模板渲染功能，支持：
- Jinja2 模板引擎
- 自定义过滤器（Markdown 转换、数字格式化等）
- 模板继承和组件复用
- 响应式设计支持
"""

from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
from jinja2 import Environment, FileSystemLoader, select_autoescape
import markdown
import html
import re


class EmailRenderer:
    """统一邮件渲染器"""

    def __init__(self, template_base_dir: Optional[Path] = None):
        """
        初始化渲染器

        Args:
            template_base_dir: 模板根目录，默认为 shared/email_templates
        """
        if template_base_dir is None:
            # 默认相对于此文件的父目录的 email_templates
            template_base_dir = Path(__file__).parent.parent / "email_templates"

        self.template_dir = Path(template_base_dir)

        # 初始化 Jinja2 环境
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            autoescape=select_autoescape(['html', 'xml']),
        )

        # 注册自定义过滤器
        self._register_filters()

    def _register_filters(self):
        """注册自定义 Jinja2 过滤器"""

        def markdown_to_html(text: str) -> str:
            """
            Markdown 转 HTML

            Args:
                text: Markdown 格式文本

            Returns:
                HTML 格式文本
            """
            if not text:
                return ""

            # 处理转义的换行符（支持 JSON 中的 \\n）
            text = text.replace('\\n', '\n')

            # 清理 AI 输出中的元信息（不应出现在邮件中）
            # 移除"语言规则"、"输出语言"等开头段落
            lines = text.split('\n')
            filtered_lines = []
            skip_next = False

            for i, line in enumerate(lines):
                # 跳过包含"语言规则"、"原文语言为"的行
                if any(keyword in line for keyword in ['语言规则', '输出语言', '原文语言为', '**语言规则**']):
                    # 如果这一行后面跟着 <hr />，也跳过 hr
                    if i + 1 < len(lines) and '<hr />' in lines[i + 1]:
                        skip_next = True
                    continue

                if skip_next:
                    skip_next = False
                    continue

                filtered_lines.append(line)

            text = '\n'.join(filtered_lines)

            # 修复 AI 输出中的 markdown 代码块标记问题
            # 移除 ```markdown 和 ``` 标记，但保留其他代码块
            # 模式1: ```markdown\n内容\n```  -> 内容
            # 模式2: ```\n内容\n```  -> 内容（如果内容看起来不像代码）
            text = re.sub(
                r'```markdown\s*\n(.*?)\n```',
                lambda m: m.group(1),
                text,
                flags=re.DOTALL
            )

            # 先转义 HTML，然后转换 Markdown
            html_text = markdown.markdown(
                text,
                extensions=[
                    'tables',      # 表格支持
                    'fenced_code', # 代码块
                    'nl2br',       # 换行转 <br>
                    'sane_lists',  # 更好的列表支持
                ]
            )

            # 清理过多的 <hr /> 分隔线（移动端显示效果差）
            # 将连续的多个 hr 减少为一个
            html_text = re.sub(r'(<hr\s*/?>[\s\n]*){2,}', '<hr />', html_text)

            # 移除标题前的 hr（标题本身已有分隔）
            html_text = re.sub(r'<hr\s*/?>\s*<h([23])', r'<h\1', html_text)

            # 修复 iOS Mail 兼容性：移除标题标签内的 <strong> 嵌套
            # iOS Mail 无法正确渲染 <h3><strong>标题</strong></h3>
            # 转换为 <h3>标题</h3>（通过 CSS 让 h3 自动加粗）
            html_text = re.sub(
                r'<h([23])>\s*<strong>(.*?)</strong>\s*</h\1>',
                r'<h\1>\2</h\1>',
                html_text,
                flags=re.DOTALL
            )

            return html_text

        def number_format(value: Any, decimals: int = 2) -> str:
            """
            数字格式化（千分位）

            Args:
                value: 数字值
                decimals: 小数位数

            Returns:
                格式化后的字符串
            """
            if value is None:
                return "-"

            try:
                value_float = float(value)
                return f"{value_float:,.{decimals}f}"
            except (ValueError, TypeError):
                return str(value)

        def format_money(value: Any, unit: str = "亿") -> str:
            """
            金额格式化（用于北向资金等）

            Args:
                value: 金额值
                unit: 单位（亿、万等）

            Returns:
                格式化后的字符串
            """
            if value is None:
                return "-"

            try:
                value_float = float(value)
                sign = "+" if value_float > 0 else ""
                return f"{sign}{value_float:.1f}{unit}"
            except (ValueError, TypeError):
                return str(value)

        def escape_html(text: str) -> str:
            """
            HTML 转义

            Args:
                text: 原始文本

            Returns:
                转义后的文本
            """
            return html.escape(str(text)) if text else ""

        def truncate(text: str, length: int = 100, suffix: str = "...") -> str:
            """
            文本截断

            Args:
                text: 原始文本
                length: 最大长度
                suffix: 截断后缀

            Returns:
                截断后的文本
            """
            if not text:
                return ""

            text = str(text)
            if len(text) <= length:
                return text

            return text[:length] + suffix

        def format_date(value: Any, format_str: str = "%Y-%m-%d %H:%M") -> str:
            """
            日期格式化

            Args:
                value: 日期值（字符串或 datetime 对象）
                format_str: 格式化字符串

            Returns:
                格式化后的日期字符串
            """
            if not value:
                return "-"

            # 如果是字符串，尝试解析
            if isinstance(value, str):
                try:
                    # 处理 ISO 格式
                    if "T" in value:
                        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
                    else:
                        # 简单格式
                        value = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    return value

            if isinstance(value, datetime):
                return value.strftime(format_str)

            return str(value)

        def render_status_badge(status: bool) -> str:
            """
            渲染状态徽章

            Args:
                status: 状态（True=成功, False=失败）

            Returns:
                HTML 徽章字符串
            """
            if status:
                return '<span class="badge ok">✓ 正常</span>'
            else:
                return '<span class="badge error">✗ 异常</span>'

        # 注册所有过滤器到 Jinja2 环境
        self.jinja_env.filters['markdown_to_html'] = markdown_to_html
        self.jinja_env.filters['number_format'] = number_format
        self.jinja_env.filters['format_money'] = format_money
        self.jinja_env.filters['escape_html'] = escape_html
        self.jinja_env.filters['truncate'] = truncate
        self.jinja_env.filters['format_date'] = format_date
        self.jinja_env.filters['render_status_badge'] = render_status_badge

    def render(
        self,
        template_path: str,
        context: Dict[str, Any],
        template_vars: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        渲染模板

        Args:
            template_path: 模板路径（相对于模板根目录）
                         例如：modules/podcast/episode_update.html
            context: 模板变量
            template_vars: 额外的模板变量（会合并到 context）

        Returns:
            渲染后的 HTML 内容

        Raises:
            TemplateNotFound: 模板文件不存在
            TemplateError: 模板渲染错误
        """
        # 添加默认变量
        final_context = {
            'now': datetime.now(),
            **(template_vars or {}),
            **context
        }

        # 渲染模板
        try:
            template = self.jinja_env.get_template(template_path)
            return template.render(**final_context)
        except Exception as e:
            raise Exception(f"模板渲染失败: {template_path}, 错误: {e}") from e

    def render_module_email(
        self,
        module: str,
        template_name: str,
        context: Dict[str, Any]
    ) -> str:
        """
        渲染模块邮件（便捷方法）

        Args:
            module: 模块名称（podcast/investment/monitor/deploy/wechat）
            template_name: 模板文件名
            context: 模板变量

        Returns:
            渲染后的 HTML 内容

        Example:
            >>> renderer = EmailRenderer()
            >>> html = renderer.render_module_email(
            ...     module='podcast',
            ...     template_name='episode_update.html',
            ...     context={'episode': {...}}
            ... )
        """
        template_path = f"modules/{module}/{template_name}"
        return self.render(template_path, context)

    def test_render(self, module: str, template_name: str) -> str:
        """
        测试渲染（使用测试数据）

        Args:
            module: 模块名称
            template_name: 模板文件名

        Returns:
            渲染后的 HTML 内容
        """
        import json

        # 加载测试数据
        test_data_file = Path(__file__).parent.parent.parent / "agents" / "test_data" / f"{module}_test_data.json"

        if not test_data_file.exists():
            raise FileNotFoundError(f"测试数据文件不存在: {test_data_file}")

        with open(test_data_file, 'r', encoding='utf-8') as f:
            test_data = json.load(f)

        # 渲染模板
        return self.render_module_email(module, template_name, test_data)


# 便捷函数
def create_renderer(template_base_dir: Optional[Path] = None) -> EmailRenderer:
    """
    创建邮件渲染器（便捷函数）

    Args:
        template_base_dir: 模板根目录

    Returns:
        EmailRenderer 实例
    """
    return EmailRenderer(template_base_dir)


# 导出
__all__ = ['EmailRenderer', 'create_renderer']
