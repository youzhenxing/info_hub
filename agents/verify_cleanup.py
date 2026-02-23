#!/usr/bin/env python3
# coding=utf-8
"""
基本功能验证脚本

验证清理后的代码完整性
"""

import os
import sys
from pathlib import Path

# 添加项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

print("="*60)
print("🔍 TrendRadar 代码清理验证")
print("="*60)
print(f"📁 项目根目录: {PROJECT_ROOT}")
print()

# 测试结果
all_passed = True
errors = []

# 1. 测试核心模块导入
print("1️⃣ 测试核心模块导入...")
modules_to_test = [
    ("trendradar.investment.analyzer", "InvestmentAnalyzer"),
    ("trendradar.podcast.analyzer", "PodcastAnalyzer"),
    ("trendradar.community.analyzer", "CommunityAnalyzer"),
    ("wechat.src.analyzer", "WechatAnalyzer"),
]

for module_name, class_name in modules_to_test:
    try:
        module = __import__(module_name, fromlist=[class_name])
        cls = getattr(module, class_name)
        print(f"  ✅ {module_name}.{class_name}")
    except Exception as e:
        all_passed = False
        errors.append(f"{module_name}.{class_name}: {e}")
        print(f"  ❌ {module_name}.{class_name}: {e}")

print()

# 2. 测试配置文件
print("2️⃣ 测试配置文件...")
try:
    from trendradar.core.loader import load_config
    config = load_config()
    print(f"  ✅ config.yaml 加载成功")
    print(f"  ✅ 投资模块启用: {config.get('investment', {}).get('enabled', False)}")
    print(f"  ✅ 播客模块启用: {config.get('podcast', {}).get('enabled', False)}")
    print(f"  ✅ 社区模块启用: {config.get('community', {}).get('enabled', False)}")
except Exception as e:
    all_passed = False
    errors.append(f"config.yaml: {e}")
    print(f"  ❌ config.yaml: {e}")

print()

# 3. 测试 prompt 文件
print("3️⃣ 测试 Prompt 文件...")
prompt_files = [
    "prompts/podcast_prompts.txt",
    "prompts/community_prompts.txt",
    "prompts/investment_step1_article.txt",
    "prompts/investment_step2_aggregate.txt",
    "wechat/prompts/wechat_step1_summary.txt",
    "wechat/prompts/wechat_step2_aggregate.txt",
]

for prompt_file in prompt_files:
    path = PROJECT_ROOT / prompt_file
    if path.exists():
        size = path.stat().st_size
        print(f"  ✅ {prompt_file} ({size} bytes)")
    else:
        all_passed = False
        errors.append(f"{prompt_file}: 文件不存在")
        print(f"  ❌ {prompt_file} - 文件不存在")

print()

# 4. 测试 fetcher 类
print("4️⃣ 测试 Fetcher 类...")
try:
    from trendradar.podcast.fetcher import PodcastFetcher, PodcastFeedConfig
    feed = PodcastFeedConfig(
        id="test",
        name="Test",
        url="https://example.com/rss",
        enabled=True
    )
    fetcher = PodcastFetcher([feed])
    print(f"  ✅ PodcastFetcher 实例化成功")
except Exception as e:
    all_passed = False
    errors.append(f"PodcastFetcher: {e}")
    print(f"  ❌ PodcastFetcher: {e}")

print()

# 5. 验证清理效果
print("5️⃣ 验证清理效果...")
print("  检查不应存在的文件...")

should_not_exist = [
    "prompts/investment_legacy_daily.txt",
    "prompts/investment_article.txt",
    "prompts/investment_aggregate.txt",
    "wechat/prompts/article_summary.txt",
    "wechat/prompts/topic_aggregate.txt",
    "__pycache__",
]

for file_path in should_not_exist:
    path = PROJECT_ROOT / file_path
    if path.exists():
        all_passed = False
        errors.append(f"{file_path}: 应该被删除但仍然存在")
        print(f"  ❌ {file_path} - 应该被删除但仍然存在")
    else:
        print(f"  ✅ {file_path} - 已正确删除")

print()
print("="*60)
print("📊 验证结果总结")
print("="*60)

if all_passed:
    print()
    print("🎉 所有测试通过！")
    print()
    print("✅ 代码清理成功：")
    print("  - 所有核心模块正常导入")
    print("  - 配置文件加载正常")
    print("  - Prompt 文件完整")
    print("  - 冗余文件已清理")
    print()
    print("🚀 系统链路完整，可以正常运行！")
else:
    print()
    print("⚠️  发现问题：")
    for error in errors:
        print(f"  - {error}")
    print()

print()
print("✅ 验证完成！")
