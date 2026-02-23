#!/usr/bin/env python3
# coding=utf-8
"""
验证模板集成脚本

验证所有模块是否正确使用了新的 EmailRenderer 模板系统
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime

# 添加项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def verify_template_marker(html_content: str, expected_theme: str) -> bool:
    """
    验证 HTML 是否包含新模板标记
    
    新模板特征：<body class="theme-{module}">
    """
    marker = f'class="theme-{expected_theme}"'
    return marker in html_content


def test_investment_notifier():
    """测试投资模块 Notifier 集成"""
    print("\n📈 测试投资模块 Notifier...")
    
    try:
        # 读取测试数据
        test_data_file = PROJECT_ROOT / "agents" / "test_data" / "investment_test_data.json"
        if not test_data_file.exists():
            print(f"  ⚠️ 测试数据文件不存在: {test_data_file}")
            return False
        
        with open(test_data_file, 'r', encoding='utf-8') as f:
            test_data = json.load(f)
        
        # 使用 EmailRenderer 直接渲染（模拟 notifier 的调用方式）
        from shared.lib.email_renderer import EmailRenderer
        renderer = EmailRenderer()
        
        html = renderer.render_module_email(
            module='investment',
            template_name='daily_report.html',
            context=test_data
        )
        
        # 验证新模板标记
        if verify_template_marker(html, 'investment'):
            print("  ✅ 使用新模板 (theme-investment)")
            
            # 保存输出
            output_file = PROJECT_ROOT / "agents" / "e2e_output" / "investment_verify.html"
            output_file.parent.mkdir(parents=True, exist_ok=True)
            output_file.write_text(html, encoding='utf-8')
            print(f"  💾 已保存: {output_file}")
            return True
        else:
            print("  ❌ 未使用新模板")
            return False
            
    except Exception as e:
        print(f"  ❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_podcast_notifier():
    """测试播客模块 Notifier 集成"""
    print("\n🎙️ 测试播客模块 Notifier...")
    
    try:
        # 读取测试数据
        test_data_file = PROJECT_ROOT / "agents" / "test_data" / "podcast_test_data.json"
        if not test_data_file.exists():
            print(f"  ⚠️ 测试数据文件不存在: {test_data_file}")
            return False
        
        with open(test_data_file, 'r', encoding='utf-8') as f:
            test_data = json.load(f)
        
        # 使用 EmailRenderer 直接渲染
        from shared.lib.email_renderer import EmailRenderer
        renderer = EmailRenderer()
        
        html = renderer.render_module_email(
            module='podcast',
            template_name='episode_update.html',
            context=test_data
        )
        
        # 验证新模板标记
        if verify_template_marker(html, 'podcast'):
            print("  ✅ 使用新模板 (theme-podcast)")
            
            # 保存输出
            output_file = PROJECT_ROOT / "agents" / "e2e_output" / "podcast_verify.html"
            output_file.parent.mkdir(parents=True, exist_ok=True)
            output_file.write_text(html, encoding='utf-8')
            print(f"  💾 已保存: {output_file}")
            return True
        else:
            print("  ❌ 未使用新模板")
            return False
            
    except Exception as e:
        print(f"  ❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_community_notifier():
    """测试社区模块 Notifier 集成"""
    print("\n🌐 测试社区模块 Notifier...")
    
    try:
        # 读取测试数据
        test_data_file = PROJECT_ROOT / "agents" / "test_data" / "community_test_data.json"
        if not test_data_file.exists():
            print(f"  ⚠️ 测试数据文件不存在: {test_data_file}")
            return False
        
        with open(test_data_file, 'r', encoding='utf-8') as f:
            test_data = json.load(f)
        
        # 使用 EmailRenderer 直接渲染
        from shared.lib.email_renderer import EmailRenderer
        renderer = EmailRenderer()
        
        html = renderer.render_module_email(
            module='community',
            template_name='daily_report.html',
            context=test_data
        )
        
        # 验证新模板标记
        if verify_template_marker(html, 'community'):
            print("  ✅ 使用新模板 (theme-community)")
            
            # 保存输出
            output_file = PROJECT_ROOT / "agents" / "e2e_output" / "community_verify.html"
            output_file.parent.mkdir(parents=True, exist_ok=True)
            output_file.write_text(html, encoding='utf-8')
            print(f"  💾 已保存: {output_file}")
            return True
        else:
            print("  ❌ 未使用新模板")
            return False
            
    except Exception as e:
        print(f"  ❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_wechat_notifier():
    """测试公众号模块 Notifier 集成"""
    print("\n📱 测试公众号模块 Notifier...")
    
    try:
        # 读取测试数据
        test_data_file = PROJECT_ROOT / "agents" / "test_data" / "wechat_test_data.json"
        if not test_data_file.exists():
            print(f"  ⚠️ 测试数据文件不存在: {test_data_file}")
            return False
        
        with open(test_data_file, 'r', encoding='utf-8') as f:
            test_data = json.load(f)
        
        # 使用 EmailRenderer 直接渲染
        from shared.lib.email_renderer import EmailRenderer
        renderer = EmailRenderer()
        
        html = renderer.render_module_email(
            module='wechat',
            template_name='daily_report.html',
            context=test_data
        )
        
        # 验证新模板标记
        if verify_template_marker(html, 'wechat'):
            print("  ✅ 使用新模板 (theme-wechat)")
            
            # 保存输出
            output_file = PROJECT_ROOT / "agents" / "e2e_output" / "wechat_verify.html"
            output_file.parent.mkdir(parents=True, exist_ok=True)
            output_file.write_text(html, encoding='utf-8')
            print(f"  💾 已保存: {output_file}")
            return True
        else:
            print("  ❌ 未使用新模板")
            return False
            
    except Exception as e:
        print(f"  ❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_notifier_code():
    """验证 Notifier 代码是否包含 EmailRenderer 集成"""
    print("\n🔍 验证 Notifier 代码集成...")
    
    notifiers = {
        "投资模块": PROJECT_ROOT / "trendradar" / "investment" / "notifier.py",
        "播客模块": PROJECT_ROOT / "trendradar" / "podcast" / "notifier.py",
        "社区模块": PROJECT_ROOT / "trendradar" / "community" / "notifier.py",
        "公众号模块": PROJECT_ROOT / "wechat" / "src" / "notifier.py",
    }
    
    results = {}
    for name, path in notifiers.items():
        if not path.exists():
            print(f"  ⚠️ {name}: 文件不存在")
            results[name] = False
            continue
        
        content = path.read_text(encoding='utf-8')
        
        # 检查是否导入了 EmailRenderer
        has_import = 'from shared.lib.email_renderer import EmailRenderer' in content
        # 检查是否有 fallback 方法
        has_fallback = '_render_email_html_fallback' in content or '_builtin_daily_report_template' in content
        # 检查是否调用了 render_module_email
        has_render = 'render_module_email' in content
        
        if has_import and has_render:
            print(f"  ✅ {name}: 已集成 EmailRenderer" + (" (带 fallback)" if has_fallback else ""))
            results[name] = True
        else:
            print(f"  ❌ {name}: 未集成 EmailRenderer")
            results[name] = False
    
    return all(results.values())


def main():
    """主函数"""
    print("="*60)
    print("🔧 TrendRadar 模板集成验证")
    print("="*60)
    print(f"⏰ 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 验证代码集成
    code_ok = verify_notifier_code()
    
    # 验证模板渲染
    results = {
        "投资模块": test_investment_notifier(),
        "播客模块": test_podcast_notifier(),
        "社区模块": test_community_notifier(),
        "公众号模块": test_wechat_notifier(),
    }
    
    # 汇总结果
    print("\n" + "="*60)
    print("📊 验证结果汇总")
    print("="*60)
    
    print("\n代码集成:")
    print(f"  {'✅' if code_ok else '❌'} 所有模块代码已集成 EmailRenderer")
    
    print("\n模板渲染:")
    for name, ok in results.items():
        print(f"  {'✅' if ok else '❌'} {name}")
    
    success_count = sum(1 for ok in results.values() if ok)
    total_count = len(results)
    
    print(f"\n总计: {success_count}/{total_count} 模块验证通过")
    print(f"📁 输出目录: {PROJECT_ROOT / 'agents' / 'e2e_output'}")
    
    if success_count == total_count and code_ok:
        print("\n🎉 所有模块验证通过！可以进行发布。")
        return 0
    else:
        print("\n⚠️ 存在验证失败的模块，请检查。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
