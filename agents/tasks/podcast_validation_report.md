# 播客 RSS 源有效性验证报告

**验证时间**: 2026-01-30 15:20  
**更新时间**: 2026-01-30 15:45

---

## 当前状态

| 类别 | 数量 | 说明 |
|------|------|------|
| ✅ **稳定可用** | 8 | 直接可用，已验证 |
| ⏳ **临时限流** | 2 | rsshub.bestblogs.dev 限流，稍后可恢复 |
| ❌ **网络不通** | 11 | 需要代理或替代源 |

---

## 验证结果汇总

| 状态 | 数量 | 说明 |
|------|------|------|
| ✅ 有效 | 8 | RSS 可访问，包含音频 |
| ❌ 失败 | 13 | 无法访问或超时 |
| **总计** | **21** | |

---

## 详细结果

### ✅ 有效源 (8个)

| 播客名称 | 最新节目 | 节目数 | RSS 源 |
|----------|----------|--------|--------|
| 硅谷101 | 1月26日 | 15 | rsshub.bestblogs.dev |
| 张小珺Jùn｜商业访谈录 | 1月26日 | 15 | rsshub.bestblogs.dev |
| 罗永浩的十字路口 | 1月15日 | 15 | rsshub.bestblogs.dev |
| The a16z Show | 1月29日 | 1000 | feeds.simplecast.com |
| Latent Space | 1月30日 | 20 | latent.space |
| Lex Fridman Podcast | 1月13日 | 490 | lexfridman.com |
| Anything Goes with Emma Chamberlain | 1月26日 | 106 | feeds.megaphone.fm |
| Acquired | 1月26日 | 212 | feeds.transistor.fm |

### ❌ 失败源 (13个)

| 播客名称 | 错误类型 | 原因分析 |
|----------|----------|----------|
| 晚点聊 LateTalk | HTTP 404 | 源地址已失效 |
| The Prompt | HTTP 403 | 被服务器拒绝 |
| 硬地骇客 | HTTP 404 | 源地址已失效 |
| The Alphaist | 连接失败 | rsshub.app 无法访问 |
| 晚安咖啡 GoodNightCoffee | 连接失败 | rsshub.app 无法访问 |
| 投资实战派 | 连接失败 | rsshub.app 无法访问 |
| 十字路口 Crossing | 连接失败 | rsshub.app 无法访问 |
| On Board (创业邦) | 连接失败 | rsshub.app 无法访问 |
| The Joe Rogan Experience | 连接失败 | feeds.megaphone.fm 部分失败 |
| Modern Wisdom | 连接失败 | libsyn.com 无法访问 |
| The Diary of a CEO | 超时 | feeds.megaphone.fm 响应慢 |
| Business Breakdowns | 连接失败 | feeds.megaphone.fm 部分失败 |
| Huberman Lab | 连接失败 | feeds.megaphone.fm 部分失败 |

---

## 问题分析

### 1. rsshub.app 无法访问
`rsshub.app` 公共实例可能被墙或不稳定，影响 6 个播客。

**解决方案**:
- 使用替代实例：`rsshub.bestblogs.dev`（已验证可用）
- 或自建 RSSHub 实例
- 或使用播客官方 RSS 源

### 2. 部分 megaphone.fm 源不稳定
`feeds.megaphone.fm` 部分源无法访问（可能是地区限制）。

**解决方案**:
- 尝试使用代理
- 寻找替代 RSS 源（如 Apple Podcast RSS）

### 3. 源地址失效
`podcast.latepost.com/feed` 和 `hardhacker.com/feed` 返回 404。

**解决方案**:
- 需要更新 RSS 地址
- 或从 Apple Podcast / 小宇宙获取新源

---

## 推荐保留的播客列表

基于验证结果，以下 8 个播客源稳定可用：

```xml
<outline text="硅谷101" xmlUrl="https://rsshub.bestblogs.dev/xiaoyuzhou/podcast/5e5c52c9418a84a04625e6cc"/>
<outline text="张小珺Jùn｜商业访谈录" xmlUrl="https://rsshub.bestblogs.dev/xiaoyuzhou/podcast/626b46ea9cbbf0451cf5a962"/>
<outline text="罗永浩的十字路口" xmlUrl="https://rsshub.bestblogs.dev/xiaoyuzhou/podcast/68981df29e7bcd326eb91d88"/>
<outline text="The a16z Show" xmlUrl="https://feeds.simplecast.com/JGE3yC0V"/>
<outline text="Latent Space" xmlUrl="https://www.latent.space/feed"/>
<outline text="Lex Fridman Podcast" xmlUrl="https://lexfridman.com/feed/podcast/"/>
<outline text="Anything Goes with Emma Chamberlain" xmlUrl="https://feeds.megaphone.fm/anythinggoes"/>
<outline text="Acquired" xmlUrl="https://feeds.transistor.fm/acquired"/>
```

---

## 后续建议

1. **替换 rsshub.app 为 rsshub.bestblogs.dev** - 该实例目前稳定
2. **更新失效的源地址** - 晚点聊、硬地骇客需要新的 RSS 源
3. **添加备用源** - 为重要播客配置多个 RSS 源
4. **定期验证** - 建议每周自动验证一次源的有效性
