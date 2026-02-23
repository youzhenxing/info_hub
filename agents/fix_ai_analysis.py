#!/usr/bin/env python3
"""
AI 分析问题诊断和修复
"""

import sys
import os
sys.path.insert(0, '/home/zxy/Documents/code/TrendRadar')

import yaml
from trendradar.community.collector import CommunityCollector
from trendradar.community.analyzer import CommunityAnalyzer

print('=' * 80)
print('AI 分析问题诊断和修复')
print('=' * 80)
print()

# 检查 AI API Key
print('步骤 1: 检查 AI 配置')
ai_api_key = os.environ.get('AI_API_KEY', '')
print(f'  AI_API_KEY 环境变量: {"已设置" if ai_api_key else "未设置"}')

if not ai_api_key:
    print('  ⚠️  AI_API_KEY 未设置')
    print('  这可能导致 AI 分析失败')
    print()
    print('  解决方案:')
    print('  1. 设置环境变量: export AI_API_KEY=your_key')
    print('  2. 或在 config.yaml 中配置 api_key')
    print()

# 加载配置
with open('config/config.yaml', 'r', encoding='utf-8') as f:
    config_data = yaml.safe_load(f)

ai_config = config_data.get('ai', {})
print(f'  配置中的模型: {ai_config.get("MODEL")}')
print(f'  配置中的 API Key: {"已设置" if ai_config.get("api_key") else "未设置"}')
print(f'  配置中的 API Base: {ai_config.get("api_base") or "未设置"}')
print()

# 数据收集
print('步骤 2: 数据收集')
community_config = config_data.get('community', {})
collector = CommunityCollector.from_config(community_config)
collected_data = collector.collect()

print(f'✅ 数据收集完成: {collected_data.total_items} 条')
print()

# 创建 AI 分析器
print('步骤 3: 创建 AI 分析器')
try:
    analyzer = CommunityAnalyzer.from_config(community_config)
    print('✅ AI 分析器创建成功')
    print(f'  AI 客户端已初始化: {analyzer.ai_client is not None}')
    print()
except Exception as e:
    print(f'❌ AI 分析器创建失败: {e}')
    print()
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 测试 AI 调用
print('步骤 4: 测试 AI 调用')
test_messages = [
    {"role": "system", "content": "你是一个科技内容分析助手。"},
    {"role": "user", "content": "简单测试：请回复'测试成功'三个字。"}
]

try:
    print('  发送测试消息到 AI...')
    response = analyzer.ai_client.chat(test_messages)
    print(f'  ✅ AI 响应: {response[:100] if response else "None"}...')
    print()
except Exception as e:
    print(f'  ❌ AI 调用失败: {e}')
    print()
    import traceback
    traceback.print_exc()
    print()

# 完整分析测试（详细模式）
print('步骤 5: 完整分析测试（详细模式）')
print('  这将分析每个来源的 5 个案例，可能需要 5-10 分钟...')
print()

try:
    print('  开始分析...')
    analysis_result = analyzer.analyze(
        collected_data,
        quick_mode=False,  # 使用详细模式
        items_per_source=5  # 每个来源分析 5 个案例
    )

    print()
    print('✅ 分析完成')
    print(f'  success: {analysis_result.success}')
    print(f'  error: {analysis_result.error}')
    print(f'  scored_items: {len(analysis_result.scored_items)}')
    print(f'  source_analyses: {len(analysis_result.source_analyses)}')
    print(f'  overall_summary 长度: {len(analysis_result.overall_summary) if analysis_result.overall_summary else 0} 字符')
    print()

    # 显示分析结果
    if analysis_result.source_analyses:
        print('📊 分析结果:')
        for source_id, source_analysis in analysis_result.source_analyses.items():
            print(f'\n  {source_analysis.source_name}:')
            if source_analysis.summary:
                print(f'    摘要: {source_analysis.summary[:200]}...')
            else:
                print(f'    摘要: 无')

            if source_analysis.highlights:
                print(f'    亮点 ({len(source_analysis.highlights)} 条):')
                for highlight in source_analysis.highlights[:3]:
                    print(f'      - {highlight[:80]}...')

            if source_analysis.trends:
                print(f'    趋势 ({len(source_analysis.trends)} 条):')
                for trend in source_analysis.trends[:3]:
                    print(f'      - {trend[:80]}...')

    print()
    print('=' * 80)
    print('✅ 完整测试完成！')
    print('=' * 80)
    print()
    print('如果 analysis_result.success 为 True 且有内容，则 AI 分析正常工作。')

except Exception as e:
    import traceback
    print()
    print('=' * 80)
    print('❌ 完整分析失败')
    print('=' * 80)
    print(f'错误: {type(e).__name__}: {e}')
    print()
    print('详细错误堆栈:')
    print(traceback.format_exc())
