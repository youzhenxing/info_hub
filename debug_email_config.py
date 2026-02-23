#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""调试播客邮件配置"""

from trendradar.core.loader import load_config
from trendradar.podcast.processor import PodcastProcessor

# 加载配置
config = load_config()

print("=" * 60)
print("配置调试信息")
print("=" * 60)

# 检查播客配置
podcast_config = config.get("PODCAST", {})
print("\n1. 播客通知配置:")
notification_config = podcast_config.get("NOTIFICATION", {})
print(f"   ENABLED: {notification_config.get('ENABLED')}")
print(f"   CHANNELS: {notification_config.get('CHANNELS')}")

# 检查全局邮件配置（在 config 根级别）
print("\n2. 全局邮件配置（config 根级别）:")
print(f"   EMAIL_FROM: {config.get('EMAIL_FROM')}")
print(f"   EMAIL_TO: {config.get('EMAIL_TO')}")
print(f"   EMAIL_PASSWORD: {'***' if config.get('EMAIL_PASSWORD') else None}")
print(f"   EMAIL_SMTP_SERVER: {config.get('EMAIL_SMTP_SERVER')}")
print(f"   EMAIL_SMTP_PORT: {config.get('EMAIL_SMTP_PORT')}")

print("\n2b. 构建的邮件配置字典:")
email_config = {
    "FROM": config.get("EMAIL_FROM", ""),
    "PASSWORD": config.get("EMAIL_PASSWORD", ""),
    "TO": config.get("EMAIL_TO", ""),
    "SMTP_SERVER": config.get("EMAIL_SMTP_SERVER", ""),
    "SMTP_PORT": config.get("EMAIL_SMTP_PORT", ""),
}
print(f"   {email_config}")

# 创建 processor
print("\n3. 创建 PodcastProcessor...")
processor = PodcastProcessor.from_config(config)

print(f"   processor.enabled: {processor.enabled}")
print(f"   notifier.enabled: {processor.notifier.enabled}")
print(f"   notifier.channels: {processor.notifier.channels}")
print(f"   notifier.email_config: {processor.notifier.email_config}")

# 测试邮件配置读取
from_email = processor.notifier.email_config.get("FROM", processor.notifier.email_config.get("from", ""))
password = processor.notifier.email_config.get("PASSWORD", processor.notifier.email_config.get("password", ""))
to_email = processor.notifier.email_config.get("TO", processor.notifier.email_config.get("to", ""))

print("\n4. Notifier 中实际读取的邮件配置:")
print(f"   from_email: {from_email}")
print(f"   to_email: {to_email}")
print(f"   password: {'***' if password else None}")
print(f"   配置完整: {all([from_email, password, to_email])}")

print("\n" + "=" * 60)
