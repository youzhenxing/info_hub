#!/usr/bin/env python3
"""
Wewe-RSS 账号状态监控脚本

功能：
1. 检查 Wewe-RSS 账号是否有效
2. 检测到账号失效时发送告警邮件
3. 记录账号状态到日志

使用方法：
- 手动运行：python monitor_wewe_account.py
- 定时任务：添加到 crontab，每天运行一次
"""

import requests
import smtplib
import os
from datetime import datetime
from email.mime.text import MIMEText
from email.header import Header

# Wewe-RSS 配置
Wewe_RSS_URL = "http://localhost:4000"
W_API_URL = f"{Wewe_RSS_URL}/api"

# 邮件配置
EMAIL_FROM = os.environ.get('EMAIL_FROM', '{{EMAIL_ADDRESS}}')
EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD', '')
EMAIL_TO = os.environ.get('EMAIL_TO', '{{EMAIL_ADDRESS}}')
SMTP_SERVER = os.environ.get('EMAIL_SMTP_SERVER', 'smtp.163.com')
SMTP_PORT = int(os.environ.get('EMAIL_SMTP_PORT', '465'))


def check_account_status():
    """检查 Wewe-RSS 账号状态"""
    try:
        # 尝试访问 Wewe-RSS 主页
        response = requests.get(Wewe_RSS_URL, timeout=10)
        response.raise_for_status()

        # 尝试检查容器日志中的错误
        import subprocess
        result = subprocess.run(
            ['docker', 'logs', 'wewe-rss', '--tail', '20'],
            capture_output=True,
            text=True,
            timeout=5
        )

        logs = result.stdout

        # 检查是否有"暂无可用账号"错误
        if '暂无可用读书账号' in logs or '暂无可用账号' in logs:
            return False, "账号已失效（日志显示：暂无可用账号）"

        # 检查最近是否有成功的同步
        if '同步成功' in logs or 'sync success' in logs.lower():
            return True, "账号正常（日志显示：同步成功）"

        # 如果日志中没有明确的错误信息，尝试通过健康检查判断
        if response.status_code == 200:
            return True, "Wewe-RSS 服务运行正常"

        return False, f"未知状态（HTTP {response.status_code}）"

    except Exception as e:
        return False, f"检查失败: {str(e)}"


def send_alert_email(message):
    """发送告警邮件"""
    if not EMAIL_PASSWORD:
        print("⚠️ 未配置邮件密码，跳过发送")
        return

    try:
        msg = MIMEText(
            f"Wewe-RSS 账号失效告警\n\n"
            f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"状态: {message}\n\n"
            f"请立即处理:\n"
            f"1. 访问 {Wewe_RSS_URL}\n"
            f"2. 使用微信扫描二维码重新登录\n"
            f"3. 点击'立即同步'按钮\n\n"
            f"处理完成后，可以手动触发采集:\n"
            f"docker exec wechat-service python main.py run\n",
            'plain',
            'utf-8'
        )

        msg['From'] = EMAIL_FROM
        msg['To'] = EMAIL_TO
        msg['Subject'] = Header('⚠️ Wewe-RSS 账号失效告警', 'utf-8')

        server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, timeout=10)
        server.login(EMAIL_FROM, EMAIL_PASSWORD)
        server.sendmail(EMAIL_FROM, [EMAIL_TO], msg.as_string())
        server.quit()

        print("✅ 告警邮件已发送")

    except Exception as e:
        print(f"❌ 发送邮件失败: {e}")


def main():
    """主函数"""
    print("=" * 60)
    print("Wewe-RSS 账号状态监控")
    print("=" * 60)
    print(f"检查时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # 检查账号状态
    is_valid, message = check_account_status()

    if is_valid:
        print(f"✅ {message}")
        print()
        print("Wewe-RSS 运行正常，无需处理")
        return 0
    else:
        print(f"❌ {message}")
        print()
        print("⚠️ 检测到账号失效！")
        print()
        print("正在发送告警邮件...")

        send_alert_email(message)

        print()
        print("请按以下步骤处理：")
        print(f"1. 访问 {Wewe_RSS_URL}")
        print("2. 使用微信扫描二维码重新登录")
        print("3. 点击'立即同步'按钮")
        print()
        print("处理完成后，重新触发采集：")
        print("docker exec wechat-service python main.py run")

        return 1


if __name__ == "__main__":
    exit(main())
