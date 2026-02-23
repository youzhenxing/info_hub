#!/usr/bin/env python3
"""
TrendRadar 端到端测试触发器

作用：
  - 构造参数调用生产代码
  - 不包含任何业务逻辑
  - 验证测试代码 = 生产代码

使用方法：
  python agents/test_e2e.py                # 运行所有测试
  python agents/test_e2e.py podcast        # 仅播客测试
  python agents/test_e2e.py investment     # 仅投资测试
  python agents/test_e2e.py community      # 仅社区测试
  python agents/test_e2e.py wechat         # 仅微信测试
"""

import subprocess
import sys
import os
from pathlib import Path
from typing import List, Tuple

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent


def send_deploy_notification(results: List[Tuple[str, bool]]):
    """
    发送发版通知邮件

    Args:
        results: 测试结果列表，格式: [("播客", True), ("投资", False), ...]
    """
    try:
        from trendradar.notification.deploy_notifier import DeployNotifier
        from trendradar.core.loader import load_config

        # 读取版本号
        version_file = PROJECT_ROOT / "version"
        version = version_file.read_text().strip() if version_file.exists() else "unknown"

        # 构建模块结果
        module_results = {}
        module_name_map = {
            "播客": "podcast",
            "投资": "investment",
            "社区": "community",
            "微信": "wechat",
        }

        for name, success in results:
            module_key = module_name_map.get(name, name.lower())
            module_results[module_key] = {
                "success": success,
                "message": "测试通过" if success else "测试失败",
            }

        # 发送通知
        config = load_config()
        notifier = DeployNotifier(config)
        notifier.send_deploy_notification(version, module_results)

    except Exception as e:
        print(f"[DeployNotifier] 发送失败: {e}")
        import traceback
        traceback.print_exc()


def get_test_env():
    """
    获取测试环境变量

    注意：代理控制已在代码层面实现：
    - AI API 调用时自动禁用代理（trendradar/ai/client.py）
    - 社区模块通过配置文件控制代理使用（config.yaml community.proxy）
    """
    env = os.environ.copy()
    env["TEST_MODE"] = "true"
    return env


def test_podcast():
    """
    测试播客模块

    固定测试Lex Fridman某一期节目
    确保每次测试运行相同的数据
    """
    print("=" * 60)
    print("播客模块 E2E 测试")
    print("=" * 60)

    # 固定测试数据（使用数据库中已成功完成的episode，保证测试一致性）
    TEST_FEED_ID = "a16z"
    TEST_EPISODE_GUID = "359216a5-6ac0-4002-bae0-d2355f3751d5"  # "Anyone Can Code Now" - 已完整处理（有转写+分析）

    print(f"测试feed: {TEST_FEED_ID}")
    print(f"测试guid: {TEST_EPISODE_GUID}")
    print()

    # 构造命令（调用生产代码）
    cmd = [
        sys.executable, "-m", "trendradar",
        "--podcast-only",
        "--test-mode",
        "--test-feed", TEST_FEED_ID,
        "--test-guid", TEST_EPISODE_GUID,
    ]

    print("执行命令:")
    print(" ".join(cmd))
    print()

    # 执行（设置环境变量，修复代理问题）
    result = subprocess.run(
        cmd,
        cwd=PROJECT_ROOT,
        env=get_test_env(),
    )

    if result.returncode == 0:
        print("\n✅ 播客模块测试通过")
        return True
    else:
        print("\n❌ 播客模块测试失败")
        return False


def test_investment():
    """
    测试投资模块

    测试A股/港股市场简报
    使用 --test-mode 强制运行（跳过时间检查）
    """
    print("=" * 60)
    print("投资模块 E2E 测试")
    print("=" * 60)

    print("测试市场: A股/港股")
    print()

    # 构造命令（调用生产代码）
    cmd = [
        sys.executable, "-m", "trendradar",
        "--investment-only",
        "--test-mode",
        "--market", "cn",
    ]

    print("执行命令:")
    print(" ".join(cmd))
    print()

    # 执行（设置环境变量，修复代理问题）
    result = subprocess.run(
        cmd,
        cwd=PROJECT_ROOT,
        env=get_test_env(),
    )

    if result.returncode == 0:
        print("\n✅ 投资模块测试通过")
        return True
    else:
        print("\n❌ 投资模块测试失败")
        return False


def test_community():
    """
    测试社区模块

    测试社区监控（HackerNews、Reddit、GitHub等）
    使用 --test-mode 强制运行（跳过时间检查）
    """
    print("=" * 60)
    print("社区模块 E2E 测试")
    print("=" * 60)

    print("测试数据源: HackerNews、Reddit、GitHub、ProductHunt等")
    print()

    # 构造命令（调用生产代码）
    cmd = [
        sys.executable, "-m", "trendradar",
        "--community-only",
        "--test-mode",
    ]

    print("执行命令:")
    print(" ".join(cmd))
    print()

    # 执行（设置环境变量，修复代理问题）
    result = subprocess.run(
        cmd,
        cwd=PROJECT_ROOT,
        env=get_test_env(),
    )

    if result.returncode == 0:
        print("\n✅ 社区模块测试通过")
        return True
    else:
        print("\n❌ 社区模块测试失败")
        return False


def test_wechat():
    """
    测试微信模块

    固定测试3个公众号
    需要在 wechat/config.yaml 中启用 test.enabled=true
    """
    print("=" * 60)
    print("微信模块 E2E 测试")
    print("=" * 60)

    # 检查配置
    config_path = PROJECT_ROOT / "wechat" / "config.yaml"

    print(f"配置文件: {config_path}")
    print()
    print("⚠️  请确保 wechat/config.yaml 中配置了:")
    print("    test:")
    print("      enabled: true")
    print("      feed_limit: 3")
    print()

    # 构造命令（调用生产代码）
    cmd = [
        sys.executable, "main.py", "run"
    ]

    print("\n执行命令:")
    print(" ".join(cmd))
    print()

    # 执行（在wechat目录下，修复代理问题）
    result = subprocess.run(
        cmd,
        cwd=PROJECT_ROOT / "wechat",
        env=get_test_env(),
    )

    if result.returncode == 0:
        print("\n✅ 微信模块测试通过")
        return True
    else:
        print("\n❌ 微信模块测试失败")
        return False


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("TrendRadar 端到端测试框架")
    print("=" * 60)
    print()
    print("注意：此脚本调用生产代码，使用真实配置")
    print("测试运行的代码 = 生产部署的代码")
    print()

    # 选择测试模块
    if len(sys.argv) > 1:
        module = sys.argv[1]

        if module == "podcast":
            success = test_podcast()
        elif module == "investment":
            success = test_investment()
        elif module == "community":
            success = test_community()
        elif module == "wechat":
            success = test_wechat()
        else:
            print(f"未知模块: {module}")
            print()
            print("用法:")
            print("  python agents/test_e2e.py                  # 运行所有测试")
            print("  python agents/test_e2e.py podcast          # 仅播客测试")
            print("  python agents/test_e2e.py investment       # 仅投资测试")
            print("  python agents/test_e2e.py community        # 仅社区测试")
            print("  python agents/test_e2e.py wechat           # 仅微信测试")
            sys.exit(1)

        sys.exit(0 if success else 1)
    else:
        # 运行所有测试
        results = []

        print("▶ 测试1/4: 播客模块")
        print()
        results.append(("播客", test_podcast()))

        print("\n" + "-" * 60 + "\n")

        print("▶ 测试2/4: 投资模块")
        print()
        results.append(("投资", test_investment()))

        print("\n" + "-" * 60 + "\n")

        print("▶ 测试3/4: 社区模块")
        print()
        results.append(("社区", test_community()))

        print("\n" + "-" * 60 + "\n")

        print("▶ 测试4/4: 微信模块")
        print()
        results.append(("微信", test_wechat()))

        # 汇总结果
        print("\n" + "=" * 60)
        print("测试结果汇总")
        print("=" * 60)

        for name, success in results:
            status = "✅ 通过" if success else "❌ 失败"
            print(f"  {name}模块: {status}")

        all_success = all(r[1] for r in results)

        print()
        if all_success:
            print("🎉 所有测试通过！")
        else:
            print("⚠️  部分测试失败，请检查日志")

        # 发送发版通知邮件
        print("\n" + "=" * 60)
        print("📧 发送发版通知邮件")
        print("=" * 60)
        send_deploy_notification(results)

        sys.exit(0 if all_success else 1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n测试已取消")
        sys.exit(1)
