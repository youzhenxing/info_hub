# 邮件推送配置成功记录

**配置时间**: 2026-01-28 11:54
**配置状态**: ✅ 成功

---

## 📧 配置信息

### 邮箱账户
- **邮箱服务商**: 163 邮箱
- **发件人邮箱**: {{EMAIL_ADDRESS}}
- **收件人邮箱**: {{EMAIL_ADDRESS}}（发给自己）
- **授权码**: your_email_auth_code

### SMTP 配置
- **服务器地址**: smtp.163.com
- **端口**: 465 (SSL)
- **认证方式**: 授权码认证

---

## 🛠️ 配置过程

### 1. 获取授权码
用户已在 163 邮箱设置中开启 SMTP 服务并获取授权码。

### 2. 修改配置文件
**文件**: `config/config.yaml`
**位置**: 第 250-255 行

```yaml
email:
  from: "{{EMAIL_ADDRESS}}"        # 发件人邮箱地址
  password: "your_email_auth_code"    # 发件人邮箱密码或授权码
  to: "{{EMAIL_ADDRESS}}"          # 收件人邮箱，多个用逗号分隔
  smtp_server: "smtp.163.com"     # SMTP 服务器
  smtp_port: "465"                # SMTP 端口
```

### 3. 重启容器
```bash
docker restart trendradar
```

### 4. 验证配置
容器启动日志显示：
```
配置文件加载成功: /app/config/config.yaml
通知渠道配置来源: 邮件(配置文件)
通知功能已启用，将发送通知
```

---

## ✅ 测试结果

### 首次邮件发送
**时间**: 2026-01-28 11:55:15
**内容**: 热榜 42 条新闻
**状态**: ✅ 发送成功

### 日志记录
```
[推送] 准备发送：热榜 42 条，合计 42 条
正在发送邮件到 {{EMAIL_ADDRESS}}...
邮件发送成功 [当前榜单] -> {{EMAIL_ADDRESS}}
```

---

## 📊 推送规则

### 通知设置
- **通知功能**: ✅ 已启用 (`notification.enabled: true`)
- **推送时间窗口**: 20:00 - 22:00（北京时间）
- **窗口内推送频率**: 每天一次 (`once_per_day: true`)

### 抓取设置
- **定时规则**: `*/30 * * * *`（每 30 分钟）
- **运行模式**: 当前榜单模式 (current)
- **监控平台**: 11 个（今日头条、百度、微博等）

### 推送逻辑
1. 每 30 分钟自动抓取一次数据
2. 检查是否在推送时间窗口内（20:00-22:00）
3. 如果在窗口内且今天还没推送过，则发送邮件
4. 邮件包含当前榜单的热点新闻

---

## 📧 邮件格式

### 邮件主题
```
[当前榜单] TrendRadar 热点新闻推送
```

### 邮件内容
- **格式**: HTML
- **数据源**: 11 个热榜平台
- **展示方式**: 按平台分组
- **包含信息**:
  - 新闻标题
  - 热度值
  - 原文链接
  - 平台来源
  - 抓取时间

---

## 🔧 高级配置选项

### 修改推送时间窗口
编辑 `config/config.yaml`：
```yaml
notification:
  time_window:
    enabled: true
    start: "09:00"      # 修改开始时间
    end: "18:00"        # 修改结束时间
    once_per_day: true
```

### 添加多个收件人
```yaml
email:
  to: "{{EMAIL_ADDRESS}},other@example.com"  # 逗号分隔
```

### 调整抓取频率
编辑 `docker-compose-build.yml`：
```yaml
environment:
  - CRON_SCHEDULE=*/15 * * * *  # 改为每 15 分钟
```

---

## 📝 使用建议

### 1. 检查邮件接收
- 首次接收建议检查垃圾邮件文件夹
- 将发件人添加到通讯录避免进入垃圾箱
- 163 邮箱可能会有延迟，通常 1-2 分钟内到达

### 2. 推送时间优化
当前设置为晚上 20:00-22:00 推送，这是合理的选择：
- 避免白天工作时间打扰
- 晚上有时间阅读新闻
- 每天一次汇总，信息量适中

### 3. 邮件管理
- 定期清理旧邮件避免占用空间
- 可以设置邮件规则自动归类到特定文件夹
- 重要新闻可以标星保存

### 4. 安全提示
- 授权码已保存在配置文件中，注意文件权限
- 如果授权码泄露，可在 163 邮箱设置中重新生成
- 不要将配置文件提交到公开的代码仓库

---

## 🔍 故障排查

### 如果没有收到邮件

1. **检查垃圾邮件文件夹**
   ```
   163邮箱 > 垃圾邮件
   ```

2. **查看容器日志**
   ```bash
   docker logs trendradar | grep -i email
   ```

3. **检查推送时间**
   - 确认当前时间是否在 20:00-22:00 窗口内
   - 或者手动触发测试：
   ```bash
   docker exec -it trendradar python manage.py run
   ```

4. **验证邮箱配置**
   ```bash
   docker exec -it trendradar cat /app/config/config.yaml | grep -A 5 "email:"
   ```

5. **检查 SMTP 连接**
   - 163 邮箱可能限制频繁发送
   - 确认授权码没有过期
   - 检查网络是否可以访问 smtp.163.com:465

### 常见错误

**错误 1**: `Authentication failed`
- 原因：授权码错误或已失效
- 解决：重新获取授权码并更新配置

**错误 2**: `Connection timeout`
- 原因：网络无法访问 SMTP 服务器
- 解决：检查防火墙设置，确保 465 端口开放

**错误 3**: `Sender address rejected`
- 原因：发件人邮箱格式错误
- 解决：确认邮箱地址正确无误

---

## 📈 监控与维护

### 日志监控
定期检查日志确保邮件正常发送：
```bash
# 查看最近的邮件发送记录
docker logs trendradar | grep "邮件发送"

# 实时监控日志
docker logs trendradar -f
```

### 配置备份
建议定期备份配置文件：
```bash
cp config/config.yaml config/config.yaml.backup
```

### 授权码管理
- 授权码保存在配置文件中，定期检查是否过期
- 建议使用环境变量管理敏感信息（生产环境）
- 可以为不同应用生成不同的授权码

---

## 🎯 后续优化

### 可选改进

1. **使用环境变量**
   ```yaml
   # docker-compose-build.yml
   environment:
     - EMAIL_FROM={{EMAIL_ADDRESS}}
     - EMAIL_PASSWORD=your_email_auth_code
   ```

2. **配置多个通知渠道**
   - 邮件 + 飞书
   - 邮件 + Telegram
   - 同时推送到多个渠道

3. **自定义邮件模板**
   - 修改 HTML 样式
   - 添加个性化内容
   - 优化移动端显示

4. **智能推送**
   - 只推送包含特定关键词的新闻
   - 根据新闻热度筛选
   - 设置不同主题的推送规则

---

## 📚 相关文档

- [Docker 部署问题修复](./docker-deployment-fix.md)
- [TrendRadar 配置说明](../config/config.yaml)
- [Docker Compose 配置](../docker/docker-compose-build.yml)

---

**配置完成时间**: 2026-01-28 11:55
**首次邮件发送**: 2026-01-28 11:55
**配置状态**: ✅ 完全成功
