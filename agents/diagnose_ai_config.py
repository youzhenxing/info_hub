#!/usr/bin/env python3
"""
诊断 AI 配置和 API 调用
"""

import sys
import os
sys.path.insert(0, '/home/zxy/Documents/code/TrendRadar')

import yaml
from trendradar.ai.client import AIClient

print('=' * 80)
print('AI 配置和 API 调用诊断')
print('=' * 80)
print()

# 加载配置
with open('config/config.yaml', 'r', encoding='utf-8') as f:
    config_data = yaml.safe_load(f)

# 步骤 1: 检查全局 AI 配置
print('步骤 1: 检查全局 AI 配置')
ai_config = config_data.get('ai', {})
print(f'  ai.model: {ai_config.get("model")}')
print(f'  ai.api_key: {"已设置" if ai_config.get("api_key") else "未设置"}')
print(f'  ai.api_base: {ai_config.get("api_base") or "未设置"}')
print()

# 步骤 2: 检查 community.analysis 配置
print('步骤 2: 检查 community.analysis 配置')
community_config = config_data.get('community', {})
analysis_config = community_config.get('analysis', {})
print(f'  community.analysis.model: {analysis_config.get("model")}')
print(f'  community.analysis.api_key: {"已设置" if analysis_config.get("api_key") else "未设置"}')
print(f'  community.analysis.api_base: {analysis_config.get("api_base")}')
print()

# 步骤 3: 确定最终使用的配置
print('步骤 3: 确定最终使用的配置')
final_model = (analysis_config.get("MODEL") or analysis_config.get("model") or
               ai_config.get("MODEL") or ai_config.get("model"))
final_api_base = (analysis_config.get("API_BASE") or analysis_config.get("api_base") or
                  ai_config.get("API_BASE") or ai_config.get("api_base"))
final_api_key = (analysis_config.get("API_KEY") or analysis_config.get("api_key") or
                 ai_config.get("API_KEY") or ai_config.get("api_key") or
                 os.environ.get("AI_API_KEY", ""))

print(f'  最终 model: {final_model}')
print(f'  最终 api_base: {final_api_base or "未设置"}')
print(f'  最终 api_key: {"已设置" if final_api_key else "未设置"}')
print()

# 步骤 4: 创建 AI 客户端
print('步骤 4: 创建 AI 客户端')
try:
    ai_client_config = {
        "model": final_model,
        "api_base": final_api_base,
        "api_key": final_api_key,
        "temperature": 0.7,
        "max_tokens": 1000,
        "timeout": 120,
    }

    client = AIClient(ai_client_config)
    print('  ✅ AI 客户端创建成功')
    print(f'  client.model: {client.model}')
    print(f'  client.api_base: {client.api_base}')
    print(f'  client.api_key: {"已设置" if client.api_key else "未设置"}')
    print()

except Exception as e:
    print(f'  ❌ AI 客户端创建失败: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 步骤 5: 测试 AI 调用
print('步骤 5: 测试 AI 调用')
test_messages = [
    {"role": "system", "content": "你是一个助手。"},
    {"role": "user", "content": "你好，请用一句话介绍你自己。"}
]

try:
    print('  发送测试消息到 AI...')
    response = client.chat(test_messages)
    print(f'  ✅ AI 响应成功')
    print(f'  响应类型: {type(response)}')
    print(f'  响应内容: {response[:200] if response else "None"}...')
    print()

except Exception as e:
    print(f'  ❌ AI 调用失败')
    print(f'  错误: {type(e).__name__}: {e}')
    print()
    import traceback
    print('  详细堆栈:')
    print(traceback.format_exc())
    print()
    sys.exit(1)

print('=' * 80)
print('✅ 所有测试通过！AI 配置和 API 调用正常')
print('=' * 80)
