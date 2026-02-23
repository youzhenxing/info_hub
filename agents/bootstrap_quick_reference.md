# Bootstrap 快速参考指南

## 🚀 快速开始

### 执行验证
```bash
cd /home/zxy/Documents/code/TrendRadar
bash agents/verify_bootstrap.sh
```

### 手动触发 Bootstrap
```bash
# 删除标记文件
docker exec wechat-service rm /app/data/.wechat_bootstrap_done

# 重启容器
cd /home/zxy/Documents/code/TrendRadar/wechat
docker compose restart wechat-service

# 查看日志
docker logs wechat-service 2>&1 | grep -A 30 "Bootstrap"
```

---

## 📋 核心概念

### Bootstrap vs Daily

| 特性 | Bootstrap | Daily |
|------|-----------|-------|
| **触发时间** | 容器启动时 | 每天 23:00 |
| **文章来源** | 随机 3 个公众号 | 所有公众号 |
| **数据保存** | ❌ 不保存数据库 | ✅ 保存数据库 |
| **AI 分析** | ❌ 跳过 | ✅ 完整分析 |
| **推送类型** | `bootstrap` | `daily` |
| **邮件内容** | 简化版 | 完整版 |
| **执行时间** | 15-30 秒 | 5-15 分钟 |

---

## 🔍 常见问题

### Q1: Bootstrap 会污染数据库吗？
**A**: ❌ 不会。Bootstrap 采集的文章仅保存在内存中，不调用 `storage.save_article()`。

### Q2: Bootstrap 会影响 23:00 的推送吗？
**A**: ❌ 不会。Bootstrap 使用独立的推送类型 `bootstrap`，`has_pushed_today()` 只检查 `daily` 类型。

### Q3: 如何确认 Bootstrap 推送成功？
**A**: 检查以下内容：
1. 日志显示 `[Wechat][Bootstrap] 推送成功 ✅`
2. 收到验证邮件
3. 数据库文章数为 0（或只有之前的数据）
4. 推送记录中包含 `bootstrap` 类型

### Q4: 如何重新触发 Bootstrap？
**A**:
```bash
# 方法1: 删除标记文件并重启
docker exec wechat-service rm /app/data/.wechat_bootstrap_done
docker compose restart wechat-service

# 方法2: 修改 APP_VERSION 环境变量
```

### Q5: Bootstrap 邮件内容是什么？
**A**:
- 主题：包含日期
- 第一类文章：完整显示（原文 + 标题）
- 第二类文章：显示摘要
- 话题聚合：❌ 无（`topics=[]`）

---

## 🛠️ 调试命令

### 查看 Bootstrap 日志
```bash
# 实时查看
docker logs -f wechat-service 2>&1 | grep Bootstrap

# 查看最近 50 行
docker logs wechat-service 2>&1 | grep Bootstrap | tail -50

# 查看完整日志
docker logs wechat-service 2>&1 | grep -A 30 "Bootstrap"
```

### 查看推送记录
```bash
docker exec wechat-service python -c "
import sqlite3
conn = sqlite3.connect('/app/data/wechat.db')
cursor = conn.cursor()
cursor.execute('SELECT push_type, push_time, article_count FROM push_history ORDER BY push_time DESC LIMIT 10')
for r in cursor.fetchall():
    print(f'{r[0]} | {r[1]} | {r[2]} 篇')
"
```

### 查看数据库文章数
```bash
docker exec wechat-service python -c "
import sqlite3
conn = sqlite3.connect('/app/data/wechat.db')
cursor = conn.cursor()
cursor.execute('SELECT COUNT(*) FROM articles')
print(f'文章总数: {cursor.fetchone()[0]}')
"
```

### 查看标记文件版本
```bash
docker exec wechat-service cat /app/data/.wechat_bootstrap_done
```

---

## 📊 验证清单

### ✅ 成功标志
- [ ] 日志显示采集了 3 个公众号
- [ ] 日志显示推送成功 ✅
- [ ] 收到验证邮件
- [ ] 数据库文章数为 0（或只有之前的数据）
- [ ] 推送记录中包含 `bootstrap` 类型
- [ ] 标记文件已创建并包含当前版本号

### ❌ 失败排查
1. **未采集到文章**：检查公众号配置和 Wewe-RSS 服务
2. **推送失败**：检查邮件配置（SMTP、账号密码）
3. **数据库有新数据**：检查是否调用了 `storage.save_article()`
4. **未收到邮件**：检查垃圾邮件文件夹

---

## 🔄 工作流程

### 首次启动
```
容器启动 → Bootstrap 检查 → 随机采集 3 个公众号
→ 发送验证邮件 → 标记已完成 → 等待 23:00 定时任务
```

### 后续启动
```
容器启动 → Bootstrap 检查 → 版本已完成 → 跳过
→ 等待 23:00 定时任务
```

### 版本升级
```
容器启动 → Bootstrap 检查 → 版本不匹配 → 重新执行
→ 发送验证邮件 → 更新标记 → 等待 23:00 定时任务
```

---

## 📝 相关文件

| 文件 | 说明 |
|------|------|
| `wechat/main.py:221-345` | Bootstrap 函数实现 |
| `src/models.py` | DailyReport、Article、FeedType |
| `src/analyzer.py:109-110` | analyze_daily() 依赖数据库 |
| `src/storage.py` | record_push() 支持不同类型 |
| `src/notifier.py` | send_daily_report() 发送邮件 |

---

## 🎯 设计原则

1. ✅ **不污染数据库**：Bootstrap 采集的文章不保存
2. ✅ **验证功能**：立即发送邮件，确认功能正常
3. ✅ **快速执行**：跳过 AI 分析，缩短执行时间
4. ✅ **互不干扰**：不影响 23:00 的定时任务

---

**版本**: v5.24.0
**更新**: 2026-02-05
