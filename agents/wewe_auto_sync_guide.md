# Wewe-RSS 自动同步说明

**更新时间**: 2026-02-07
**版本**: v1.0

---

## 📖 自动同步机制说明

### 默认行为：完全自动 ✅

**Wewe-RSS 配置**:
```yaml
CRON_EXPRESSION=0 */2 * * *  # 每2小时自动同步一次
```

**正常工作流程**:
```
1. Wewe-RSS 自动同步（每2小时）
   ↓
2. 获取最新的公众号文章
   ↓
3. 保存到数据库
   ↓
4. 微信服务定时触发（每天23:00）
   ↓
5. 从数据库采集文章
   ↓
6. AI分析并生成报告
   ↓
7. 发送邮件推送
```

**结论**: **正常情况下完全自动，无需手动操作** ✅

---

## ⚠️ 什么时候需要手动操作？

### 情况1: 微信读书账号失效 ⚠️

**原因**:
- 微信读书账号有时效性
- 可能几周或几个月需要重新登录一次

**症状**:
- Wewe-RSS 日志显示："暂无可用读书账号!"
- 微信服务采集不到最新文章
- 公众号文章数据陈旧

**解决方案**:
```bash
1. 访问 http://localhost:4000
2. 重新扫码登录微信读书
3. 点击"立即同步"按钮
4. 等待同步完成（2-5分钟）
```

**频率**: 偶尔发生（不是常态）

---

### 情况2: 想立即获取最新文章（可选）

**场景**:
- 刚发布重要文章
- 不想等2小时的自动同步
- 测试功能

**解决方法**:
```bash
# 方法1: Wewe-RSS 管理界面
访问 http://localhost:4000 → 点击"立即同步"

# 方法2: 重新触发微信服务采集
docker exec wechat-service python main.py run
```

**注意**: 这是可选操作，不是必须的

---

## 🛡️ 如何避免账号失效导致的问题？

### 自动监控方案（推荐）⭐

我已经创建了监控脚本：`agents/monitor_wewe_account.py`

**功能**:
- ✅ 自动检测 Wewe-RSS 账号状态
- ✅ 账号失效时发送告警邮件
- ✅ 提供详细的处理步骤

**使用方法**:

#### 方法1: 手动运行
```bash
cd /home/zxy/Documents/code/TrendRadar
python agents/monitor_wewe_account.py
```

#### 方法2: 添加到定时任务（推荐）

```bash
# 编辑 crontab
crontab -e

# 添加以下行（每天凌晨3点检查一次）
0 3 * * * cd /home/zxy/Documents/code/TrendRadar && python agents/monitor_wewe_account.py >> logs/wewe_monitor.log 2>&1
```

**效果**:
- 每天自动检查账号状态
- 账号失效时立即发送邮件通知
- 提前发现问题，避免影响推送

---

## 📊 账号状态检查

### 查看当前账号状态

```bash
# 方法1: 查看日志
docker logs wewe-rss --tail 50 | grep -E "ERROR|暂无可用账号"

# 方法2: 运行监控脚本
python agents/monitor_wewe_account.py
```

### 正常状态
```
✅ Wewe-RSS 运行正常，无需处理
```

### 异常状态
```
❌ 暂无可用读书账号!
⚠️ 检测到账号失效！
正在发送告警邮件...
```

---

## 🔄 完整的工作流程

### 日常运行（全自动）

```
00:00 - Wewe-RSS 自动同步
02:00 - Wewe-RSS 自动同步
04:00 - Wewe-RSS 自动同步
06:00 - Wewe-RSS 自动同步
08:00 - Wewe-RSS 自动同步
10:00 - Wewe-RSS 自动同步
12:00 - Wewe-RSS 自动同步
14:00 - Wewe-RSS 自动同步
16:00 - Wewe-RSS 自动同步
18:00 - Wewe-RSS 自动同步
20:00 - Wewe-RSS 自动同步
22:00 - Wewe-RSS 自动同步

23:00 - 微信服务自动采集 + 推送
```

**结论**: 全自动，无需干预 ✅

---

### 账号失效时（需要手动介入）

```
Wewe-RSS 自动同步失败（每2小时）
  ↓
监控脚本检测到账号失效（每天3点）
  ↓
发送告警邮件到 {{EMAIL_ADDRESS}}
  ↓
你收到告警
  ↓
手动重新登录 Wewe-RSS
  ↓
恢复正常
```

**结论**: 只有账号失效时才需要手动操作 ⚠️

---

## 🎯 推荐做法

### 日常维护

1. **添加监控到定时任务**（推荐）
   ```bash
   crontab -e
   # 添加
   0 3 * * * cd /home/zxy/Documents/code/TrendRadar && python agents/monitor_wewe_account.py >> logs/wewe_monitor.log 2>&1
   ```

2. **定期检查日志**（可选）
   ```bash
   # 查看最近1天的日志
   docker logs wewe-rss --since 24h | grep -E "ERROR|成功|sync"
   ```

3. **关注告警邮件**（重要）
   - 如果收到 "Wewe-RSS 账号失效告警"
   - 立即访问 http://localhost:4000 重新登录
   - 登录后自动同步恢复

---

## 📋 快速参考

### 正常情况
- ✅ 完全自动运行
- ✅ 每2小时自动同步
- ✅ 每天23:00自动推送
- ✅ 无需任何操作

### 账号失效时
- ⚠️ 会收到告警邮件
- ⚠️ 需要手动重新登录
- ⚠️ 登录后自动恢复

### 紧急情况（想立即同步）
```bash
# 访问管理页面
http://localhost:4000

# 点击"立即同步"按钮
# 或运行监控脚本检查状态
python agents/monitor_wewe_account.py
```

---

## ❓ 常见问题

### Q1: 需要每天手动点击同步吗？
**A**: 不需要！Wewe-RSS 每2小时自动同步一次。只有在账号失效时才需要手动重新登录。

### Q2: 账号多久会失效一次？
**A**: 不固定，可能几周或几个月。建议添加监控脚本，失效时会自动通知你。

### Q3: 如何知道账号是否有效？
**A**:
- 方法1: 运行监控脚本 `python agents/monitor_wewe_account.py`
- 方法2: 查看日志 `docker logs wewe-rss --tail 50`
- 方法3: 等待告警邮件（如果添加了监控）

### Q4: 重新登录后还需要做什么吗？
**A**: 不需要！重新登录后，自动同步会立即恢复，下次推送会正常工作。

---

## 📞 技术支持

如有问题，请查看：
- Wewe-RSS 日志: `docker logs wewe-rss`
- 微信服务日志: `docker logs wechat-service`
- 监控日志: `logs/wewe_monitor.log`

---

**总结**: **正常情况下完全自动，只在账号失效时需要手动重新登录** ✅

**建议**: 添加监控脚本到定时任务，提前发现问题
