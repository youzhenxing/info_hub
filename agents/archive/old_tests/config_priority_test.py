#!/usr/bin/env python3
"""
测试配置优先级实验
验证 .env 和 config.yaml 的实际加载行为
"""

import os
import sys
from pathlib import Path

# 添加 wechat 模块路径
sys.path.insert(0, str(Path(__file__).parent.parent / "wechat"))

def test_config_priority():
    """测试配置优先级"""

    print("=" * 70)
    print("配置优先级测试实验")
    print("=" * 70)

    # 1. 检查环境变量（包括 load_dotenv 加载的）
    print("\n1️⃣ 环境变量（os.environ）中的配置：")
    print(f"   EMAIL_FROM = {os.environ.get('EMAIL_FROM', '❌ 未设置')}")
    print(f"   EMAIL_PASSWORD = {os.environ.get('EMAIL_PASSWORD', '❌ 未设置')[:8]}..." if os.environ.get('EMAIL_PASSWORD') else "   EMAIL_PASSWORD = ❌ 未设置")

    # 2. 检查 ConfigLoader 加载的配置
    from src.config_loader import ConfigLoader
    config = ConfigLoader('wechat/config.yaml')

    print("\n2️⃣ ConfigLoader 加载的配置：")
    print(f"   from = {config.email.from_addr}")
    print(f"   password = {config.email.password[:8]}...")

    # 3. 检查 .env 文件内容
    env_file = Path("wechat/.env")
    if env_file.exists():
        print("\n3️⃣ wechat/.env 文件内容（相关行）：")
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line.startswith("EMAIL_") and not line.startswith("#"):
                    # 隐藏密码
                    if "PASSWORD" in line:
                        parts = line.split("=")
                        if len(parts) > 1:
                            print(f"   {parts[0]}= {parts[1][:8]}...")
                    else:
                        print(f"   {line}")
    else:
        print("\n3️⃣ wechat/.env 文件：❌ 不存在")

    # 4. 检查 config.yaml 文件内容
    import yaml
    yaml_file = Path("wechat/config.yaml")
    if yaml_file.exists():
        with open(yaml_file) as f:
            yaml_config = yaml.safe_load(f)
        print("\n4️⃣ wechat/config.yaml 文件内容：")
        email_config = yaml_config.get('email', {})
        print(f"   from: {email_config.get('from', '❌ 未设置')}")
        pwd = email_config.get('password', '')
        print(f"   password: {pwd[:8]}..." if pwd else "   password: ❌ 未设置")

    # 5. 分析配置来源
    print("\n" + "=" * 70)
    print("📊 配置来源分析：")
    print("=" * 70)

    env_pwd = os.environ.get('EMAIL_PASSWORD', '')
    yaml_pwd = yaml_config.get('email', {}).get('password', '')

    if env_pwd:
        print(f"\n✅ 使用环境变量（来自 .env 加载）")
        print(f"   环境变量中的密码: {env_pwd[:8]}...")
        if env_pwd == yaml_pwd:
            print(f"   → 与 config.yaml 一致")
        else:
            print(f"   → 与 config.yaml 不同（config.yaml 中是 {yaml_pwd[:8]}...）")
            print(f"   → 说明环境变量优先级更高，覆盖了 config.yaml")
    else:
        print(f"\n❌ 环境变量未设置")
        print(f"   使用 config.yaml 的配置")
        print(f"   config.yaml 中的密码: {yaml_pwd[:8]}...")

    print("\n" + "=" * 70)
    print("结论：")
    print("=" * 70)

    # 检查是否一致
    if env_pwd and env_pwd == yaml_pwd:
        print("✅ .env 和 config.yaml 配置一致（推荐状态）")
        print("   修改任何一个都可以生效")
    elif env_pwd:
        print("⚠️  .env 和 config.yaml 配置不一致")
        print("   实际生效的是 .env 的配置")
        print("   修改 config.yaml 不会生效，除非 .env 不存在或为空")
    else:
        print("✅ 未使用 .env，config.yaml 生效")

if __name__ == "__main__":
    test_config_priority()
