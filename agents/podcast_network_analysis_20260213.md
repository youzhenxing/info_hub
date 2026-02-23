# 播客模块网络问题分析报告

**日期**: 2026-02-13
**问题**: 播客模块部分域名无法连接

---

## 执行时间线分析

### 播客模块执行记录（过去 24 小时）

| 开始时间 | 完成时间 | 耗时 | 成功推送 | 状态 |
|---------|---------|------|---------|------|
| 03:36:57 | - | - | - | Bootstrap（不推送） |
| 04:00:02 | 04:57:17 | 57 分钟 | Games Workshop | ✅ |
| 08:00:01 | 09:09:23 | 69 分钟 | Essentials: Using Play to Rewire & Improve Your Brain | ✅ |
| 12:00:01 | 13:24:25 | 84 分钟 | Anthropic's Cloud App Integrations and Hiring Challenges | ✅ |
| 16:00:00 | 17:09:23 | 69 分钟 | (无推送) | ✅ |
| 20:00:00 | 21:24:25 | 84 分钟 | (无推送) | ✅ |

**结论**：4 小时频率（CRON_SCHEDULE = `0 */4 * * *`）正常工作！

---

## 失败统计

### 失败类型

| 错误类型 | 次数 |
|---------|------|
| 下载超时（1800s） | 9 次 |
| 网络不可达（Network unreachable） | 6 次 |
| 转录超时（3600s） | 1 次 |

### 受影响的播客源

| 播客源 | 问题类型 |
|---------|---------|
| Lex Fridman Podcast | `media.blubrry.com` 网络不可达 |
| 投资实战派 | `feeds.soundon.fm` 网络不可达 |
| Modern Wisdom | 下载超时 |
| RSSHub（投资/社区模块） | `rsshub.app` 网络不可达 |

---

## 网络连接测试

### DNS 解析（正常）

```
media.blubrry.com → 108.160.170.44
feeds.soundon.fm → 202.160.130.117
rsshub.app → 108.160.162.102
```

### 连通性测试

| 目标 | 宿主机 | 容器内 | 结果 |
|------|---------|---------|------|
| api.siliconflow.cn | ✅ | ✅ | 正常 |
| api.deepseek.com | ✅ | ✅ | 正常 |
| cn.bing.com | ✅ | ✅ | 正常 |
| www.google.com | ❌ | ❌ | 超时 |
| media.blubrry.com | ❌ | ❌ | 网络不可达 |
| feeds.soundon.fm | ❌ | ❌ | 网络不可达 |
| rsshub.app | ❌ | ❌ | 连接失败 |

**IP 直接连测试**（绕过 DNS）：
- 108.160.170.44 (media.blubrry.com) → ❌ 无法连接
- 202.160.130.117 (feeds.soundon.fm) → ❌ 无法连接
- 108.160.162.102 (rsshub.app) → ❌ 无法连接

---

## 根本原因分析

### 1. GFW（防火墙）网络限制

**现象**：
- 国内服务（硅谷流、DeepSeek）可访问
- 国外服务（Google、Blubrry）被阻止

**结论**：**这是 GFW 导致的网络限制，不是代码问题**

### 2. Tailscale VPN 影响

系统运行 Tailscale VPN（100.99.204.70），但测试表明这不是主要问题：
- 宿主机和容器内都无法访问这些域名
- VPN 运行状态正常

### 3. 下载超时（30分钟）

配置的超时时间是 1800 秒（30分钟），对于大型播客文件（200-500MB）：
- 部分播客源（Modern Wisdom）的 CDN 响应慢
- 网络波动导致多次重试失败

---

## 解决方案建议

### 方案 1：调整播客源配置（推荐）

从播客源列表中移除无法访问的播客：

```yaml
# config/config.yaml
podcast:
  sources:
    # 移除或注释无法访问的源
    # - name: "Lex Fridman Podcast"
    #   url: "https://feeds.buzzsprout.com/1847531.rss"
    # - name: "投资实战派"
    #   url: "https://feeds.soundon.fm/..."
```

**优点**：立即生效，减少无效轮询
**缺点**：减少播客源数量

### 方案 2：增加代理支持（长期）

为播客下载和 RSS 抓取增加 HTTP/SOCKS5 代理支持：

```python
# 在 AudioDownloader 中添加代理支持
session = requests.Session()
session.proxies = {
    'http': os.environ.get('HTTP_PROXY'),
    'https': os.environ.get('HTTPS_PROXY')
}
```

**优点**：解决所有网络问题
**缺点**：需要额外配置代理服务器

### 方案 3：使用 RSSHub 镜像（临时）

使用 RSSHub 的国内镜像服务：

```
原地址: https://rsshub.app/quantum-bit
镜像: https://rsshub.rssforever.com/quantum-bit
```

**优点**：无需代码修改
**缺点**：依赖第三方镜像服务

### 方案 4：增加 CDN 失败降级（技术）

当主 CDN 失败时，尝试备用下载源：

```python
def download_audio(url: str) -> DownloadResult:
    # 尝试主 CDN
    result = try_download(url)
    if not result.success:
        # 尝试备用 CDN 或直接链接
        backup_url = get_backup_url(url)
        result = try_download(backup_url)
    return result
```

**优点**：提高成功率
**缺点**：需要维护备用源映射

---

## 当前配置验证

### CRON_SCHEDULE 配置
```
当前值: 0 */4 * * *
预期: 0 */4 * * * （每 4 小时执行）
```
✅ **配置正确，4 小时频率正常工作**

### 播客模块状态
```
轮询模式: 启用
目标: 成功推送 1 个节目
候选数量: 9-10 个
成功率: 10-12%
```

---

## 总结

### 问题分类

| 问题类型 | 严重程度 | 原因 | 解决方案 |
|---------|---------|------|---------|
| 4 小时频率不更新 | 🟢 无此问题 | 实际上频率正常 | 无需修复 |
| 某些域名无法访问 | 🔴 高 | GFW 防火墙限制 | 方案 1-4 |
| 下载超时 | 🟡 中 | 大文件 + CDN 慢 | 调整超时或使用代理 |

### 建议

**短期**：移除无法访问的播客源（方案 1）

**长期**：实现代理支持和 CDN 降级（方案 2 + 4）

**监控**：增加网络连通性检查，定期测试关键域名

---

## 相关文件

- `trendradar/podcast/downloader.py` - 音频下载器
- `trendradar/podcast/processor.py` - 播客处理器
- `trendradar/podcast/content_fetcher.py` - 内容抓取器
- `config/config.yaml` - 播客源配置
