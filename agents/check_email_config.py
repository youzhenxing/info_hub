#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
邮件配置快速检查脚本
"""

import os
from pathlib import Path

DEV_BASE = Path("/home/zxy/Documents/code/TrendRadar")

# 加载 .env 文件
def load_env():
    env_file = DEV_BASE / "agents" / ".env"
    if env_file.exists():
        with open(env_file, 'r') as f:
            config = {}
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    config[key] = value
            return config
    return {}

config = load_env()

print("=" * 60)
print("邮件配置检查")
print("=" * 60)

EMAIL_FROM = config.get("EMAIL_FROM", "")
EMAIL_TO = config.get("EMAIL_TO", "")
EMAIL_SMTP = config.get("EMAIL_SMTP_SERVER", "")

print(f"\n📧 当前配置:")
print(f"  发件人 (EMAIL_FROM): {EMAIL_FROM}")
print(f"  收件人 (EMAIL_TO):   {EMAIL_TO}")
print(f"  SMTP 服务器:         {EMAIL_SMTP}")

if EMAIL_FROM == EMAIL_TO:
    print(f"\n❌ 问题发现: 发件人和收件人相同！")
    print(f"\n💡 这可能导致:")
    print(f"  1. 163 邮箱拒绝接收（认为是重复邮件）")
    print(f"  2. 自动归档到\"已发送\"而不是\"收件箱\"")
    print(f"  3. 直接被垃圾邮件过滤")
    print(f"\n✅ 解决方案:")
    print(f"  编辑 {DEV_BASE}/agents/.env")
    print(f"  修改 EMAIL_TO 为其他邮箱（如 Gmail、QQ 邮箱等）")
else:
    print(f"\n✅ 配置正常: 发件人和收件人不同")

print("\n" + "=" * 60)
