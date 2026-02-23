#!/usr/bin/env python3
"""
查找播客的替代RSS源
"""
import requests
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Tuple

# 需要查找替代源的播客
PROBLEM_FEEDS = [
    ("硅谷101", "5e5c52c9418a84a04625e6cc"),
    ("硬地骇客", "640ee2438be5d40013fe4a87"),
    ("晚安咖啡GoodNightCoffee", "674b16830ed328720a7b9144"),
    ("十字路口Crossing", "60502e253c92d4f62c2a9577"),
    ("中金研究院", "610d156f5df6959814391430"),
]

# 其他RSSHub实例
RSSHUB_MIRRORS = [
    "https://rsshub.app",
    "https://rss.huaweijun.com",
    "https://rss.qinqique.com",
]

ALTERNATIVE_RSS = {
    "Acquired": [
        "https://feeds.acast.com/public/shows/acquired",
        "https://feeds.transistor.fm/acquired",
        "https://feeds.megaphone.fm/acquired",
    ],
    "Latent Space": [
        "https://www.latent.space/feed",
        "https://feeds.transistor.fm/latent-space",
    ],
    "Modern Wisdom": [
        "https://feeds.acast.com/public/shows/modern-wisdom",
    ],
    "Anything Goes with Emma Chamberlain": [
        "https://feeds.acast.com/public/shows/anything-goes",
    ],
    "The Joe Rogan Experience": [
        "https://feeds.libsyn.com/125135/rss",
    ],
    "The Diary of a CEO": [
        "https://feeds.transistor.fm/the-diary-of-a-ceo",
        "https://rss.com/podcasts/the-diary-of-a-ceo/feed.xml",
    ],
}


def test_url(url: str, timeout: int = 10) -> Tuple[bool, str]:
    """测试URL是否可访问"""
    try:
        response = requests.get(url, timeout=timeout, allow_redirects=True)
        if response.status_code == 200:
            return True, f"HTTP {response.status_code}"
        else:
            return False, f"HTTP {response.status_code}"
    except Exception as e:
        return False, str(e)[:50]


def find_xiaoyuzhou_alternative(name: str, podcast_id: str) -> List[Tuple[str, bool]]:
    """为小宇宙播客查找替代RSS源"""
    alternatives = []

    # 尝试不同的RSSHub实例
    for mirror in RSSHUB_MIRRORS:
        url = f"{mirror}/xiaoyuzhou/podcast/{podcast_id}"
        success, message = test_url(url)
        alternatives.append((url, success))

    return alternatives


def find_standard_alternative(name: str) -> List[Tuple[str, bool]]:
    """为标准播客查找替代RSS源"""
    if name not in ALTERNATIVE_RSS:
        return []

    alternatives = []
    for url in ALTERNATIVE_RSS[name]:
        success, message = test_url(url)
        alternatives.append((url, success))

    return alternatives


def main():
    """主函数"""
    print("=" * 80)
    print("查找替代RSS源")
    print("=" * 80)
    print()

    all_alternatives = []

    # 查找小宇宙播客的替代源
    print("【小宇宙播客】查找替代RSSHub实例:")
    print("-" * 80)

    for name, podcast_id in PROBLEM_FEEDS:
        print(f"\n{name}:")
        alternatives = find_xiaoyuzhou_alternative(name, podcast_id)

        for url, success in alternatives:
            status = "✓" if success else "✗"
            print(f"  {status} {url}")
            if success:
                all_alternatives.append((name, url))

    # 查找其他播客的替代源
    print("\n" + "=" * 80)
    print("【其他播客】查找替代RSS源:")
    print("-" * 80)

    for name in ALTERNATIVE_RSS.keys():
        print(f"\n{name}:")
        alternatives = find_standard_alternative(name)

        if not alternatives:
            print("  (无预配置的替代源)")
            continue

        for url, success in alternatives:
            status = "✓" if success else "✗"
            print(f"  {status} {url}")
            if success:
                all_alternatives.append((name, url))

    # 输出结果
    print("\n" + "=" * 80)
    print("找到可用的替代RSS源:")
    print("-" * 80)

    if all_alternatives:
        for name, url in sorted(all_alternatives, key=lambda x: x[0]):
            print(f"[{name}]")
            print(f"  {url}")
            print()
    else:
        print("未找到可用的替代RSS源")

    print("=" * 80)


if __name__ == "__main__":
    main()
