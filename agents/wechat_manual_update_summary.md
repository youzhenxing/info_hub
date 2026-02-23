# 微信公众号模块关闭自动更新说明

## 修改日期
2026-02-10

## 修改内容

### 问题描述
- **原配置**：wewe-rss 每 2 小时自动更新所有公众号订阅源
- **存在问题**：频繁自动更新容易被微信限流，导致账号失效

### 解决方案
- **新配置**：关闭 CRON_EXPRESSION，改为手动触发模式
- **更新方式**：每天早上手动执行一次更新

---

## 修改的文件

### 1. 配置文件修改
**文件**：`wechat/docker-compose.yml`

**修改内容**：
```yaml
# 修改前（第 30 行）
- CRON_EXPRESSION=0 */2 * * *

# 修改后（已注释）
# ⚠️ 已关闭自动定时更新，改为手动触发以避免限流
# - CRON_EXPRESSION=0 */2 * * *
```

### 2. 新增手动更新脚本
**文件**：`wechat/update-feeds.sh`

**功能**：
- 检查容器状态
- 逐个更新所有订阅源
- 显示更新进度和统计
- 提供下一步操作提示

**使用方法**：
```bash
cd /home/zxy/Documents/code/TrendRadar/wechat
bash ./update-feeds.sh
```

### 3. 文档更新
**文件**：`CLAUDE.md`

**新增章节**：`🔄 手动更新公众号订阅源`

**内容**：
- 推荐更新时机
- 三种手动更新方式
- 更新后验证方法
- 常见问题解答

---

## 验证结果

### 容器重建
```bash
# 重新创建容器以应用新配置
cd /home/zxy/Documents/code/TrendRadar/wechat
docker compose down && docker compose up -d
```

### 环境变量验证
```bash
# 验证 CRON_EXPRESSION 已移除
docker exec wewe-rss printenv | grep -i cron
# （无输出，说明已成功移除）
```

### 容器状态
```bash
$ docker ps | grep -E "wewe|wechat"
48d393e0e033   wechat-wechat-service   "python main.py sche…"   13 seconds ago   Up 7 seconds
92bd76117473   wewe-rss-sqlite:local   "docker-entrypoint.s…"   13 seconds ago   Up 12 seconds (healthy)
```

✅ 两个容器都正常运行

---

## 使用建议

### 推荐操作流程

**每天早上 8:00-10:00**：
1. 检查服务状态：访问 http://localhost:4000
2. 如果账号失效，扫码登录微信读书
3. 执行更新脚本：`bash ./update-feeds.sh`
4. 等待更新完成（约 5-15 分钟）
5. 触发微信模块分析：`trend run wechat`

### 避免限流的注意事项

1. **不要频繁更新**：每天 1 次即可
2. **避开高峰期**：早上 8-10 点或晚上 8-10 点
3. **设置更新延迟**：`UPDATE_DELAY_TIME=60`（每个订阅源间隔 60 秒）
4. **限制请求频率**：`MAX_REQUEST_PER_MINUTE=30`

---

## 技术要点

### 为什么需要重建容器？

Docker 容器的环境变量在启动时加载，重启容器（`docker restart`）不会重新读取环境变量，必须重新创建容器（`docker compose down && up -d`）。

### CRON_EXPRESSION 的作用

Wewe-RSS 使用 node-cron 库实现定时任务，`CRON_EXPRESSION` 环境变量控制订阅源自动更新的时间间隔。

**原配置**：`0 */2 * * *`（每 2 小时执行一次）
**新配置**：已注释（禁用自动更新）

### 手动更新的优势

1. **避免限流**：手动控制更新时机和频率
2. **账号安全**：减少与微信读书 API 的交互次数
3. **灵活可控**：根据需要决定是否更新
4. **问题排查**：更新失败时能及时发现并处理

---

## 相关文件

- **配置文件**：`wechat/docker-compose.yml`
- **更新脚本**：`wechat/update-feeds.sh`
- **项目规范**：`CLAUDE.md`
- **容器日志**：`docker logs wewe-rss --tail 50`
- **Web 界面**：http://localhost:4000

---

## 后续优化建议

1. **监控机制**：添加订阅源更新状态监控，超过 24 小时未更新时发送提醒
2. **健康检查**：定期检查账号状态，提前预警账号失效
3. **批量更新**：优化更新脚本，支持并行更新（注意控制速率）
4. **数据分析**：统计各公众号的更新频率，动态调整更新策略
