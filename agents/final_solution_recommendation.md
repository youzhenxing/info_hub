# 社区模块最终解决方案

## 🎯 问题诊断结论

经过全面测试，发现：

1. **本地无法直接访问 Reddit/Twitter**（网络限制）
2. **通过 Clash 代理出现 TLS 握手失败**
3. **GitHub API 可以通过 Clash 代理正常访问**

**根本原因：** Clash 的 TLS 检查与 Reddit/Twitter 的 TLS 配置不兼容

---

## ✅ 可行的解决方案

### 方案 1：使用 Lighthouse 作为中转服务 ⭐⭐⭐⭐⭐

**架构：**
```
本地 TrendRadar → Lighthouse API → Reddit/Twitter
                   ↑
             (无需 TLS 检查)
```

**实施步骤：**

#### 步骤 1：在 Lighthouse 上部署简单的 API 服务

```bash
# SSH 登录到 Lighthouse
ssh root@43.162.100.95

# 安装 Flask
pip3 install flask feedparser requests

# 创建 API 服务
cat > /root/community_api.py << 'EOF'
from flask import Flask, jsonify
import requests
import feedparser

app = Flask(__name__)

@app.route('/reddit/<subreddit>')
def get_reddit(subreddit):
    """获取 Reddit 内容"""
    try:
        url = f"https://old.reddit.com/r/{subreddit}/.rss?limit=25"
        response = requests.get(url, timeout=15)
        feed = feedparser.parse(response.content)

        items = []
        for entry in feed.entries:
            items.append({
                'title': entry.get('title', ''),
                'url': entry.get('link', ''),
                'author': entry.get('author', ''),
                'published': entry.get('published', ''),
            })

        return jsonify({'status': 'success', 'items': items})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/twitter/<username>')
def get_twitter(username):
    """获取 Twitter 内容（通过 Nitter）"""
    nitter_instances = [
        "https://nitter.net",
        "https://nitter.poast.org",
    ]

    for nitter in nitter_instances:
        try:
            url = f"{nitter}/{username}/rss"
            response = requests.get(url, timeout=10)
            feed = feedparser.parse(response.content)

            items = []
            for entry in feed.entries:
                items.append({
                    'content': entry.get('summary', ''),
                    'url': entry.get('link', ''),
                    'author': entry.get('author', ''),
                })

            return jsonify({'status': 'success', 'items': items})
        except:
            continue

    return jsonify({'status': 'error', 'message': 'All Nitter instances failed'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
EOF

# 后台运行服务
nohup python3 /root/community_api.py > /root/api.log 2>&1 &
```

#### 步骤 2：本地测试

```bash
# 测试 Reddit API
curl http://43.162.100.95:5000/reddit/MachineLearning

# 测试 Twitter API
curl http://43.162.100.95:5000/twitter/elonmusk
```

#### 步骤 3：修改 TrendRadar 代码

**文件：** `trendradar/community/sources/reddit.py`

```python
class RedditSource:
    def __init__(self, ..., use_lighthouse=False, lighthouse_api=None):
        # ...
        self.use_lighthouse = use_lighthouse
        self.lighthouse_api = lighthouse_api or "http://43.162.100.95:5000"

    def fetch(self):
        if self.use_lighthouse:
            return self._fetch_via_lighthouse()
        else:
            return self._fetch_via_rss()

    def _fetch_via_lighthouse(self):
        """通过 Lighthouse API 获取数据"""
        all_items = []

        for sub_config in self.subreddits:
            try:
                url = f"{self.lighthouse_api}/reddit/{sub_config['name']}"
                response = self.session.get(url, timeout=30)
                data = response.json()

                if data['status'] == 'success':
                    for item in data['items']:
                        all_items.append(RedditItem(
                            id=f"reddit_{hash(item['url'])}",
                            title=item['title'],
                            url=item['url'],
                            score=0,
                            comments=0,
                            author=item['author'],
                            subreddit=sub_config['name'],
                            created_at=item['published'],
                            source='reddit',
                        ))
            except Exception as e:
                print(f"[Reddit] Lighthouse API 失败: {e}")

        return all_items[:self.max_items]
```

**优势：**
- ✅ 完全绕过本地代理问题
- ✅ Lighthouse 在美国，访问快
- ✅ 稳定可靠

**成本：**
- Lighthouse：¥36/月（已有）
- 开发时间：1-2 小时

---

### 方案 2：专注于可用的数据源 ⭐⭐⭐⭐⭐

**直接使用已有且可用的数据源：**

```yaml
# config.yaml
community:
  enabled: true

  sources:
    hackernews:
      enabled: true
      max_items: 30

    github:
      enabled: true
      max_items: 30

    producthunt:
      enabled: true
      max_items: 20

    reddit:
      enabled: false  # 暂时禁用

    twitter:
      enabled: false  # 暂时禁用
```

**优势：**
- ✅ 立即可用，无需任何修改
- ✅ HackerNews + GitHub + ProductHunt 已经很有价值
- ✅ 零成本

**劣势：**
- ⚠️ 缺少 Reddit 和 Twitter

---

### 方案 3：修复 Clash TLS 问题 ⭐⭐⭐

**尝试以下 Clash 配置调整：**

#### 选项 A：修改 Clash 的 TLS 版本

```yaml
# Clash 配置
tls:
  verify: true
  sni: true
  prefer-server-ciphers: true
  skip-cert-verify: false

# 为特定域名跳过 MITM
mitm:
  skip:
    - "old.reddit.com:443"
    - "www.reddit.com:443"
```

#### 选项 B：使用 TUN 模式

Clash Verge 的 TUN 模式可能对 TLS 的处理更友好。

#### 选项 C：切换到其他代理工具

- v2rayN
- Shadowsocks
- Qv2ray

**优势：** 修复后所有应用都能用
**劣势：** 需要时间调试，不确定能否成功

---

## 🎯 推荐方案

### 短期（今天）：方案 2
**启用可用数据源，让社区模块先跑起来**

### 中期（本周）：方案 1
**在 Lighthouse 上部署 API 服务，恢复 Reddit/Twitter**

### 长期（未来）：方案 3
**调试 Clash 配置，一劳永逸解决问题**

---

## 📊 方案对比

| 方案 | 时间 | 成本 | 可靠性 | 推荐度 |
|------|------|------|--------|--------|
| 方案 1 | 1-2小时 | ¥36/月 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| 方案 2 | 5分钟 | 免费 | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| 方案 3 | 2-4小时 | 免费 | ⭐⭐ | ⭐⭐⭐ |

---

## 🚀 立即行动

### 选项 A：先用方案 2（立即可用）

我可以立即帮你修改配置，启用 HackerNews、GitHub、ProductHunt。

### 选项 B：实施方案 1（一劳永逸）

我帮你：
1. 在 Lighthouse 上部署 API 服务
2. 修改 TrendRadar 代码
3. 测试验证

**你倾向哪个？** 或者我们先用方案 2 让系统跑起来，再慢慢实施方案 1？
