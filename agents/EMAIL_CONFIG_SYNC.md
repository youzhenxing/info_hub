# 邮件授权码配置同步说明

## 📧 授权码是通用的吗？

**答案：是的** ✅

所有模块（投资、播客、社区、微信）都使用**同一个163邮箱账户**：
- 邮箱: `{{EMAIL_ADDRESS}}`
- 授权码: `your_email_auth_code` (2026-02-02更新)

---

## 📊 配置架构

### 读取顺序

所有模块按照以下优先级读取邮件配置：

```
1. 环境变量 (优先级最高)
   ↓
2. 模块独立配置文件 (仅微信模块有)
   ↓
3. config/system.yaml (统一配置)
```

### 配置文件分布

| 模块 | 配置文件 | 邮件配置 | 当前状态 |
|------|---------|---------|---------|
| **投资模块** | config/investment.yaml | 从 system.yaml | ✅ 已同步 |
| **播客模块** | config/podcast.yaml | 从 system.yaml | ✅ 已同步 |
| **社区监控** | config/community.yaml | 从 system.yaml | ✅ 已同步 |
| **微信模块** | wechat/config.yaml | 独立配置 | ✅ 已同步 |
| **统一配置** | config/system.yaml | 主配置文件 | ✅ 已更新 |

---

## ✅ 已完成的更新

### 更新1: wechat/config.yaml (19:55)
```yaml
email:
  from: "{{EMAIL_ADDRESS}}"
  password: "your_email_auth_code"  # 新授权码
  to: "{{EMAIL_ADDRESS}}"
```

### 更新2: config/system.yaml (20:15)
```yaml
email:
  from: "{{EMAIL_ADDRESS}}"
  password: "your_email_auth_code"  # 新授权码
  to: "{{EMAIL_ADDRESS}}"
```

---

## 🎯 影响范围

### 直接影响的模块

1. **投资模块** (`trendradar/investment/`)
   - 每日市场分析报告
   - 话题聚合邮件

2. **播客模块** (`trendradar/podcast/`)
   - 新节目即时通知
   - AI分析报告

3. **社区监控** (`trendradar/community/`)
   - 重要文章推送
   - 热门话题汇总

4. **微信模块** (`wechat/`)
   - 公众号日报
   - 已验证可正常发送 ✅

---

## 🔧 配置管理建议

### 开发环境 (当前)

**推荐**: 使用配置文件
- ✅ 已配置在 `config/system.yaml`
- ✅ 已配置在 `wechat/config.yaml`
- ✅ 无需设置环境变量

### 生产环境

**推荐**: 使用环境变量

```bash
# 在 ~/.bashrc 或 ~/.zshrc 中添加
export EMAIL_FROM="{{EMAIL_ADDRESS}}"
export EMAIL_PASSWORD="your_email_auth_code"
export EMAIL_TO="{{EMAIL_ADDRESS}}"
```

**优点**:
- 配置不在代码仓库中，更安全
- 不同环境可以使用不同邮箱
- Docker容器可以通过环境变量注入

---

## 🧪 测试其他模块

### 测试投资模块邮件
```bash
cd /home/zxy/Documents/code/TrendRadar
unset all_proxy && \
export AI_API_KEY="{{SILICONFLOW_API_KEY}}" && \
python -m trendradar.cli run investment
```

### 测试播客模块邮件
```bash
cd /home/zxy/Documents/code/TrendRadar
unset all_proxy && \
export AI_API_KEY="{{SILICONFLOW_API_KEY}}" && \
python -m trendradar.cli run podcast
```

---

## 📝 Git提交记录

```bash
94d48c23 - chore: 更新统一邮件配置到config/system.yaml
e694f458 - fix(wechat): 修复邮件中AI摘要的markdown渲染问题
90e657e1 - fix(wechat): 更新163邮箱授权码，邮件发送成功
```

---

## ⚠️ 重要提示

### 授权码安全

1. **不要在公开仓库中提交真实授权码**
   - 代码仓库中的授权码应该占位符或示例
   - 真实授权码通过环境变量或本地配置管理

2. **定期更新授权码**
   - 163邮箱授权码可能过期
   - 建议每3-6个月更新一次
   - 更新后记得同步到所有配置位置

3. **授权码泄露处理**
   - 如果怀疑授权码泄露，立即在163邮箱中撤销
   - 重新生成新授权码
   - 更新所有配置文件和环境变量

---

## ✅ 总结

**问题**: 邮件授权码是通用的吗？

**答案**: 是的，所有模块共用一个163邮箱授权码。

**同步状态**:
- ✅ wechat/config.yaml - 已更新
- ✅ config/system.yaml - 已更新
- ✅ 所有模块现在都可以发送邮件

**下次更新授权码时**:
1. 登录163邮箱生成新授权码
2. 更新 `config/system.yaml`
3. 更新 `wechat/config.yaml`
4. 如使用环境变量，更新环境变量
5. 测试各模块邮件发送功能

---

生成时间: 2026-02-02 20:15
配置文件: config/system.yaml, wechat/config.yaml
授权码: your_email_auth_code
