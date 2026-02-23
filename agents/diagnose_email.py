#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
邮件发送诊断脚本
用于诊断 163 邮箱发送问题
"""

import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def diagnose_email():
    """诊断邮件发送问题"""

    print("=" * 60)
    print("163 邮箱发送诊断")
    print("=" * 60)

    # 获取配置
    smtp_server = os.environ.get('EMAIL_SMTP_SERVER', 'smtp.163.com')
    smtp_port = int(os.environ.get('EMAIL_SMTP_PORT', '465'))
    smtp_user = os.environ.get('EMAIL_FROM', '{{EMAIL_ADDRESS}}')
    smtp_password = os.environ.get('EMAIL_PASSWORD', '')
    email_to = os.environ.get('EMAIL_TO', '{{EMAIL_ADDRESS}}')

    print(f"\n📧 邮件配置:")
    print(f"  SMTP 服务器: {smtp_server}")
    print(f"  SMTP 端口: {smtp_port}")
    print(f"  发件人: {smtp_user}")
    print(f"  收件人: {email_to}")
    print(f"  密码长度: {len(smtp_password)} 字符")

    # 检查配置
    print(f"\n🔍 配置检查:")

    if smtp_server != 'smtp.163.com':
        print(f"  ⚠️  SMTP 服务器可能不正确（应为 smtp.163.com）")
    else:
        print(f"  ✅ SMTP 服务器正确")

    if smtp_port not in [465, 994]:
        print(f"  ⚠️  SMTP 端口可能不正确（应为 465 或 994）")
    else:
        print(f"  ✅ SMTP 端口正确（{smtp_port}）")

    if '@163.com' not in smtp_user:
        print(f"  ⚠️  发件人邮箱可能不是 163 邮箱")
    else:
        print(f"  ✅ 发件人邮箱正确")

    if len(smtp_password) < 8:
        print(f"  ❌ 密码太短（163 邮箱需要 16 位授权码）")
    else:
        print(f"  ✅ 密码长度正常")

    # 尝试连接 SMTP 服务器
    print(f"\n🔌 SMTP 连接测试:")

    try:
        print(f"  正在连接 {smtp_server}:{smtp_port}...")

        if smtp_port == 465:
            server = smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=30)
        else:
            server = smtplib.SMTP(smtp_server, smtp_port, timeout=30)
            server.starttls()

        print(f"  ✅ SMTP 连接成功")

        # 尝试登录
        print(f"  正在登录...")
        try:
            server.login(smtp_user, smtp_password)
            print(f"  ✅ SMTP 登录成功")
        except smtplib.SMTPAuthenticationError as e:
            print(f"  ❌ SMTP 认证失败: {e}")
            print(f"\n💡 可能的原因:")
            print(f"  1. 密码错误或授权码错误")
            print(f"  2. 需要使用 163 邮箱的授权码（不是登录密码）")
            print(f"  3. SMTP 服务未开启")
            print(f"\n📝 解决方案:")
            print(f"  1. 登录 163 邮箱网页版")
            print(f"  2. 进入设置 -> POP3/SMTP/IMAP")
            print(f"  3. 开启 SMTP 服务")
            print(f"  4. 生成授权码（16 位）")
            print(f"  5. 使用授权码代替密码更新配置")
            return False

        # 发送测试邮件
        print(f"\n📨 发送测试邮件...")

        msg = MIMEMultipart()
        msg['From'] = smtp_user
        msg['To'] = email_to
        msg['Subject'] = '[测试] TrendRadar 邮件发送诊断'

        body = f"""
这是一封测试邮件，用于诊断邮件发送问题。

如果您收到这封邮件，说明：
✅ SMTP 配置正确
✅ 认证成功
✅ 邮件发送功能正常

测试时间: {os.popen('date').read().strip()}
"""

        msg.attach(MIMEText(body, 'plain', 'utf-8'))

        server.sendmail(smtp_user, email_to, msg.as_string())
        server.quit()

        print(f"  ✅ 测试邮件发送成功！")
        print(f"\n📬 请检查邮箱: {email_to}")
        print(f"   注意：可能在垃圾箱或垃圾邮件文件夹中")

        return True

    except smtplib.SMTPConnectError as e:
        print(f"  ❌ SMTP 连接失败: {e}")
        print(f"\n💡 可能的原因:")
        print(f"  1. 网络问题（无法访问 smtp.163.com）")
        print(f"  2. 防火墙阻止了 SMTP 端口")
        return False

    except Exception as e:
        print(f"  ❌ 发送失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = diagnose_email()

    print("\n" + "=" * 60)
    if success:
        print("✅ 诊断完成 - 邮件发送正常")
        print("\n下一步:")
        print("1. 检查邮箱（包括垃圾箱）")
        print("2. 如果收到了，说明配置正确")
        print("3. 播客邮件应该也能正常发送")
    else:
        print("❌ 诊断完成 - 发现问题")
        print("\n建议:")
        print("1. 按照 163 邮箱授权码设置指南操作")
        print("2. 更新 EMAIL_PASSWORD 环境变量")
        print("3. 重新部署容器")
    print("=" * 60)
