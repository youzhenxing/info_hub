#!/usr/bin/env python3
# coding=utf-8
"""
使用之前的 AI 分析结果重新渲染播客邮件（应用移动端修复）
"""

import sys
from pathlib import Path

# 添加项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

def main():
    """重新渲染播客邮件"""
    from trendradar.core.loader import load_config
    from trendradar.podcast.fetcher import PodcastFetcher, PodcastFeedConfig
    from trendradar.podcast.notifier import PodcastNotifier
    from datetime import datetime

    print("="*60)
    print("🎙️ 播客邮件重新渲染 - 应用移动端修复")
    print("="*60)

    # 加载配置
    config = load_config()

    # 获取播客
    print("\n  📡 获取播客源...")
    podcast_config = config.get("PODCAST", config.get("podcast", {}))
    feeds_config = podcast_config.get("feeds", podcast_config.get("FEEDS", []))

    if not feeds_config:
        feeds_config = [{"name": "硅谷101", "url": "https://feeds.buzzsprout.com/1930654.rss", "enabled": True}]

    feeds = []
    for f in feeds_config:
        if isinstance(f, dict):
            feed_id = f.get("feed_id", f.get("name", "unknown").lower().replace(" ", "_"))
            feeds.append(PodcastFeedConfig(
                id=feed_id,
                name=f.get("name", "Unknown"),
                url=f.get("url", ""),
                enabled=f.get("enabled", True),
                max_items=f.get("max_items", 10),
            ))
        else:
            feeds.append(f)

    fetcher = PodcastFetcher(feeds)
    all_episodes = fetcher.fetch_all()

    # 获取第一个节目
    episodes = None
    for feed_id, eps in all_episodes.items():
        if eps:
            episodes = eps
            break

    if not episodes:
        print("  ❌ 未获取到播客节目")
        return False

    episode = episodes[0]
    print(f"  ✅ 获取到节目: {episode.title}")

    # 读取之前保存的 AI 分析结果
    print("\n  📄 读取之前的 AI 分析结果...")
    old_html_file = PROJECT_ROOT / "agents" / "e2e_output" / "podcast_prerelease_153809.html"

    if not old_html_file.exists():
        print(f"  ❌ 文件不存在: {old_html_file}")
        return False

    old_html = old_html_file.read_text(encoding="utf-8")

    # 提取 AI 分析部分（在 <div class="card-body"> 标签内）
    import re
    match = re.search(r'<div class="card-body">(.*?)</div>\s*</div>\s*</section>', old_html, re.DOTALL)

    if not match:
        print("  ❌ 无法提取 AI 分析内容")
        return False

    analysis_content = match.group(1)
    print(f"  ✅ 提取到 AI 分析内容: {len(analysis_content)} 字符")

    # 重新渲染邮件（会应用新的过滤器）
    print("\n  📧 重新渲染邮件...")
    notifier = PodcastNotifier.from_config(config)
    html_content = notifier._render_email_html(episode, "", analysis_content)

    # 验证修复效果
    print("\n  🔍 验证移动端优化效果:")

    if "语言规则" in html_content or "原文语言为" in html_content:
        print("  ❌ 未移除语言规则元信息")
    else:
        print("  ✅ 已移除语言规则元信息")

    hr_count = html_content.count('<hr')
    print(f"  📊 分隔线数量: {hr_count}")
    if hr_count < 8:
        print("  ✅ 已减少分隔线数量")
    else:
        print("  ⚠️ 分隔线仍然较多")

    if "@media (max-width: 480px)" in html_content:
        print("  ✅ 包含移动端响应式样式")
    else:
        print("  ❌ 缺少移动端响应式样式")

    # 保存新 HTML
    output_dir = PROJECT_ROOT / "agents" / "e2e_output"
    html_file = output_dir / f"podcast_mobile_fixed_{datetime.now().strftime('%H%M%S')}.html"
    html_file.write_text(html_content, encoding="utf-8")
    print(f"\n  💾 新 HTML 已保存: {html_file}")
    print(f"  📱 请在手机上查看效果，应该看到：")
    print(f"     - ✅ 无\"语言规则\"等乱码")
    print(f"     - ✅ 更少的分隔线")
    print(f"     - ✅ 更大的文字（14px）和更宽的显示区域")

    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
