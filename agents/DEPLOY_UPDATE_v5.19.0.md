# 部署更新 v5.19.0

## 📋 版本信息

**版本号**: v5.19.0
**发布日期**: 2026-02-02
**发布类型**: 功能发布（配置重构）

---

## ✅ 待推送提交

共 11 个新提交待推送：

```bash
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

---

## 🔐 推送问题

**当前错误**:
```
ERROR: Permission to sansan0/TrendRadar.git denied to youzhenxing
```

---

## 🔧 解决方案

### 方案 1: 使用 Personal Access Token（推荐）

#### 1. 生成 GitHub Token

1. 访问：https://github.com/settings/tokens
2. 点击 "Generate new token" → "Generate new token (classic)"
3. 设置权限：
   - ✅ `repo` （完整仓库访问权限）
4. 点击 "Generate token"
5. **复制 token**（只显示一次！）

#### 2. 推送代码

```bash
# 切换回 HTTPS
git remote set-url origin https://github.com/sansan0/TrendRadar.git

# 推送（会提示输入用户名和密码）
git push origin master

# 用户名: youzhenxing
# 密码: <粘贴你的 Personal Access Token>
```

---

### 方案 2: 配置 SSH 密钥

#### 1. 生成 SSH 密钥

```bash
# 生成密钥（如果已有则跳过）
ssh-keygen -t ed25519 -C "{{EMAIL_ADDRESS}}"

# 查看公钥
cat ~/.ssh/id_ed25519.pub
```

#### 2. 添加 SSH 密钥到 GitHub

1. 访问：https://github.com/settings/keys
2. 点击 "New SSH key"
3. 粘贴公钥内容
4. 点击 "Add SSH key"

#### 3. 推送代码

```bash
# 已切换到 SSH
git push origin master
```

---

### 方案 3: 使用 Git Credential Helper（最简单）

```bash
# 配置 credential helper
git config --global credential.helper store

# 切换到 HTTPS
git remote set-url origin https://github.com/sansan0/TrendRadar.git

# 推送（输入一次后会保存凭据）
git push origin master
# 输入用户名: youzhenxing
# 输入密码: <Personal Access Token>
```

---

## 📊 本次更新内容

### 主要变更

**微信模块配置统一化重构**:
- ✅ 移除独立的 `.env` 加载机制
- ✅ 统一到 `config/system.yaml`
- ✅ 实现配置合并算法
- ✅ 修正配置优先级

### 配置优先级（修正后）

```
1. 环境变量（最高优先级）
   ↓ 覆盖
2. config/system.yaml（统一配置）
   ↓ 覆盖
3. wechat/config.yaml（本地默认）
```

### 修复问题

1. ✅ 修正配置优先级
2. ✅ 修复微信邮件 markdown 渲染
3. ✅ 修复 AI 分析提示词路径
4. ✅ 更新邮件授权码
5. ✅ 移除 .env 文件跟踪

### 测试验证

- ✅ Investment 模块测试通过
- ✅ Community 模块测试通过
- ✅ WeChat 模块测试通过
- ⏸️ Podcast 模块待测试

---

## 🚀 部署步骤

### 1. 推送代码到远程

选择上述任一方案推送代码。

### 2. 服务器拉取更新

```bash
cd /install/trendradar
git pull origin master
```

### 3. 重启服务（如果需要）

```bash
# 使用 Docker Compose
cd /install/trendradar
docker-compose down
docker-compose up -d

# 或直接重启服务
docker-compose restart
```

### 4. 验证部署

```bash
# 检查版本
cat version

# 检查配置
cat config/system.yaml

# 测试运行
docker-compose logs --tail 50 trendradar
```

---

## ⚠️ 注意事项

### 环境变量配置

生产环境需要设置以下环境变量：

```yaml
# docker-compose.yml
services:
  trendradar:
    environment:
      - EMAIL_PASSWORD=your_password_here
      - AI_API_KEY={{SILICONFLOW_API_KEY}}_here
      # 或其他敏感配置
```

### 配置迁移

如果你之前使用了 `wechat/.env`：

1. 迁移配置到 `config/system.yaml` 或环境变量
2. 清空 `wechat/.env`（已有弃用说明）
3. 验证配置加载

---

## 📝 相关文档

- `agents/WECHAT_CONFIG_UNIFICATION.md` - 重构详细报告
- `agents/ALL_MODULES_CONFIG_ANALYSIS.md` - 配置机制分析
- `agents/ALL_MODULES_TEST_REPORT.md` - 测试验证报告

---

## 🎯 总结

**状态**: ✅ 代码已提交，等待推送

**待办**:
1. 使用上述方案之一推送代码到远程仓库
2. 服务器拉取更新
3. 验证部署

**风险**: 低（向后兼容，配置平滑迁移）

---

生成时间: 2026-02-02 21:30
版本: v5.19.0
