# Reddit API Token 获取指南

## 🎯 目标
获取 Reddit API 的 `client_id` 和 `client_secret`，用于访问 Reddit 数据。

---

## 📝 详细步骤

### 步骤 1：登录 Reddit
使用您的 Reddit 账号登录：
```
https://www.reddit.com/login/
```

---

### 步骤 2：访问应用创建页面
登录后，访问应用管理页面：
```
https://www.reddit.com/prefs/apps
```

或者：
1. 点击右上角用户名下拉菜单
2. 选择 "User Settings"（用户设置）
3. 点击左侧边栏的 "Developer Tools"（开发者工具）
4. 点击顶部 "Create App" 或滚动到底部 "create app"

---

### 步骤 3：创建应用

在页面底部找到 **"create app"** 或 **"create another app"** 按钮，填写以下信息：

| 字段 | 填写内容 | 说明 |
|------|---------|------|
| **name** | `TrendRadar` | 应用名称，任意填写 |
| **app type** | `script` | ⚠️ **必须选择 "script"** |
| **description** | `Community monitoring tool` | 可选 |
| **about url** | `http://localhost` | 可选，随便填 |
| **redirect uri** | `http://localhost:8080` | ⚠️ **必须填写** |

**重要提示**：
- ✅ **app type 必须选择 "script"**
- ✅ **redirect uri 必须填写**（即使是 http://localhost）

---

### 步骤 4：获取凭证

创建应用后，页面上方会显示您的应用信息，找到以下两行：

```
client_id     = 14字符的字符串（在 application name 下方）
client_secret = 27字符的字符串（标示为 "secret"）
```

**示例**（这是假数据）：
```python
client_id     = "pJxCx7uGvC8z5A"
client_secret = "your_reddit_client_secret"
```

**⚠️ 重要**：
- `client_id` 就是 **application name** 正下方显示的 14 字符字符串
- `client_secret` 是标示为 **"secret"** 的那一行
- 不要包含 "secret:" 前缀，只要后面的字符串

---

### 步骤 5：记录信息

请记录以下信息：

```python
# Reddit API 凭证
client_id     = "您的 client_id"
client_secret = "您的 client_secret"
user_agent    = "TrendRadar/1.0 by your_username"

# 您的 Reddit 用户名（用于 user_agent）
username = "your_reddit_username"
```

---

## 🔧 配置到 TrendRadar

获取到凭证后，我会帮您：

1. ✅ 修改 `config.yaml` 添加 Reddit API 配置
2. ✅ 更新 `RedditSource` 代码使用 API 而不是 RSS
3. ✅ 测试 API 连接

---

## 📊 Reddit API 限制

使用 Reddit API 的好处：

| 特性 | RSS 方式 | API 方式 |
|------|---------|---------|
| **速率限制** | 无限制但易被拦截 | 60 次/分钟（足够） |
| **内容完整性** | ❌ 标题+简短描述 | ✅ 完整内容+评论 |
| **反爬虫** | ❌ 经常 403 | ✅ 官方通道，稳定 |
| **认证要求** | 不需要 | 需要 token |

**速率限制详情**：
- 每分钟最多 60 次请求
- 对于我们的使用场景（每天收集一次）完全足够
- 10 个案例 = 10 次请求，远低于限制

---

## 🚀 下一步

完成上述步骤后，请提供：

1. `client_id`
2. `client_secret`
3. 您的 Reddit 用户名（用于生成 user_agent）

我会帮您配置并测试！

---

## 💡 注意事项

1. **保密性**：`client_secret` 相当于密码，不要分享或提交到公开仓库
2. **User Agent**：Reddit 要求 API 请求必须包含合理的 User Agent
3. **速率限制**：严格遵守速率限制，避免被封禁

---

## 📸 页面参考

创建应用后的页面布局：

```
┌─────────────────────────────────────────┐
│ your apps                               │
├─────────────────────────────────────────┤
│                                         │
│  Application Information                │
│  ┌───────────────────────────────────┐  │
│  │ application name: TrendRadar      │  │
│  │                                   │  │
│  │ client_id     <- 14字符字符串     │  │
│  │ client_secret <- 27字符字符串     │  │
│  │                                   │  │
│  │ redirect uri: http://localhost:8080│  │
│  └───────────────────────────────────┘  │
│                                         │
│  [delete] [edit]                        │
└─────────────────────────────────────────┘
```

---

## ✅ 验证清单

完成配置后，请确认：

- [ ] 已登录 Reddit 账号
- [ ] 已访问 https://www.reddit.com/prefs/apps
- [ ] 已创建应用（app type = script）
- [ ] 已填写 redirect uri
- [ ] 已找到 client_id（14 字符）
- [ ] 已找到 client_secret（27 字符）
- [ ] 已记录上述信息

---

**准备好后，将凭证提供给我，我会帮您完成配置！** 🚀
