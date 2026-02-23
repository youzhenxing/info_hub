#!/usr/bin/env python3
"""
诊断 AI 分析失败的原因
"""

import sys
sys.path.insert(0, '/home/zxy/Documents/code/TrendRadar')

import yaml
from trendradar.community.collector import CommunityCollector
from trendradar.community.analyzer import CommunityAnalyzer

print('=' * 80)
print('AI 分析问题诊断')
print('=' * 80)
print()

# 加载配置
with open('config/config.yaml', 'r', encoding='utf-8') as f:
    config_data = yaml.safe_load(f)

community_config = config_data.get('community', {})

# 步骤 1: 数据收集
print('步骤 1: 数据收集')
collector = CommunityCollector.from_config(community_config)
collected_data = collector.collect()

print(f'✅ 数据收集完成')
print(f'  类型: {type(collected_data)}')
print(f'  total_items: {collected_data.total_items}')
print(f'  sources: {list(collected_data.sources.keys())}')
print()

# 步骤 2: 检查数据类型
print('步骤 2: 检查数据类型')
print(f'  collected_data 类型: {type(collected_data)}')
print(f'  是否有 sources 属性: {hasattr(collected_data, "sources")}')
print(f'  sources 类型: {type(collected_data.sources)}')
print()

# 步骤 3: 测试 AI 分析（关闭快速模式）
print('步骤 3: 测试 AI 分析（详细模式）')
analyzer = CommunityAnalyzer.from_config(community_config)

try:
    print('  调用 analyzer.analyze(collected_data, quick_mode=False)...')
    analysis_result = analyzer.analyze(collected_data, quick_mode=False, items_per_source=5)

    print(f'\n✅ AI 分析成功')
    print(f'  success: {analysis_result.success}')
    print(f'  error: {analysis_result.error}')
    print(f'  scored_items: {len(analysis_result.scored_items)}')
    print(f'  source_analyses: {len(analysis_result.source_analyses)}')
    print(f'  overall_summary: {len(analysis_result.overall_summary) if analysis_result.overall_summary else 0} 字符')

    # 显示分析结果
    if analysis_result.source_analyses:
        print('\n  分析结果:')
        for source_id, source_analysis in analysis_result.source_analyses.items():
            print(f'    - {source_analysis.source_name}:')
            print(f'      摘要: {source_analysis.summary[:100] if source_analysis.summary else "无"}...')
            print(f'      案例数: {len(source_analysis.item_analyses)}')

except Exception as e:
    import traceback
    print(f'\n❌ AI 分析失败')
    print(f'  错误: {type(e).__name__}: {e}')
    print(f'\n  详细堆栈:')
    print(traceback.format_exc())
