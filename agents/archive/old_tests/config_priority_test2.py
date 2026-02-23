#!/usr/bin/env python3
"""
测试配置优先级实验 - 修正版（从 wechat 目录运行）
验证 .env 和 config.yaml 的实际加载行为
"""

import os
import sys
from pathlib import Path

def test_config_priority_from_wechat_dir():
    """从 wechat 目录测试配置优先级"""

    print("=" * 70)
    print("配置优先级测试实验（从 wechat 目录运行）")
    print("=" * 70)

    # 切换到 wechat 目录（模拟实际运行环境）
    original_dir = Path.cwd()
    wechat_dir = Path(__file__).parent.parent / "wechat"
    os.chdir(wechat_dir)
    print(f"\n📁 当前工作目录: {Path.cwd()}")

    # 导入 ConfigLoader（这会触发 load_dotenv()）
    sys.path.insert(0, str(wechat_dir))
    from src.config_loader import ConfigLoader

    # 1. 检查环境变量（包括 load_dotenv 加载的）
    print("\n1️⃣ 环境变量（os.environ）中的配置：")
    print(f"   EMAIL_FROM = {os.environ.get('EMAIL_FROM', '❌ 未设置')}")
    pwd = os.environ.get('EMAIL_PASSWORD')
    if pwd:
        print(f"   EMAIL_PASSWORD = {pwd[:8]}...")
    else:
        print(f"   EMAIL_PASSWORD = ❌ 未设置")

    # 2. 检查 ConfigLoader 加载的配置
    config = ConfigLoader('config.yaml')

    print("\n2️⃣ ConfigLoader 加载的配置：")
    print(f"   from = {config.email.from_addr}")
    print(f"   password = {config.email.password[:8]}...")

    # 3. 检查 .env 文件内容
    env_file = Path(".env")
    if env_file.exists():
        print("\n3️⃣ .env 文件内容（相关行）：")
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line.startswith("EMAIL_") and not line.startswith("#"):
                    if "PASSWORD" in line and "=" in line:
                        parts = line.split("=", 1)
                        if len(parts) > 1:
                            print(f"   {parts[0]}= {parts[1][:8]}...")
                    elif "=" in line:
                        print(f"   {line}")
    else:
        print("\n3️⃣ .env 文件：❌ 不存在")

    # 4. 检查 config.yaml 文件内容
    import yaml
    yaml_file = Path("config.yaml")
    if yaml_file.exists():
        with open(yaml_file) as f:
            yaml_config = yaml.safe_load(f)
        print("\n4️⃣ config.yaml 文件内容：")
        email_config = yaml_config.get('email', {})
        print(f"   from: {email_config.get('from', '❌ 未设置')}")
        pwd_yaml = email_config.get('password', '')
        print(f"   password: {pwd_yaml[:8]}..." if pwd_yaml else "   password: ❌ 未设置")

    # 5. 分析配置来源
    print("\n" + "=" * 70)
    print("📊 配置来源分析：")
    print("=" * 70)

    env_pwd = os.environ.get('EMAIL_PASSWORD', '')
    yaml_pwd = yaml_config.get('email', {}).get('password', '')

    if env_pwd:
        print(f"\n✅ 使用环境变量（通过 load_dotenv() 从 .env 加载）")
        print(f"   环境变量中的密码: {env_pwd[:8]}...")
        if env_pwd == yaml_pwd:
            print(f"   → 与 config.yaml 一致")
        else:
            print(f"   → 与 config.yaml 不同（config.yaml 中是 {yaml_pwd[:8]}...）")
            print(f"   → 说明环境变量优先级更高，覆盖了 config.yaml")
    else:
        print(f"\n❌ 环境变量未设置（.env 文件未被加载或不存在）")
        print(f"   使用 config.yaml 的配置")
        print(f"   config.yaml 中的密码: {yaml_pwd[:8]}...")

    print("\n" + "=" * 70)
    print("结论：")
    print("=" * 70)

    # 检查是否一致
    if env_pwd and env_pwd == yaml_pwd:
        print("✅ .env 和 config.yaml 配置一致（推荐状态）")
        print("   当前两者密码都是:", env_pwd[:8] + "...")
    elif env_pwd:
        print("⚠️  .env 和 config.yaml 配置不一致")
        print("   实际生效的是 .env 的配置:", env_pwd[:8] + "...")
        print("   config.yaml 的配置被覆盖:", yaml_pwd[:8] + "...")
    else:
        print("✅ 未使用 .env，config.yaml 生效:", yaml_pwd[:8] + "...")

    # 恢复原始工作目录
    os.chdir(original_dir)

if __name__ == "__main__":
    test_config_priority_from_wechat_dir()
