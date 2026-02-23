# Clash 代理 SSL 问题修复指南

## 🔍 问题诊断

### 症状
```
通过 Clash 代理访问 Reddit/Twitter 时出现：
SSL: EOF occurred in violation of protocol
```

### 根本原因
Clash Verge 的 TLS 拦截/检查与某些网站的 TLS 配置不兼容。

---

## ✅ 解决方案

### 方案 A：在 Clash 配置中添加直连规则（推荐）

**操作步骤：**

1. **打开 Clash Verge 配置**
   - 点击 Clash Verge 图标
   - 选择「配置」或「Profiles」

2. **编辑当前配置文件**
   - 找到正在使用的配置
   - 点击「编辑」或「Edit」

3. **添加规则**

   在 `rules:` 部分添加：

   ```yaml
   rules:
     # Reddit 直连
     - DOMAIN-SUFFIX,reddit.com,DIRECT
     - DOMAIN-SUFFIX,old.reddit.com,DIRECT
     - DOMAIN-SUFFIX,redd.it,DIRECT

     # Twitter/Nitter 直连
     - DOMAIN-SUFFIX,twitter.com,DIRECT
     - DOMAIN-SUFFIX,x.com,DIRECT
     - DOMAIN-SUFFIX,nitter.net,DIRECT
     - DOMAIN-SUFFIX,nitter.poast.org,DIRECT

     # 其他规则...
     # - MATCH,PROXY
   ```

   或者使用 `MITM` 配置跳过这些域名的 TLS 检查：

   ```yaml
   mitm:
     skip:
       - "old.reddit.com:443"
       - "www.reddit.com:443"
       - "nitter.net:443"
   ```

4. **保存并重启 Clash**
   - 保存配置
   - 重启 Clash Verge
   - 等待几秒让配置生效

5. **测试连接**

   ```bash
   curl -x http://127.0.0.1:7897 https://old.reddit.com/r/MachineLearning/.rss
   ```

---

### 方案 B：修改 Reddit 数据源使用 HTTP（临时方案）

**文件：** `trendradar/community/sources/reddit.py`

**修改 `BASE_URL`：**

```python
# 原来
BASE_URL = "https://www.reddit.com"

# 改为
BASE_URL = "http://www.reddit.com"  # 注意：可能不稳定
```

**优点：** 无需修改 Clash 配置
**缺点：** Reddit 可能不支持 HTTP，或重定向到 HTTPS

---

### 方案 C：在 Python 中禁用特定域名的代理（代码层面）

**创建代理绕过机制：**

```python
import requests
from urllib.parse import urlparse

class SmartProxySession(requests.Session):
    """智能代理会话，某些域名不使用代理"""

    def __init__(self, proxy_url=None, no_proxy_domains=None):
        super().__init__()
        self.proxy_url = proxy_url
        self.no_proxy_domains = set(no_proxy_domains or [])

        if proxy_url:
            self.proxies = {"http": proxy_url, "https": proxy_url}

    def request(self, method, url, **kwargs):
        parsed = urlparse(url)
        domain = parsed.netloc

        # 检查是否应该跳过代理
        for no_proxy_domain in self.no_proxy_domains:
            if domain.endswith(no_proxy_domain):
                # 临时禁用代理
                old_proxies = self.proxies
                self.proxies = None
                try:
                    response = super().request(method, url, **kwargs)
                    return response
                finally:
                    self.proxies = old_proxies

        # 使用代理
        return super().request(method, url, **kwargs)

# 使用示例
session = SmartProxySession(
    proxy_url="http://127.0.0.1:7897",
    no_proxy_domains=["reddit.com", "old.reddit.com", "redd.it"]
)

# Reddit 访问将跳过代理
response = session.get("https://old.reddit.com/r/MachineLearning/.rss")
```

**集成到 RedditSource：**

```python
# reddit.py 修改

class RedditSource:
    def __init__(self, ..., proxy_url=None):
        # ...

        # 使用智能代理会话
        self.session = SmartProxySession(
            proxy_url=proxy_url,
            no_proxy_domains=["reddit.com", "old.reddit.com", "redd.it"]
        )
```

---

### 方案 D：使用环境变量控制代理（最简单）

**在启动 TrendRadar 时设置：**

```bash
# 设置代理但跳过某些域名
export HTTP_PROXY=http://127.0.0.1:7897
export HTTPS_PROXY=http://127.0.0.1:7897
export NO_PROXY=localhost,127.0.0.1,.reddit.com,.old.reddit.com,.redd.it

# 启动 TrendRadar
python -m trendradar.community.processor
```

**或者在配置文件中设置（config.yaml）：**

```yaml
community:
  proxy:
    enabled: true
    url: "http://127.0.0.1:7897"
    no_proxy:
      - "reddit.com"
      - "old.reddit.com"
      - "redd.it"
```

---

## 🎯 推荐方案对比

| 方案 | 难度 | 效果 | 维护成本 | 推荐度 |
|------|------|------|----------|--------|
| **A. Clash 规则** | ⭐ 简单 | ⭐⭐⭐⭐⭐ 完美 | ⭐ 低 | ⭐⭐⭐⭐⭐ |
| **B. HTTP 回退** | ⭐ 很简单 | ⭐⭐ 不稳定 | ⭐ 低 | ⭐⭐ |
| **C. 代码层面** | ⭐⭐⭐ 中等 | ⭐⭐⭐⭐ 稳定 | ⭐⭐ 中 | ⭐⭐⭐⭐ |
| **D. 环境变量** | ⭐ 很简单 | ⭐⭐⭐ 一般 | ⭐ 低 | ⭐⭐⭐ |

---

## 🚀 实施建议

**分两步走：**

### 第一步：快速验证（5分钟）
使用方案 D（环境变量）快速测试是否有效：

```bash
export NO_PROXY=.reddit.com,.old.reddit.com
python3 << 'EOF'
from trendradar.community.sources.reddit import RedditSource

source = RedditSource(
    subreddits=[{'name': 'MachineLearning', 'limit': 5}],
    proxy_url='http://127.0.0.1:7897'
)

items = source.fetch()
print(f"✅ 成功获取 {len(items)} 条数据")
EOF
```

### 第二步：长期解决（10分钟）
如果第一步有效，实施方案 A（Clash 规则）或方案 C（代码层面）。

---

## 📋 修改清单

### 选择方案 A：修改 Clash 配置

- [ ] 打开 Clash Verge 配置
- [ ] 添加 Reddit 直连规则
- [ ] 添加 Twitter/Nitter 直连规则
- [ ] 保存并重启 Clash
- [ ] 测试连接
- [ ] 验证 TrendRadar 可用

### 选择方案 C：修改代码

需要修改的文件：
- [ ] `trendradar/community/sources/reddit.py` - 添加 SmartProxySession
- [ ] `trendradar/community/sources/twitter.py` - 添加 SmartProxySession
- [ ] `trendradar/community/collector.py` - 传递 no_proxy 配置

---

## 🔧 额外提示

### 检查 Clash 配置是否生效

```bash
# 查看当前 Clash 使用的端口
netstat -tuln | grep 7897

# 测试代理是否工作
curl -x http://127.0.0.1:7897 https://api.github.com

# 查看代理出口 IP
curl -x http://127.0.0.1:7897 https://httpbin.org/ip
```

### 调试 Python requests 的代理问题

```python
import logging
import requests

# 启用详细日志
logging.basicConfig(level=logging.DEBUG)
logging.getLogger("urllib3").setLevel(logging.DEBUG)

# 测试请求
response = requests.get(
    "https://old.reddit.com/r/MachineLearning/.rss",
    proxies={"http": "http://127.0.0.1:7897", "https": "http://127.0.0.1:7897"}
)
```

---

## 📊 预期结果

修复后，你应该能看到：

```bash
$ python3 -c "
from trendradar.community.sources.reddit import RedditSource
source = RedditSource(subreddits=[{'name': 'MachineLearning', 'limit': 5}], proxy_url='http://127.0.0.1:7897')
items = source.fetch()
print(f'✅ 成功获取 {len(items)} 条数据')
"

✅ 成功获取 15 条数据
```

---

## 🆘 如果还是不行

1. **检查 Clash 日志**
   - Clash Verge → 日志
   - 查看是否有错误信息

2. **尝试其他 Clash 模式**
   - 切换到「规则模式」或「全局模式」
   - 或者「直连模式」

3. **使用其他代理工具**
   - v2ray
   - Shadowsocks
   - 或者不使用代理（直接访问，可能需要其他网络工具）

4. **最后方案：使用 Lighthouse**
   - 在 Lighthouse 上部署 Reddit scraper
   - 本地直接访问 Lighthouse
