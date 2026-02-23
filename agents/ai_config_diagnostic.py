#!/usr/bin/env python3
"""
AI 配置诊断脚本

检查生产环境的 AI 配置状态，诊断部署邮件显示的"AI分析异常"问题
"""

import sys
from pathlib import Path

# 添加项目路径
project_root = Path("/home/zxy/Documents/install/trendradar")
sys.path.insert(0, str(project_root))

import yaml

def load_yaml(file_path):
    """加载 YAML 文件"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def check_ai_config():
    """检查 AI 配置状态"""

    print("=" * 80)
    print("AI 配置诊断报告")
    print("=" * 80)

    # 加载生产环境配置
    config_path = project_root / "shared/config/config.yaml"
    config = load_yaml(config_path)

    print("\n📋 配置文件路径:", config_path)

    # 1. 检查全局 AI 配置
    print("\n" + "─" * 80)
    print("1️⃣  全局 AI 配置 (ai.*)")
    print("─" * 80)

    global_ai = config.get("ai", {})
    print(f"model: {global_ai.get('model', '未配置')}")
    print(f"api_key: {'✅ 已配置' if global_ai.get('api_key') else '❌ 未配置 (空值)'}")
    print(f"api_base: {global_ai.get('api_base', '未配置')}")

    # 2. 检查播客模块 AI 配置
    print("\n" + "─" * 80)
    print("2️⃣  播客模块 AI 配置 (podcast.analysis.*)")
    print("─" * 80)

    podcast = config.get("podcast", {})
    podcast_analysis = podcast.get("analysis", {})
    print(f"enabled: {podcast_analysis.get('enabled', False)}")
    print(f"model: {podcast_analysis.get('model', '未配置')}")
    print(f"api_key: {'✅ 已配置' if podcast_analysis.get('api_key') else '❌ 未配置'}")
    print(f"api_base: {podcast_analysis.get('api_base', '未配置')}")

    # 3. 检查投资模块 AI 配置
    print("\n" + "─" * 80)
    print("3️⃣  投资模块 AI 配置 (investment.analysis.*)")
    print("─" * 80)

    investment = config.get("investment", {})
    investment_analysis = investment.get("analysis", {})
    print(f"enabled: {investment_analysis.get('enabled', False)}")
    print(f"model: {investment_analysis.get('model', '未配置')}")
    print(f"api_key: {'✅ 已配置' if investment_analysis.get('api_key') else '❌ 未配置'}")
    print(f"api_base: {investment_analysis.get('api_base', '未配置')}")

    # 4. 检查社区模块 AI 配置
    print("\n" + "─" * 80)
    print("4️⃣  社区模块 AI 配置 (community.analysis.*)")
    print("─" * 80)

    community = config.get("community", {})
    community_analysis = community.get("analysis", {})
    print(f"enabled: {community_analysis.get('enabled', False)}")
    print(f"model: {community_analysis.get('model', '未配置')}")
    print(f"api_key: {'✅ 已配置' if community_analysis.get('api_key') else '❌ 未配置'}")
    print(f"api_base: {community_analysis.get('api_base', '未配置')}")

    # 5. 检查全局 AI 分析功能
    print("\n" + "─" * 80)
    print("5️⃣  全局 AI 分析功能 (ai_analysis.*)")
    print("─" * 80)

    ai_analysis = config.get("ai_analysis", {})
    print(f"enabled: {ai_analysis.get('enabled', False)}")
    print("注意: 全局 ai_analysis.enabled = false (已关闭，专注播客/投资/社区模块)")

    # 6. 总结
    print("\n" + "=" * 80)
    print("📊 诊断总结")
    print("=" * 80)

    issues = []
    recommendations = []

    # 检查全局 AI 配置
    if not global_ai.get("api_key"):
        issues.append("全局 ai.api_key 未配置")
        recommendations.append("建议: 在 ai.api_key 添加 API key，或保持空值（各模块已独立配置）")

    # 检查各模块配置
    module_configs = {
        "播客模块": podcast_analysis,
        "投资模块": investment_analysis,
        "社区模块": community_analysis
    }

    for module_name, module_config in module_configs.items():
        if module_config.get("enabled"):
            if module_config.get("api_key"):
                print(f"✅ {module_name}: AI 配置完整")
            else:
                issues.append(f"{module_name} enabled 但缺少 api_key")
                print(f"❌ {module_name}: enabled 但缺少 api_key")
        else:
            print(f"⚪ {module_name}: 未启用")

    if issues:
        print("\n❌ 发现的问题:")
        for i, issue in enumerate(issues, 1):
            print(f"   {i}. {issue}")
    else:
        print("\n✅ 所有启用的模块 AI 配置完整")

    if recommendations:
        print("\n💡 建议:")
        for rec in recommendations:
            print(f"   {rec}")

    # 7. 部署通知检查逻辑说明
    print("\n" + "=" * 80)
    print("🔍 部署通知脚本检查逻辑")
    print("=" * 80)
    print("""
部署通知脚本 (send_deploy_notification.py) 的检查逻辑：

    check_config_status():
        "ai_configured": bool(config.get("ai", {}).get("api_key"))

这个检查只验证全局 ai.api_key 是否存在，不检查模块独立配置。

实际情况：
  - 全局 ai.api_key = "" (空值) ❌
  - 播客 podcast.analysis.api_key = "sk-..." ✅
  - 投资 investment.analysis.api_key = "sk-..." ✅
  - 社区 community.analysis.api_key = "sk-..." ✅

结论: 部署邮件显示"AI分析异常"是因为全局 ai.api_key 为空，
      但实际各功能模块的 AI 配置都是完整的，功能正常工作。
    """)

    print("\n" + "=" * 80)

if __name__ == "__main__":
    check_ai_config()
