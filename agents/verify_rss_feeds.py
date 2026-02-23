#!/usr/bin/env python3
"""
验证播客RSS订阅链接的有效性
"""
import requests
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Tuple

# RSS订阅列表
RSS_FEEDS = [
    # 中文播客
    ("硅谷101", "https://rsshub.bestblogs.dev/xiaoyuzhou/podcast/5e5c52c9418a84a04625e6cc"),
    ("晚点聊LateTalk", "https://feeds.fireside.fm/latetalk/rss"),
    ("硬地骇客", "https://rsshub.bestblogs.dev/xiaoyuzhou/podcast/640ee2438be5d40013fe4a87"),
    ("晚安咖啡GoodNightCoffee", "https://rsshub.bestblogs.dev/xiaoyuzhou/podcast/674b16830ed328720a7b9144"),
    ("投资实战派", "https://feeds.soundon.fm/podcasts/811969b4-4493-407e-8aeb-ed413cf5d90d.xml"),
    ("十字路口Crossing", "https://rsshub.bestblogs.dev/xiaoyuzhou/podcast/60502e253c92d4f62c2a9577"),
    ("The Prompt", "https://rsshub.bestblogs.dev/xiaoyuzhou/podcast/6101a3936c68b8a230638ad8"),
    ("The Alphaist", "https://rsshub.bestblogs.dev/xiaoyuzhou/podcast/690b589170e20ba3f0553778"),
    ("On Board", "https://rsshub.bestblogs.dev/xiaoyuzhou/podcast/61cbaac48bb4cd867fcabe22"),
    ("中金研究院", "https://rsshub.bestblogs.dev/xiaoyuzhou/podcast/610d156f5df6959814391430"),

    # 英文播客
    ("Latent Space", "https://rss.art19.com/latent-space-ai"),
    ("Lex Fridman Podcast", "https://lexfridman.com/feed/podcast/"),
    ("The Joe Rogan Experience", "https://feeds.megaphone.fm/GLT1412515089"),
    ("Acquired", "https://feeds.transistor.fm/acquired"),
    ("Business Breakdowns", "https://feeds.megaphone.fm/breakdowns"),
    ("Huberman Lab", "https://feeds.megaphone.fm/hubermanlab"),
    ("Modern Wisdom", "https://feeds.megaphone.fm/modernwisdom"),
    ("Anything Goes with Emma Chamberlain", "https://feeds.megaphone.fm/stupid-genius"),
    ("The Diary of a CEO", "https://feeds.acast.com/public/shows/the-diary-of-a-ceo"),
]


def verify_rss_feed(name: str, url: str, timeout: int = 15) -> Tuple[str, str, bool, str]:
    """
    验证单个RSS feed

    Args:
        name: 播客名称
        url: RSS链接
        timeout: 超时时间（秒）

    Returns:
        (name, url, is_valid, message)
    """
    try:
        response = requests.get(url, timeout=timeout, allow_redirects=True)
        response.raise_for_status()

        # 尝试解析XML
        ET.fromstring(response.content)

        # 检查是否包含RSS相关元素
        content = response.text
        if any(tag in content for tag in ['<rss', '<feed>', '<channel>']):
            return (name, url, True, f"✓ 有效 (HTTP {response.status_code})")
        else:
            return (name, url, False, f"✗ 不是有效的RSS格式")

    except requests.exceptions.Timeout:
        return (name, url, False, f"✗ 超时 (>{timeout}秒)")
    except requests.exceptions.HTTPError as e:
        return (name, url, False, f"✗ HTTP错误: {e.response.status_code}")
    except requests.exceptions.RequestException as e:
        return (name, url, False, f"✗ 请求失败: {str(e)}")
    except ET.ParseError:
        return (name, url, False, f"✗ XML解析失败")
    except Exception as e:
        return (name, url, False, f"✗ 未知错误: {str(e)}")


def main():
    """主函数"""
    print("=" * 80)
    print("播客RSS订阅链接验证报告")
    print("=" * 80)
    print()

    valid_feeds = []
    invalid_feeds = []

    # 使用线程池并发验证
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(verify_rss_feed, name, url): (name, url)
            for name, url in RSS_FEEDS
        }

        for future in as_completed(futures):
            name, url, is_valid, message = future.result()
            if is_valid:
                valid_feeds.append((name, url, message))
            else:
                invalid_feeds.append((name, url, message))

    # 打印结果
    print(f"✓ 有效的RSS订阅 ({len(valid_feeds)}个):")
    print("-" * 80)
    for name, url, message in sorted(valid_feeds, key=lambda x: x[0]):
        print(f"{message}")
        print(f"  [{name}]")
        print(f"  {url}")
        print()

    if invalid_feeds:
        print()
        print(f"✗ 无效的RSS订阅 ({len(invalid_feeds)}个):")
        print("-" * 80)
        for name, url, message in sorted(invalid_feeds, key=lambda x: x[0]):
            print(f"{message}")
            print(f"  [{name}]")
            print(f"  {url}")
            print()

    # 总结
    print()
    print("=" * 80)
    print(f"验证完成: 共 {len(RSS_FEEDS)} 个RSS订阅")
    print(f"  - 有效: {len(valid_feeds)} 个 ({len(valid_feeds)*100//len(RSS_FEEDS)}%)")
    print(f"  - 无效: {len(invalid_feeds)} 个 ({len(invalid_feeds)*100//len(RSS_FEEDS)}%)")
    print("=" * 80)

    # 生成修复建议
    if invalid_feeds:
        print()
        print("修复建议:")
        print("-" * 80)
        for name, url, message in invalid_feeds:
            if "rsshub" in url:
                print(f"[{name}]")
                print(f"  - 尝试使用其他RSSHub实例: https://rsshub.app/xiaoyuzhou/podcast/{{id}}")
                print(f"  - 或者查找该播客在其他平台的RSS链接")
                print()
            elif "timeout" in message.lower():
                print(f"[{name}]")
                print(f"  - 网络连接超时，可能是网络问题或服务器响应慢")
                print(f"  - 建议稍后重试或使用VPN")
                print()


if __name__ == "__main__":
    main()
