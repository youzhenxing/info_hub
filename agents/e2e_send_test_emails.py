#!/usr/bin/env python3
# coding=utf-8
"""
使用测试数据发送真实邮件

快速验证4个模块的邮件渲染效果
"""

import os
import sys
from pathlib import Path
from datetime import datetime
import json

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

# 导入EmailRenderer和邮件发送器
from shared.lib.email_renderer import EmailRenderer
from trendradar.notification.senders import send_to_email


def send_test_email(module: str, test_data_file: str, subject: str):
    """
    发送测试邮件

    Args:
        module: 模块名称（podcast, investment, community, monitor）
        test_data_file: 测试数据JSON文件路径
        subject: 邮件主题
    """
    print(f"\n{'='*60}")
    print(f"📧 发送 {module.upper()} 模块测试邮件")
    print(f"{'='*60}")

    # 读取测试数据
    test_data_path = PROJECT_ROOT / "agents" / "test_data" / test_data_file
    if not test_data_path.exists():
        print(f"❌ 测试数据文件不存在: {test_data_path}")
        return False

    with open(test_data_path, 'r', encoding='utf-8') as f:
        template_data = json.load(f)

    # 使用EmailRenderer渲染
    renderer = EmailRenderer()

    # 确定模板名称
    template_map = {
        "podcast": "episode_update.html",
        "investment": "daily_report.html",
        "community": "daily_report.html",
        "monitor": "daily_log.html",
        "wechat": "daily_report.html",
        "deploy": "deploy_notification.html"
    }

    template_name = template_map.get(module, "daily_report.html")

    try:
        # 渲染模板
        html = renderer.render_module_email(
            module=module,
            template_name=template_name,
            context=template_data
        )

        # 保存HTML
        output_dir = PROJECT_ROOT / "agents" / "e2e_output"
        output_dir.mkdir(parents=True, exist_ok=True)
        html_file = output_dir / f"{module}_email.html"
        html_file.write_text(html, encoding="utf-8")
        print(f"💾 HTML已保存: {html_file}")

        # 发送邮件
        from_email = os.environ.get("EMAIL_FROM", "")
        password = os.environ.get("EMAIL_PASSWORD", "")
        to_email = os.environ.get("EMAIL_TO", "")

        if not all([from_email, password, to_email]):
            print("⚠️ 邮件配置不完整")
            print(f"   EMAIL_FROM: {'✅' if from_email else '❌'}")
            print(f"   EMAIL_PASSWORD: {'✅' if password else '❌'}")
            print(f"   EMAIL_TO: {'✅' if to_email else '❌'}")
            return False

        print("📧 发送邮件...")
        success = send_to_email(
            from_email=from_email,
            password=password,
            to_email=to_email,
            report_type=subject,
            html_file_path=str(html_file)
        )

        if success:
            print(f"✅ {module.upper()} 邮件发送成功")
            return True
        else:
            print(f"❌ {module.upper()} 邮件发送失败")
            return False

    except Exception as e:
        print(f"❌ 渲染或发送失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    print("="*60)
    print("🚀 TrendRadar 邮件发送测试")
    print("="*60)
    print(f"⏰ 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    results = {}

    # 测试4个模块
    modules = [
        {
            "name": "podcast",
            "data_file": "podcast_test_data.json",
            "subject": "🎙️ 播客更新测试 - DeepSeek R1"
        },
        {
            "name": "investment",
            "data_file": "investment_test_data.json",
            "subject": "📈 投资简报测试 - 2025-01-20"
        },
        {
            "name": "community",
            "data_file": "community_test_data.json",
            "subject": "🌐 社区热点测试 - 2025-01-20"
        },
        {
            "name": "monitor",
            "data_file": "monitor_test_data.json",
            "subject": "📋 监控日志测试 - 2025-01-20"
        }
    ]

    for module_info in modules:
        results[module_info["name"]] = send_test_email(
            module=module_info["name"],
            test_data_file=module_info["data_file"],
            subject=module_info["subject"]
        )

    # 汇总结果
    print("\n" + "="*60)
    print("📊 发送结果汇总")
    print("="*60)

    success_count = 0
    for module, success in results.items():
        status = "✅ 成功" if success else "❌ 失败"
        print(f"{module.upper()}: {status}")
        if success:
            success_count += 1

    print(f"\n总计: {success_count}/{len(results)} 封邮件发送成功")

    print(f"\n⏰ 结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📁 输出目录: {PROJECT_ROOT / 'agents' / 'e2e_output'}")


if __name__ == "__main__":
    main()
