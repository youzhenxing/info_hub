# CLAUDE.md 微信模块机制说明更新报告

## 📅 更新时间
**2026-02-09 19:15**

---

## 🎯 更新目的

为 CLAUDE.md 添加微信公众号模块的完整机制说明，使其他 agent 能够快速理解该模块的架构、运行方式和数据流。

---

## 📝 主要新增内容

### 1️⃣ 微信模块架构与运行机制

**新增章节**：`### 微信模块架构与运行机制`

包含内容：
- ✅ 架构概览（三层架构图）
- ✅ 数据流机制（分阶段说明）
- ✅ 核心要点总结

**架构说明**：
```
主系统 (trendradar-prod)     ← 独立
    ↓ 独立
微信模块 (wechat-service)   ← 独立容器
    ↓ 依赖
Wewe-RSS (wewe-rss)        ← 独立服务
```

**关键理解**：
```
手动更新 wewe-rss
    ↓
抓取文章并存入数据库
    ↓
账号失效 → 文章仍在数据库 ✅
    ↓
微信模块 23:00 读取 API
    ↓
AI 分析 + 推送 ✅
```

### 2️⃣ 容器管理

**新增命令**：
```bash
# 查看容器状态
docker ps | grep wechat

# 查看日志
docker logs wechat-service --tail 50
docker logs wewe-rss --tail 50

# 重启服务
docker restart wechat-service
docker restart wewe-rss
```

**容器配置说明**：
- `wechat-service`: 独立容器，不依赖主系统
- `wewe-rss`: SQLite版本，端口 4000
- 网络隔离：通过 localhost:4000 通信

### 3️⃣ wewe-rss 账号管理

**手动更新策略**（推荐）：
```bash
# 每天早上8点执行
1. 访问 http://localhost:4000
2. 扫码登录微信读书（如需要）
3. 点击"全部更新"按钮
4. 验证 syncTime 更新时间
```

**定时更新配置**：
```yaml
CRON_EXPRESSION: 0 */2 * * *    # 每2小时
UPDATE_DELAY_TIME: 60           # 间隔60秒
```

**重试机制**：
- 失败时每30秒重试
- 仅账号有效时成功
- 不影响已有数据

### 4️⃣ 常见问题与解决方案

**问题1：EmailRenderer 模块导入失败**
```
ModuleNotFoundError: No module named 'shared'
```
- **原因**：主系统v5.4.0缺少 shared/lib 挂载
- **解决**：已在 v5.25.3 修复
- **影响**：邮件渲染降级，但仍能发送

**问题2：Wewe-RSS 账号 API 不可用**
```
[WARNING] Wewe-RSS 账号 API 不可用
```
- **原因**：账号监控API端点变更
- **影响**：无法自动监控账号状态（非核心功能）
- **解决**：可忽略

**问题3：订阅源长时间未更新**
- **检查方法**：使用 curl 命令检查 syncTime
- **解决方案**：手动点击"全部更新"

### 5️⃣ 数据验证命令

**检查数据新鲜度**：
```bash
curl -s http://localhost:4000/feeds | python3 -c "
import json, sys
from datetime import datetime
data = json.load(sys.stdin)
now = datetime.now().timestamp()
for feed in data[:10]:
    hours = (now - feed['syncTime']) / 3600
    print(f\"{feed['name']}: {hours:.1f}小时前\")
"
```

**检查文章数量**：
```bash
docker exec wechat-service python -c "
import sqlite3
conn = sqlite3.connect('/app/data/wechat.db')
cur = conn.cursor()
cur.execute('SELECT COUNT(*) FROM articles WHERE published_at > datetime(\"now\", \"-2 days\")')
print(f'最近2天文章数: {cur.fetchone()[0]}')
conn.close()
"
```

### 6️⃣ 微信报告示例链接

**新增访问示例**：
```
微信公众号日报：
file:///home/zxy/Documents/code/TrendRadar/wechat/data/output/wechat_daily_20260208_230746.html
```

---

## 📊 更新统计

| 项目 | 更新前 | 更新后 |
|------|--------|--------|
| **微信模块说明** | ❌ 无 | ✅ 完整架构说明 |
| **数据流机制** | ❌ 无 | ✅ 三阶段详细说明 |
| **wewe-rss 管理** | ❌ 无 | ✅ 手动+定时策略 |
| **常见问题** | ❌ 无 | ✅ 3个问题+解决方案 |
| **验证命令** | ❌ 无 | ✅ 数据新鲜度检查 |
| **报告示例** | ❌ 无 | ✅ 最新报告链接 |

---

## 🎯 关键要点

### 对其他 Agent 的帮助

1. **快速理解架构**
   - 微信模块是独立容器（不在 trendradar-prod）
   - 依赖 wewe-rss 服务（数据源）
   - 数据采集与推送解耦

2. **常见问题排查**
   - 无文章：检查 wewe-rss 是否手动更新
   - 推送失败：检查邮件配置和容器状态
   - API 不可用：可忽略（非核心功能）

3. **维护建议**
   - 每天早上手动更新 wewe-rss
   - 定期检查订阅源同步时间
   - 关注最新报告内容

---

## 📚 相关文档

- 微信模块状态报告：`agents/wechat_module_status_report.md`
- wewe-rss 使用指南：`agents/wewe_auto_sync_guide.md`
- 部署相关规则：CLAUDE.md（规则0-10）

---

## ✅ 验证清单

- [x] **架构说明清晰**：三层架构图 + 数据流图
- [x] **容器管理完整**：启动、停止、日志查看
- [x] **账号管理策略**：手动+定时说明
- [x] **问题解决指南**：3个常见问题+解决方案
- [x] **验证命令可用**：数据新鲜度+文章数量
- [x] **报告示例链接**：实际可访问的HTML路径

---

*更新人：Claude Sonnet 4.5*
*更新时间：2026-02-09 19:15*
