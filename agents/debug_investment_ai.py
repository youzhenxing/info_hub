#!/usr/bin/env python3
# coding=utf-8
"""
投资模块 AI 分析调试脚本
"""

import os
import sys
import json
from pathlib import Path

# 清除代理
proxy_vars = [
    'all_proxy', 'ALL_PROXY',
    'http_proxy', 'HTTP_PROXY',
    'https_proxy', 'HTTPS_PROXY',
]
for var in proxy_vars:
    if var in os.environ:
        del os.environ[var]

# 添加项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 加载环境变量
env_file = PROJECT_ROOT / "agents" / ".env"
if env_file.exists():
    with open(env_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                if 'proxy' not in key.lower():
                    os.environ[key] = value

print("="*60)
print("🔍 投资模块 AI 分析调试")
print("="*60)

try:
    from trendradar.core.loader import load_config
    from trendradar.investment.collector import InvestmentCollector
    from trendradar.investment.analyzer import InvestmentAnalyzer

    # 加载配置
    config = load_config()

    # 收集数据
    print("\n1️⃣ 收集投资数据...")
    collector = InvestmentCollector.from_config(config)
    data = collector.collect()

    print(f"  ✅ 数据收集完成")
    print(f"      - 指数: {len(data.market_snapshot.indices) if data.market_snapshot else 0} 个")
    print(f"      - 个股: {len(data.market_snapshot.stocks) if data.market_snapshot else 0} 个")
    print(f"      - 加密货币: {len(data.market_snapshot.crypto) if data.market_snapshot else 0} 个")
    print(f"      - 新闻: {len(data.news) if data.news else 0} 条")

    if not data.news:
        print("\n❌ 没有新闻数据，无法测试 AI 分析")
        sys.exit(1)

    # 只分析第一篇新闻
    print(f"\n2️⃣ 分析第一篇新闻...")
    print(f"  标题: {data.news[0].title[:50]}...")

    analyzer = InvestmentAnalyzer.from_config(config)

    # 调试：查看 AI 的原始响应
    print(f"\n3️⃣ 调试 AI 调用...")

    # 模拟调用 - 使用和实际代码相同的方式
    from trendradar.investment.analyzer import ArticleAnalysis

    # 构建 prompt
    news = data.news[0]
    prompt = analyzer.article_prompt

    # 获取内容（和实际代码一样）
    content = news.summary or ""
    if not content:
        content = news.title

    print(f"  文章标题: {news.title}")
    print(f"  内容长度: {len(content)} 字符")
    print(f"  内容预览: {content[:100]}...")

    # 调用 AI - 使用和实际代码完全相同的方式
    messages = [
        {"role": "user", "content": prompt.format(
            title=news.title,
            source=news.source,
            content=content
        )}
    ]

    print(f"\n  调用 AI...")
    response = analyzer.ai_client.chat(messages)
    print(f"  ✅ AI 响应长度: {len(response)} 字符")

    # 显示响应前500字符
    print(f"\n  AI 响应预览（前500字符）:")
    print("  " + response[:500].replace("\n", "\n  "))

    # 尝试解析
    print(f"\n4️⃣ 解析 JSON...")

    import re
    json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
    if json_match:
        json_str = json_match.group(1)
        print(f"  ✅ 找到 JSON 块")
    else:
        json_str = response
        print(f"  ⚠️  未找到 JSON 块，使用完整响应")

    print(f"\n  JSON 内容预览（前500字符）:")
    print("  " + json_str[:500].replace("\n", "\n  "))

    # 尝试解析
    try:
        data = json.loads(json_str)
        print(f"\n  ✅ JSON 解析成功")
        print(f"  - summary: {data.get('summary', 'N/A')}")
        print(f"  - category: {data.get('category', 'N/A')}")
        print(f"  - entities: {len(data.get('entities', []))} 个")

        if data.get('summary') == '\n  "summary"':
            print(f"\n  ❌ summary 字段值异常，不是预期的摘要内容")

    except json.JSONDecodeError as e:
        print(f"\n  ❌ JSON 解析失败: {e}")
        print(f"  错误位置: {str(e)}")

    print("\n" + "="*60)
    print("✅ 调试完成")
    print("="*60)

except Exception as e:
    print(f"\n❌ 调试失败: {e}")
    import traceback
    traceback.print_exc()
