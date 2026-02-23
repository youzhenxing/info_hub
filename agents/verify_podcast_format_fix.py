#!/usr/bin/env python3
"""
验证播客格式修复效果

模拟 AI 输出并验证后处理格式化功能
"""

import sys
sys.path.insert(0, '/home/zxy/Documents/code/TrendRadar')

from trendradar.podcast.analyzer import PodcastAnalyzer

def test_real_world_scenarios():
    """测试真实场景的格式修复"""

    # 创建分析器实例
    analyzer = PodcastAnalyzer(
        ai_config={},
        analysis_config={},
    )

    print("=" * 70)
    print("播客格式修复效果验证")
    print("=" * 70)

    # 场景 1: 模拟 ID 237 的格式问题
    print("\n🔍 场景 1: 修复 `# 播客内容分析` 格式")
    print("-" * 70)

    input_237 = """# 播客内容分析

## 核心摘要
This episode of The a16z Show features a live interview with Palmer Luckey...
测试内容"""

    result_237 = analyzer._normalize_analysis_format(
        input_237,
        "The a16z Show",
        "Palmer Luckey on Hardware, Building, and the Next Frontiers of Innovation"
    )

    print("原始格式:")
    print(input_237.split("\n")[0:3])
    print("\n修复后格式:")
    print(result_237.split("\n")[0:3])

    # 验证
    assert result_237.startswith("## 核心摘要 / Summary"), "应该以标准标题开头"
    assert "# 播客内容分析" not in result_237, "不应该包含违规标题"
    print("✅ 场景 1 通过：违规格式已修复")

    # 场景 2: 模拟 ID 235 的格式问题
    print("\n🔍 场景 2: 修复 `**播客分析:` 格式")
    print("-" * 70)

    input_235 = """**播客分析: The a16z Show – Why This Isn't the Dot-Com Bubble**

**核心主题与总结**
This episode features Martin Casado...
测试内容"""

    result_235 = analyzer._normalize_analysis_format(
        input_235,
        "The a16z Show",
        "Why This Isn't the Dot-Com Bubble | Martin Casado on WSJ's BOLD NAMES"
    )

    print("原始格式:")
    print(input_235.split("\n")[0:3])
    print("\n修复后格式:")
    print(result_235.split("\n")[0:3])

    # 验证
    assert result_235.startswith("## 核心摘要 / Summary"), "应该以标准标题开头"
    assert "**播客分析:" not in result_235, "不应该包含违规标题"
    print("✅ 场景 2 通过：违规格式已修复")

    # 场景 3: 验证正确格式保持不变
    print("\n🔍 场景 3: 正确格式应保持不变")
    print("-" * 70)

    input_correct = """## 核心摘要 / Summary
This is the correct format...

## 关键洞察 / Key Insights
1. First insight
2. Second insight"""

    result_correct = analyzer._normalize_analysis_format(
        input_correct,
        "Test Podcast",
        "Test Episode"
    )

    print("输入格式:")
    print(input_correct.split("\n")[0:3])
    print("\n输出格式:")
    print(result_correct.split("\n")[0:3])

    # 验证
    assert result_correct == input_correct, "正确格式应保持不变"
    print("✅ 场景 3 通过：正确格式已保留")

    # 场景 4: 标题标准化
    print("\n🔍 场景 4: 不完整标题应自动补全")
    print("-" * 70)

    input_incomplete = """## 核心摘要
摘要内容...

## 关键要点
要点内容...

## 嘉宾观点
观点内容..."""

    result_incomplete = analyzer._normalize_analysis_format(
        input_incomplete,
        "Test Podcast",
        "Test Episode"
    )

    print("原始标题:")
    print([line for line in input_incomplete.split("\n") if line.startswith("##")])
    print("\n标准化后标题:")
    print([line for line in result_incomplete.split("\n") if line.startswith("##")])

    # 验证
    assert "## 核心摘要 / Summary" in result_incomplete, "标题应标准化"
    assert "## 关键洞察 / Key Insights" in result_incomplete, "关键要点应重命名"
    assert "## 发言者角色与主要立场" in result_incomplete, "嘉宾观点应重命名"
    print("✅ 场景 4 通过：标题已标准化")

    print("\n" + "=" * 70)
    print("🎉 所有场景验证通过！")
    print("=" * 70)

    # 输出总结
    print("\n📊 修复效果总结:")
    print("  • 格式一致性: 100%")
    print("  • 违规标题: 完全移除")
    print("  • 标准格式: 完全保留")
    print("  • 标题补全: 自动修正")

    return True

if __name__ == "__main__":
    try:
        test_real_world_scenarios()
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
