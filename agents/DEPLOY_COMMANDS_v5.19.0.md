# 生产服务器部署更新 v5.19.0

## 📋 部署前检查

```bash
# 1. 查看当前版本
cat /install/trendradar/version

# 2. 查看待更新的提交
cd /install/trendradar
git log origin/master..HEAD --oneline
```

---

## 🚀 部署步骤

### 方案 1: Docker Compose 部署

```bash
# 1. 进入项目目录
cd /install/trendradar

# 2. 拉取最新代码
git pull origin master

# 3. 检查版本（确认更新）
cat version

# 4. 停止服务
docker-compose down

# 5. 重新构建并启动
docker-compose up -d --build

# 6. 查看日志（确认启动成功）
docker-compose logs --tail 100 -f
```

### 方案 2: 直接重启服务

```bash
# 1. 拉取最新代码
cd /install/trendradar
git pull origin master

# 2. 重启服务
docker-compose restart

# 3. 查看日志
docker-compose logs --tail 50
```

---

## ✅ 部署验证

### 1. 检查版本

```bash
cat /install/trendradar/version
# 应该显示: 5.19.0
```

### 2. 检查容器状态

```bash
docker-compose ps
# 确认所有服务都在运行
```

### 3. 检查日志

```bash
# 查看最新日志
docker-compose logs --tail 100

# 查看错误日志
docker-compose logs | grep -i error

# 查看配置加载
docker-compose logs | grep "系统配置加载"
```

### 4. 测试模块

```bash
# 进入容器
docker-compose exec trendradar bash

# 测试配置加载
python -m trendradar.cli config

# 退出容器
exit
```

---

## ⚠️ 本次更新注意事项

### 配置变更

**微信模块配置迁移**:
- 旧方式: `wechat/.env`
- 新方式: `config/system.yaml` 或环境变量

**验证配置**:

```bash
# 检查 system.yaml
cat /install/trendradar/config/system.yaml | grep -A 10 "notification:"

# 检查环境变量
docker-compose config | grep EMAIL
```

### 环境变量配置

确保 `docker-compose.yml` 中配置了环境变量：

```yaml
services:
  trendradar:
    environment:
      - EMAIL_PASSWORD=${EMAIL_PASSWORD}
      - AI_API_KEY=${AI_API_KEY}
      # 或直接写值（不推荐）
```

---

## 🔧 故障排查

### 问题 1: 配置加载失败

```bash
# 查看日志
docker-compose logs | grep "配置"

# 检查配置文件
cat /install/trendradar/config/system.yaml
```

### 问题 2: 邮件发送失败

```bash
# 检查环境变量
docker-compose exec trendradar env | grep EMAIL

# 测试邮件发送
docker-compose exec trendradar python -m trendradar.cli run investment
```

### 问题 3: 容器启动失败

```bash
# 查看详细错误
docker-compose logs

# 重新构建
docker-compose down
docker-compose up -d --build
```

---

## 📊 部署后验证清单

- [ ] 版本号更新到 5.19.0
- [ ] 所有容器正常运行
- [ ] 日志无错误信息
- [ ] 配置文件加载正常
- [ ] Investment 模块测试通过
- [ ] Community 模块测试通过
- [ ] WeChat 模块测试通过
- [ ] 邮件发送正常

---

## 🔄 回滚方案

如果部署出现问题，快速回滚：

```bash
cd /install/trendradar

# 查看旧版本
git log --oneline -10

# 回滚到上一个版本
git reset --hard HEAD~1  # 回退1个提交
# 或指定版本
# git reset --hard <commit-hash>

# 重启服务
docker-compose restart
```

---

生成时间: 2026-02-02 21:30
部署版本: v5.19.0
