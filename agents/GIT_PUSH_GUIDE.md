# Git 推送指南 - v5.19.0

## 📋 当前状态

**本地提交**: 14 个新提交待推送
**远程仓库**: https://github.com/sansan0/TrendRadar.git
**推送问题**: Permission denied (403)

---

## 🔐 解决方案

### 方案 1: 使用 Personal Access Token（推荐）

#### 步骤 1: 生成 GitHub Token

1. 访问：https://github.com/settings/tokens
2. 点击 "Generate new token" → "Generate new token (classic)"
3. 设置权限：
   - ✅ `repo` （完整仓库访问权限）
4. 点击 "Generate token"
5. **复制 token**（只显示一次！）

#### 步骤 2: 推送代码

```bash
# 推送（会提示输入用户名和密码）
git push origin master

# 用户名: youzhenxing
# 密码: <粘贴你的 Personal Access Token>
```

---

### 方案 2: 配置 Git Credential Helper（最简单）

```bash
# 配置 credential helper
git config --global credential.helper store

# 推送（输入一次后会保存凭据）
git push origin master

# 输入用户名: youzhenxing
# 输入密码: <Personal Access Token>
```

---

### 方案 3: 使用 SSH 密钥

#### 步骤 1: 生成 SSH 密钥

```bash
# 生成密钥（如果已有则跳过）
ssh-keygen -t ed25519 -C "{{EMAIL_ADDRESS}}"

# 查看公钥
cat ~/.ssh/id_ed25519.pub
```

#### 步骤 2: 添加 SSH 密钥到 GitHub

1. 访问：https://github.com/settings/keys
2. 点击 "New SSH key"
3. 粘贴公钥内容
4. 点击 "Add SSH key"

#### 步骤 3: 切换到 SSH 并推送

```bash
# 切换到 SSH
git remote set-url origin git@github.com:sansan0/TrendRadar.git

# 推送
git push origin master
```

---

## 📊 待推送的提交

```bash
e7d6301a docs(log): 添加 2026-02-02 开发日志
255d7172 docs(deploy): 添加 v5.19.0 部署成功报告
0ba21f6e release: v5.19.0 - 微信模块配置统一化重构
43b7ca18 test(all): 添加全模块统一配置测试报告
8dec7b2e fix(wetchat): 修正配置优先级，system.yaml 应该覆盖本地配置
932f3bff test(wechat): 添加统一配置重构后的测试报告
54c44808 refactor(wetchat): 统一配置管理到config/system.yaml
fbc9985b security: 移除.env文件跟踪，更新.gitignore和示例文件
7395e76b chore: 同步邮件授权码到wechat/.env环境变量文件
94d48c23 chore: 更新统一邮件配置到config/system.yaml
e694f458 fix(wechat): 修复邮件中AI摘要的markdown渲染问题
90e657e1 fix(wechat): 更新163邮箱授权码，邮件发送成功
ac5e2aab fix(wechat): 修复AI分析提示词路径和数据序列化问题
0ba21f6e release: v5.19.0 - 微信模块配置统一化重构
```

共 **14 个提交**待推送。

---

## 🔍 验证推送

推送后验证：

```bash
# 检查远程提交
git log origin/master --oneline -10

# 或访问 GitHub
# https://github.com/sansan0/TrendRadar/commits/master
```

---

## 💡 推荐方案

**最简单**: 方案 2（Credential Helper）

**最安全**: 方案 1（Personal Access Token）

**最便捷**: 方案 3（SSH 密钥，一次配置永久使用）

---

生成时间: 2026-02-02 21:30
待推送提交: 14 个
最新版本: v5.19.0
